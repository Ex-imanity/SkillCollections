"""ClaudeCode -> Codex direct review adapter.

Symmetric to `codex_to_claude.py`, but for the reverse direction: a
ClaudeCode-primary turn asks the local Codex CLI for a read-only review via
`codex exec --sandbox read-only`, WITHOUT depending on the official Codex
plugin. This keeps the skill self-contained and distributable (it needs only
the `claude` and `codex` CLIs), and sidesteps the plugin broker.

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
    fail_closed,
    gate_failure_result,
    log_cost,
    persist_success,
    round_cap_guard,
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


def build_codex_command(
    cd: str,
    last_message_path: str,
    output_schema: Optional[str] = None,
    skip_git_repo_check: bool = True,
) -> list:
    """Assemble a read-only `codex exec` argv.

    The sandbox is hardcoded to `read-only` and is NOT a caller-tunable
    parameter (P1-b): a reviewer must be physically unable to write, so there
    is no escape to `workspace-write`/`danger-full-access`. This mirrors the
    hardcoded `--permission-mode plan` on the claude side. Review instructions
    are passed via stdin, never argv.
    """
    argv = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--json",
        "--output-last-message",
        last_message_path,
        "-C",
        cd,
    ]
    if skip_git_repo_check:
        argv.append("--skip-git-repo-check")
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


def _parse_codex_json_stream(stdout: str) -> dict:
    """Extract provenance/usage from a `codex exec --json` event stream.

    Real schema (probed 2026-07-24): `thread.started` carries `thread_id`;
    `turn.completed` carries `usage` (token counts). Codex reports no USD cost.
    Best-effort and defensive: unparseable lines are skipped.
    """
    meta: dict = {}
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
        if event.get("type") == "thread.started" and event.get("thread_id"):
            meta["session_id"] = event["thread_id"]
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            meta["usage"] = event["usage"]
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
            for key in ("input_tokens", "output_tokens")
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
    status = classify_codex(exit_code, text, stderr)
    if status == "success" and not _valid_codex_provenance(meta):
        status = "provenance_failure"
    effective_exit_code = exit_code if status == "success" or exit_code != 0 else 1
    envelope = {
        "detail": (
            stderr[:200]
            if status != "provenance_failure"
            else "missing required thread.started.thread_id or turn.completed.usage"
        ),
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
) -> ReviewResult:
    """End-to-end single reverse review gate (ClaudeCode primary -> Codex).

    Order: codex-available -> fixed caps -> reserve attempt -> invoke ->
    classify -> log cost -> commit success. A started call consumes an attempt
    even if it fails, preventing unbounded retries. The sandbox is always
    read-only (P1-b).
    """
    sensitive_values = _known_sensitive_values(settings_path, None)

    if not codex_available():
        fail_closed(
            handoff_dir, gate_id, "codex_unavailable",
            "codex CLI not found on PATH", request_prompt, sensitive_values,
        )
        return ReviewResult("codex_unavailable", None, {}, exit_code=1)

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
                argv = build_codex_command(cd=cd, last_message_path=last_message_path)
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
                _reserve_attempt_unlocked(marker_path, artifact_key)
                start = time.monotonic()
                result = run_codex_review(
                    argv,
                    last_message_path,
                    runner=runner,
                    timeout_seconds=timeout_seconds,
                    prompt=request_prompt,
                )
                usage = result.envelope.get("usage")
                try:
                    log_cost(
                        result.envelope,
                        cost_log_path,
                        gate_id,
                        time.monotonic() - start,
                        extra=(
                            {"provider": "codex", "usage": usage}
                            if usage is not None
                            else {"provider": "codex"}
                        ),
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
    parser.add_argument("--cd", required=True, help="repository/working dir codex reviews (read-only)")
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--marker-path", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--artifact-key", required=True)
    parser.add_argument("--cost-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--timeout-seconds", type=float, default=600)
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
