"""ClaudeCode -> Codex direct review adapter.

Symmetric to `codex_to_claude.py`, but for the reverse direction: a
ClaudeCode-primary turn asks the local Codex CLI for an unattended full-access
review via `codex exec`, WITHOUT depending on the official Codex plugin. This
keeps the skill self-contained and distributable (it needs only the `claude`
and `codex` CLIs), and sidesteps the plugin broker.

Shared guards (round cap, redaction, fail-closed, cost log) are imported from
`codex_to_claude` so both directions enforce the exact same protocol.

Pure stdlib. The subprocess boundary is injectable (`runner`) so unit tests
never make real Codex calls.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Optional

from .codex_to_claude import (
    ReviewResult,
    _commit_round_unlocked,
    _known_sensitive_values,
    _reserve_attempt_unlocked,
    _safe_gate_id,
    check_attempt_cap,
    emit_review_started,
    fail_closed,
    gate_failure_result,
    log_cost,
    MODEL_FLAG,
    build_reviewer_prompt,
    persist_success,
    round_cap_guard,
    validate_requested_model,
)

DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
# Auth-failure signatures in codex stderr. Specific phrases only (no bare "login").
_CODEX_AUTH_PHRASES = (
    "not logged in",
    "unauthorized",
    "forbidden",
    "authentication",
    "authenticate",
    "401",
    "403",
)


def codex_available() -> bool:
    """True when the `codex` CLI is on PATH. Portability precheck."""
    return shutil.which("codex") is not None


def codex_supports_model(
    executable: Optional[str] = None,
    help_runner: Callable = subprocess.run,
    timeout_seconds: float = 5,
) -> Optional[bool]:
    """Best-effort check that ``codex exec`` accepts the model flag."""
    exe = executable or shutil.which("codex")
    if not exe:
        return None
    try:
        completed = help_runner(
            [exe, "exec", "--help"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (getattr(completed, "stdout", "") or "") + (getattr(completed, "stderr", "") or "")
    return None if not text.strip() else MODEL_FLAG in text


def build_codex_command(
    cd: str,
    last_message_path: str,
    output_schema: Optional[str] = None,
    skip_git_repo_check: bool = True,
    model: Optional[str] = None,
) -> list:
    """Assemble an unattended full-access `codex exec` argv.

    The sandbox and approval bypass are hardcoded rather than caller-tunable:
    review subprocesses may use verification tools and write their requested
    review output without stalling for non-interactive confirmation. The review
    prompt still forbids modifying the reviewed artifact or primary-owned
    state. Review instructions are passed via stdin, never argv.
    """
    argv = [
        "codex",
        "exec",
        # Keep both flags: the sandbox mode declares the intended full-access
        # profile, while the bypass flag guarantees non-interactive execution.
        "--sandbox",
        "danger-full-access",
        "--dangerously-bypass-approvals-and-sandbox",
        "--json",
        "--output-last-message",
        last_message_path,
        "-C",
        cd,
    ]
    if skip_git_repo_check:
        argv.append("--skip-git-repo-check")
    requested_model = validate_requested_model(model)
    if requested_model is not None:
        argv.append(f"--model={requested_model}")
    if output_schema:
        argv += ["--output-schema", output_schema]
    return argv


def classify_codex(exit_code: int, last_message_text: Optional[str], stderr: str = "") -> str:
    """Classify a codex exec run: 'success' | 'auth_failure' | 'other_error'.

    Readiness is judged by a real result (non-empty last message on exit 0),
    never by a status command.
    """
    text = last_message_text if isinstance(last_message_text, str) else ""
    err = (stderr or "").lower()
    if exit_code != 0 and any(phrase in err for phrase in _CODEX_AUTH_PHRASES):
        return "auth_failure"
    if exit_code == 0 and text.strip():
        return "success"
    return "other_error"


# --- provenance: verified success contract + diagnostic-only drift hints ------
#
# ONLY the source-verified paths below may gate a successful review (codex
# rust-v0.144.1, `codex-rs/exec/src/exec_events.rs`): a session id from a
# `thread.started` event's `thread_id`, and a token pair from a `turn.completed`
# event's `usage.{input_tokens,output_tokens}`. Requiring both the event type
# and the exact field keeps a foreign/partial signal from being mistaken for
# provenance. Nothing is ever fabricated; a missing verified pair fails closed.
#
# The stream is UNVERSIONED, so if codex renames these we must NOT silently
# accept a guessed alias as success (that would persist an unverified review).
# Instead we fail closed loudly and record diagnostic hints — observed event
# types plus any conventional alias names seen — so a human can add the new
# names to the verified contract WITH fresh source evidence. Alias names never
# flip provenance_failure into success.
_VERIFIED_SESSION_EVENT = "thread.started"
_VERIFIED_SESSION_KEY = "thread_id"
_VERIFIED_USAGE_EVENT = "turn.completed"
_REQUIRED_USAGE_KEYS = ("input_tokens", "output_tokens")
# Verified optional fields on the codex usage struct — captured for telemetry
# when present, never required for validity.
_OPTIONAL_TOKEN_KEYS = ("cached_input_tokens", "reasoning_output_tokens")
# Diagnostic-only alias names (NOT accepted as provenance). Seeing one on a
# failed gate signals a likely schema rename worth investigating.
_DIAGNOSTIC_SESSION_KEYS = ("session_id", "threadId", "sessionId")
_DIAGNOSTIC_USAGE_KEYS = ("prompt_tokens", "completion_tokens")


def _nonneg_int(value: object) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _verified_session_id(event: dict, event_type: object) -> Optional[str]:
    """Session id from the verified `thread.started` + `thread_id` path only.

    Exact-key on the verified event type, so a collab field like
    `sender_thread_id` or an item/tool id is never mistaken for the session id.
    """
    if event_type != _VERIFIED_SESSION_EVENT:
        return None
    value = event.get(_VERIFIED_SESSION_KEY)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _verified_usage(event: dict, event_type: object) -> Optional[dict]:
    """Token pair from the verified `turn.completed` + `usage` path only.

    Requires a complete non-negative ``input_tokens``/``output_tokens`` pair;
    captures the verified optional cached/reasoning fields when present.
    """
    if event_type != _VERIFIED_USAGE_EVENT:
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = _nonneg_int(usage.get("input_tokens"))
    output_tokens = _nonneg_int(usage.get("output_tokens"))
    if input_tokens is None or output_tokens is None:
        return None
    normalized = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    for extra in _OPTIONAL_TOKEN_KEYS:
        value = _nonneg_int(usage.get(extra))
        if value is not None:
            normalized[extra] = value
    return normalized


def _collect_drift_hints(event: dict, event_type: object, hints: set) -> None:
    """Record conventional alias names for diagnosis only (never for success)."""
    label = event_type if isinstance(event_type, str) else "<untyped>"
    for key in _DIAGNOSTIC_SESSION_KEYS:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            hints.add(f"{label}:{key}")
    for container_key in ("usage", "token_usage"):
        usage = event.get(container_key)
        if isinstance(usage, dict):
            for key in _DIAGNOSTIC_USAGE_KEYS:
                if key in usage:
                    hints.add(f"{label}:{container_key}.{key}")


def _parse_codex_json_stream(stdout: str) -> dict:
    """Extract verified provenance from a `codex exec --json` event stream.

    Takes the first verified session id and the last verified usage pair (final
    usage is cumulative). Records ``observed_types`` and ``drift_hints`` for
    failure diagnosis only. Codex reports no USD cost. Unparseable lines skipped.
    """
    meta: dict = {}
    observed_types: list = []
    drift_hints: set = set()
    last_usage: Optional[dict] = None
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if isinstance(event_type, str):
            observed_types.append(event_type)
        if "session_id" not in meta:
            session_id = _verified_session_id(event, event_type)
            if session_id is not None:
                meta["session_id"] = session_id
        usage = _verified_usage(event, event_type)
        if usage is not None:
            last_usage = usage
        _collect_drift_hints(event, event_type, drift_hints)
    if last_usage is not None:
        meta["usage"] = last_usage
    meta["observed_types"] = observed_types
    meta["drift_hints"] = sorted(drift_hints)
    return meta


def _valid_codex_provenance(meta: dict) -> bool:
    session_id = meta.get("session_id")
    usage = meta.get("usage")
    return (
        isinstance(session_id, str)
        and bool(session_id.strip())
        and isinstance(usage, dict)
        and all(
            isinstance(usage.get(key), int)
            and not isinstance(usage.get(key), bool)
            and usage[key] >= 0
            for key in _REQUIRED_USAGE_KEYS
        )
    )


def run_codex_review(
    argv: list,
    last_message_path: str,
    runner: Callable = subprocess.run,
    env: Optional[dict] = None,
    timeout_seconds: float = 600,
    prompt: Optional[str] = None,
) -> ReviewResult:
    """Invoke `codex exec` with instructions on stdin; read the last message.

    Parses the `--json` stdout stream for session/thread id and token usage so
    the persisted review and cost log carry real provenance instead of
    `unknown`/fake-0 (P1-c). Codex reports no USD, so `total_cost_usd` is None.
    """
    try:
        completed = runner(
            argv,
            env=env,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ReviewResult(
            status="other_error",
            text=None,
            envelope={"error_type": type(exc).__name__, "total_cost_usd": None},
            exit_code=1,
        )
    exit_code = getattr(completed, "returncode", 1)
    stderr = getattr(completed, "stderr", "") or ""
    stdout = getattr(completed, "stdout", "") or ""
    try:
        with open(last_message_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = None
    meta = _parse_codex_json_stream(stdout)
    observed_types = meta.pop("observed_types", [])
    drift_hints = meta.pop("drift_hints", [])
    status = classify_codex(exit_code, text, stderr)
    if status == "success" and not _valid_codex_provenance(meta):
        status = "provenance_failure"
    effective_exit_code = exit_code if status == "success" or exit_code != 0 else 1
    if status == "provenance_failure":
        missing = []
        if not (isinstance(meta.get("session_id"), str) and meta["session_id"].strip()):
            missing.append("session_id")
        if not isinstance(meta.get("usage"), dict):
            missing.append("usage")
        # Event types and alias hints are non-sensitive labels; surfacing them
        # makes a codex schema drift diagnosable instead of a silent failure.
        seen = sorted(set(observed_types))[:20]
        hint = (
            f"; saw unverified alias fields {drift_hints} — codex may have "
            "renamed its schema, add them to the verified contract in "
            "claude_to_codex.py only with fresh source evidence"
            if drift_hints
            else ""
        )
        detail = (
            f"codex provenance incomplete: missing verified {missing}; "
            f"observed event types={seen or 'none'}{hint}"
        )
    else:
        detail = stderr[:200]
    envelope = {
        "detail": detail,
        "session_id": meta.get("session_id"),
        "usage": meta.get("usage"),
        "total_cost_usd": None,  # Codex reports token usage, not USD; never fake 0.
    }
    return ReviewResult(
        status=status,
        text=text if status == "success" else None,
        envelope=envelope,
        exit_code=effective_exit_code,
    )


def _create_last_message_file(marker_dir: str) -> str:
    fd, path = tempfile.mkstemp(prefix=".codex-last-", suffix=".txt", dir=marker_dir)
    os.close(fd)
    return path


def codex_review_gate(
    request_prompt: str,
    cd: str,
    handoff_dir: str,
    marker_path: str,
    gate_id: str,
    artifact_key: str,
    cost_log_path: str,
    output_path: Optional[str] = None,
    settings_path: str = DEFAULT_SETTINGS_PATH,
    runner: Callable = subprocess.run,
    timeout_seconds: float = 600,
    model: Optional[str] = None,
    model_help_runner: Optional[Callable] = None,
) -> ReviewResult:
    """End-to-end single reverse review gate (ClaudeCode primary -> Codex).

    Order: codex-available -> fixed caps -> reserve attempt -> invoke ->
    classify -> log cost -> commit success. A started call consumes an attempt
    even if it fails, preventing unbounded retries. The subprocess uses the
    same unattended full-access execution contract as the Claude direction.
    """
    sensitive_values = _known_sensitive_values(settings_path, None)
    try:
        requested_model = validate_requested_model(model)
    except ValueError as exc:
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "setup_failure",
            str(exc),
            request_prompt,
            sensitive_values,
        )

    if not codex_available():
        fail_closed(
            handoff_dir, gate_id, "codex_unavailable",
            "codex CLI not found on PATH", request_prompt, sensitive_values,
        )
        return ReviewResult("codex_unavailable", None, {}, exit_code=1)
    if requested_model is not None and model_help_runner is not None and (
        codex_supports_model(help_runner=model_help_runner) is False
    ):
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "setup_failure",
            f"local codex does not support {MODEL_FLAG}; upgrade the codex CLI",
            request_prompt,
            sensitive_values,
        )

    try:
        with round_cap_guard(marker_path, artifact_key) as decision:
            if not decision.allowed:
                failure_status = decision.reason or "round_cap_exceeded"
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    failure_status,
                    f"round check refused at {decision.current}; max {decision.max_rounds}",
                    request_prompt,
                    sensitive_values,
                )

            marker_dir = os.path.dirname(os.path.abspath(marker_path)) or "."
            os.makedirs(marker_dir, exist_ok=True)
            last_message_path = _create_last_message_file(marker_dir)
            log_error = None
            cleanup_error = None
            try:
                argv = build_codex_command(
                    cd=cd,
                    last_message_path=last_message_path,
                    model=requested_model,
                )
                attempt_decision = check_attempt_cap(marker_path, artifact_key)
                if not attempt_decision.allowed:
                    return gate_failure_result(
                        handoff_dir,
                        gate_id,
                        attempt_decision.reason or "attempt_cap_exceeded",
                        f"attempt check refused at {attempt_decision.current}; max {attempt_decision.max_rounds}",
                        request_prompt,
                        sensitive_values,
                    )
                attempt = _reserve_attempt_unlocked(marker_path, artifact_key)
                emit_review_started(
                    gate_id,
                    artifact_key,
                    attempt,
                    timeout_seconds,
                    sensitive_values,
                )
                start = time.monotonic()
                result = run_codex_review(
                    argv,
                    last_message_path,
                    runner=runner,
                    timeout_seconds=timeout_seconds,
                    prompt=build_reviewer_prompt(request_prompt),
                )
                usage = result.envelope.get("usage")
                try:
                    log_cost(
                        result.envelope,
                        cost_log_path,
                        gate_id,
                        time.monotonic() - start,
                        extra={
                            "provider": "codex",
                            "requested_model": requested_model,
                            **({"usage": usage} if usage is not None else {}),
                        },
                    )
                except (OSError, ValueError) as exc:
                    log_error = exc
            finally:
                try:
                    if os.path.exists(last_message_path):
                        os.unlink(last_message_path)
                except OSError as exc:
                    cleanup_error = exc

            if cleanup_error is not None:
                detail = f"{type(cleanup_error).__name__}: {cleanup_error}"
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    "cleanup_failure",
                    detail,
                    request_prompt,
                    sensitive_values,
                )
            if log_error is not None:
                detail = f"{type(log_error).__name__}: {log_error}"
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    "cost_log_failure",
                    detail,
                    request_prompt,
                    sensitive_values,
                    {"total_cost_usd": result.envelope.get("total_cost_usd")},
                )

            if result.status != "success":
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    result.status,
                    str(result.envelope.get("detail", "no result")),
                    request_prompt,
                    sensitive_values,
                    result.envelope,
                )

            if output_path:
                try:
                    persist_success(
                        output_path,
                        gate_id=gate_id,
                        result=result,
                        sensitive_values=sensitive_values,
                        reviewer="Codex",
                    )
                except (OSError, ValueError) as exc:
                    detail = f"{type(exc).__name__}: {exc}"
                    return gate_failure_result(
                        handoff_dir,
                        gate_id,
                        "persistence_failure",
                        detail,
                        request_prompt,
                        sensitive_values,
                        {"total_cost_usd": result.envelope.get("total_cost_usd")},
                    )
            try:
                _commit_round_unlocked(marker_path, artifact_key)
            except (OSError, ValueError) as exc:
                detail = f"{type(exc).__name__}: {exc}"
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    "round_state_failure",
                    detail,
                    request_prompt,
                    sensitive_values,
                    {"total_cost_usd": result.envelope.get("total_cost_usd")},
                )
            return result
    except (OSError, ValueError) as exc:
        detail = f"{type(exc).__name__}: {exc}"
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "setup_failure",
            detail,
            request_prompt,
            sensitive_values,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a fail-closed ClaudeCode->Codex review gate (direct codex CLI, no plugin)"
    )
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--cd", required=True, help="trusted repository/working dir Codex reviews")
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--marker-path", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--artifact-key", required=True)
    parser.add_argument("--cost-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--model")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    with open(args.request_file, encoding="utf-8") as fh:
        request_prompt = fh.read()
    result = codex_review_gate(
        request_prompt=request_prompt,
        cd=args.cd,
        handoff_dir=args.handoff_dir,
        marker_path=args.marker_path,
        gate_id=args.gate_id,
        artifact_key=args.artifact_key,
        cost_log_path=args.cost_log,
        output_path=args.output,
        settings_path=args.settings,
        timeout_seconds=args.timeout_seconds,
        model=args.model,
        model_help_runner=subprocess.run,
    )
    payload = {
        "status": result.status,
        "exit_code": result.exit_code,
        "session_id": result.envelope.get("session_id"),
        "output_path": args.output if result.status == "success" else None,
        "handoff_path": (
            None
            if result.status == "success"
            else os.path.join(args.handoff_dir, f"handoff-{_safe_gate_id(args.gate_id)}.md")
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
