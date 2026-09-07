"""Any-primary -> Grok review adapter.

Symmetric to `to_codex.py` for the third local peer: a primary agent
(Codex, ClaudeCode, or another Grok session) asks the local `grok` CLI for an
unattended full-access review via headless mode.

Grok headless does not read the review prompt from stdin. The adapter writes a
temporary prompt file and passes it with `--prompt-file`, then classifies the
single JSON result object (`text`, `sessionId`, optional spend fields).

Shared guards (round cap, redaction, fail-closed, cost log, completion
contract) are imported from `common` so every direction enforces the
same protocol.

Pure stdlib. The subprocess boundary is injectable (`runner`) so unit tests
never make real Grok calls.
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

from .common import (
    MODEL_FLAG,
    ReviewResult,
    _commit_round_unlocked,
    _known_sensitive_values,
    _reserve_attempt_unlocked,
    _safe_gate_id,
    build_reviewer_prompt,
    check_attempt_cap,
    emit_review_started,
    fail_closed as _fail_closed,
    gate_failure_result as _gate_failure_result,
    has_review_verdict,
    log_cost,
    persist_success,
    round_cap_guard,
    validate_requested_model,
)

_REVIEWER_NAME = "Grok"


def fail_closed(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _fail_closed(*args, **kwargs)


def gate_failure_result(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _gate_failure_result(*args, **kwargs)

DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
# Auth-failure signatures in grok stderr / error envelopes. Specific phrases only.
_GROK_AUTH_PHRASES = (
    "not logged in",
    "unauthorized",
    "forbidden",
    "authentication",
    "authenticate",
    "auth required",
    "invalid api key",
    "invalid_api_key",
    "missing api key",
    "401",
    "403",
)
_GROK_SENSITIVE_ENV_KEYS = (
    "XAI_API_KEY",
    "GROK_API_KEY",
    "OPENAI_API_KEY",
)


def grok_available() -> bool:
    """True when the `grok` CLI is on PATH. Portability precheck."""
    return shutil.which("grok") is not None


def grok_supports_model(
    executable: Optional[str] = None,
    help_runner: Callable = subprocess.run,
    timeout_seconds: float = 5,
) -> Optional[bool]:
    """Best-effort check that local `grok` accepts the model flag."""
    exe = executable or shutil.which("grok")
    if not exe:
        return None
    try:
        completed = help_runner(
            [exe, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (getattr(completed, "stdout", "") or "") + (getattr(completed, "stderr", "") or "")
    return None if not text.strip() else MODEL_FLAG in text


def build_grok_command(
    prompt_file: str,
    cwd: str,
    model: Optional[str] = None,
    grok_executable: str = "grok",
) -> list:
    """Assemble an unattended full-access headless `grok` argv.

    Headless mode is triggered by ``--prompt-file`` (Grok does not consume the
    review prompt from stdin). ``--always-approve`` mirrors the other adapters'
    non-interactive full tool permission so verification commands and requested
    review-artifact writes cannot stall. The review prompt still forbids
    modifying the reviewed artifact or primary-owned state.
    """
    if not isinstance(prompt_file, str) or not prompt_file.strip():
        raise ValueError("prompt_file must be a non-empty path")
    if not isinstance(cwd, str) or not cwd.strip():
        raise ValueError("cwd must be a non-empty path")
    argv = [
        grok_executable,
        "--prompt-file",
        prompt_file,
        "--output-format",
        "json",
        "--always-approve",
        "--cwd",
        cwd,
    ]
    requested_model = validate_requested_model(model)
    if requested_model is not None:
        # One native token keeps flag parsing unambiguous across clap-style CLIs.
        argv.append(f"--model={requested_model}")
    return argv


def _envelope_text(envelope: dict) -> Optional[str]:
    text = envelope.get("text")
    if isinstance(text, str):
        return text
    # Defensive: tolerate a Claude-shaped `result` if a proxy rewrites output.
    result = envelope.get("result")
    return result if isinstance(result, str) else None


def _envelope_session_id(envelope: dict) -> Optional[str]:
    for key in ("sessionId", "session_id"):
        value = envelope.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _envelope_usage(envelope: dict) -> Optional[dict]:
    usage = envelope.get("usage")
    if not isinstance(usage, dict):
        return None
    normalized: dict = {}
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
        "reasoning_tokens",
        "total_tokens",
    ):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            normalized[key] = value
    return normalized or None


def _auth_failure_text(*parts: str) -> bool:
    blob = " ".join(part or "" for part in parts).lower()
    return any(phrase in blob for phrase in _GROK_AUTH_PHRASES)


def classify_grok(exit_code: int, envelope: dict, stderr: str = "") -> str:
    """Classify a headless grok JSON result: success | auth_failure | other_error.

    Readiness is judged on the real envelope, never on an auth-status command.
    A success classification still requires provenance + stopReason checks in
    ``run_grok_review`` before the gate treats the review as verified.
    """
    if not isinstance(envelope, dict):
        return "other_error"
    message = envelope.get("message") if isinstance(envelope.get("message"), str) else ""
    detail = envelope.get("detail") if isinstance(envelope.get("detail"), str) else ""
    text = _envelope_text(envelope) or ""
    if envelope.get("type") == "error" or exit_code != 0:
        if _auth_failure_text(message, detail, text, stderr):
            return "auth_failure"
        return "other_error"
    if exit_code == 0 and text.strip():
        return "success"
    return "other_error"


def _envelope_stop_reason(envelope: dict) -> Optional[str]:
    for key in ("stopReason", "stop_reason"):
        value = envelope.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _valid_grok_provenance(envelope: dict) -> bool:
    """Require a real session id on success; cost may be null when withheld."""
    return _envelope_session_id(envelope) is not None


def _valid_grok_completion(envelope: dict) -> bool:
    """Require a complete-turn signal so truncated reviews cannot pass.

    Live headless Grok reports ``stopReason: "end_turn"`` on a finished
    successful turn. Other values (or absence) fail closed.
    """
    return _envelope_stop_reason(envelope) == "end_turn"


def _parse_json_object(stdout: str) -> dict:
    """Parse the first JSON object from stdout (tolerate leading banners)."""
    text = stdout or ""
    start = text.find("{")
    if start < 0:
        raise ValueError("no json object in stdout")
    obj, _end = json.JSONDecoder().raw_decode(text, start)
    if not isinstance(obj, dict):
        raise ValueError("envelope is not an object")
    return obj


def _normalize_total_cost(raw_cost: object) -> Optional[float]:
    """Record provider cost only when it is a real finite number; never fake 0."""
    if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)):
        return None
    value = float(raw_cost)
    if value != value or value in (float("inf"), float("-inf")):  # NaN/Inf
        return None
    return value


def run_grok_review(
    argv: list,
    runner: Callable = subprocess.run,
    env: Optional[dict] = None,
    timeout_seconds: float = 600,
) -> ReviewResult:
    """Invoke headless `grok` and classify the single JSON result object."""
    try:
        completed = runner(
            argv,
            env=env,
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
        envelope = _parse_json_object(stdout)
    except (ValueError, TypeError):
        return ReviewResult(
            status="other_error",
            text=None,
            envelope={"detail": "invalid_json_envelope", "total_cost_usd": None},
            exit_code=exit_code or 1,
        )

    status = classify_grok(exit_code, envelope, stderr)
    text = _envelope_text(envelope)
    stop_reason = _envelope_stop_reason(envelope)
    if status == "success" and not has_review_verdict(text):
        status = "other_error"
    if status == "success" and not _valid_grok_provenance(envelope):
        status = "provenance_failure"
    if status == "success" and not _valid_grok_completion(envelope):
        status = "completion_failure"

    session_id = _envelope_session_id(envelope)
    usage = _envelope_usage(envelope)
    total_cost = _normalize_total_cost(envelope.get("total_cost_usd"))

    if status == "provenance_failure":
        detail = "grok provenance incomplete: missing verified sessionId"
    elif status == "completion_failure":
        observed = stop_reason if stop_reason is not None else "<missing>"
        detail = f"grok completion incomplete: stopReason must be end_turn, got {observed!r}"
    elif status == "success":
        detail = ""
    else:
        detail = message_from_failure(envelope, stderr)

    normalized = {
        "detail": detail,
        "session_id": session_id,
        "usage": usage,
        "total_cost_usd": total_cost,
        "text": text,
        "stopReason": stop_reason,
        "num_turns": envelope.get("num_turns"),
    }
    effective_exit_code = exit_code if status == "success" or exit_code != 0 else 1
    return ReviewResult(
        status=status,
        text=text if status == "success" else None,
        envelope=normalized,
        exit_code=effective_exit_code,
    )


def message_from_failure(envelope: dict, stderr: str = "") -> str:
    for key in ("message", "detail", "text", "result"):
        value = envelope.get(key)
        if isinstance(value, str) and value.strip():
            return value[:200]
    err = (stderr or "").strip()
    return err[:200] if err else "no result"


def _create_prompt_file(marker_dir: str, prompt: str) -> str:
    fd, path = tempfile.mkstemp(prefix=".grok-prompt-", suffix=".txt", dir=marker_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(prompt)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _grok_sensitive_values(settings_path: str, explicit_env: Optional[dict]) -> list:
    """Known secrets for redaction: Claude proxy values plus Grok API key envs."""
    values = list(_known_sensitive_values(settings_path, explicit_env))
    sources = [os.environ, explicit_env or {}]
    for source in sources:
        for key in _GROK_SENSITIVE_ENV_KEYS:
            value = source.get(key) if hasattr(source, "get") else None
            if isinstance(value, str) and value and value not in values:
                values.append(value)
    return values


def grok_review_gate(
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
    explicit_env: Optional[dict] = None,
) -> ReviewResult:
    """End-to-end single Grok reviewer gate (any primary -> Grok).

    Order: grok-available -> fixed caps -> reserve attempt -> invoke ->
    classify -> log cost -> commit success. A started call consumes an attempt
    even if it fails. Grok has no provider USD cap on this route; require
    explicit user approval plus the fixed attempt cap and timeout.
    """
    sensitive_values = _grok_sensitive_values(settings_path, explicit_env)
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

    if not grok_available():
        fail_closed(
            handoff_dir,
            gate_id,
            "grok_unavailable",
            "grok CLI not found on PATH",
            request_prompt,
            sensitive_values,
        )
        return ReviewResult("grok_unavailable", None, {}, exit_code=1)
    if requested_model is not None and model_help_runner is not None and (
        grok_supports_model(help_runner=model_help_runner) is False
    ):
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "setup_failure",
            f"local grok does not support {MODEL_FLAG}; upgrade the grok CLI",
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
            prompt_path = None
            log_error = None
            cleanup_error = None
            try:
                prompt_path = _create_prompt_file(
                    marker_dir, build_reviewer_prompt(request_prompt)
                )
                argv = build_grok_command(
                    prompt_file=prompt_path,
                    cwd=cd,
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
                child_env = dict(os.environ)
                if explicit_env:
                    for key, value in explicit_env.items():
                        if value is not None:
                            child_env[key] = value
                result = run_grok_review(
                    argv,
                    runner=runner,
                    env=child_env,
                    timeout_seconds=timeout_seconds,
                )
                usage = result.envelope.get("usage")
                try:
                    log_cost(
                        result.envelope,
                        cost_log_path,
                        gate_id,
                        time.monotonic() - start,
                        extra={
                            "provider": "grok",
                            "requested_model": requested_model,
                            **({"usage": usage} if usage is not None else {}),
                        },
                    )
                except (OSError, ValueError) as exc:
                    log_error = exc
            finally:
                if prompt_path is not None:
                    try:
                        if os.path.exists(prompt_path):
                            os.unlink(prompt_path)
                    except OSError as exc:
                        cleanup_error = exc

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
                # Temp-file cleanup failure is secondary once the review already failed.
                if cleanup_error is not None:
                    result.envelope["cleanup_warning"] = (
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    result.status,
                    str(result.envelope.get("detail", "no result")),
                    request_prompt,
                    sensitive_values,
                    result.envelope,
                )

            # A verified paid review must not be discarded solely because the
            # temporary prompt file could not be unlinked.
            if cleanup_error is not None:
                result.envelope["cleanup_warning"] = (
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )

            if output_path:
                try:
                    persist_success(
                        output_path,
                        gate_id=gate_id,
                        result=result,
                        sensitive_values=sensitive_values,
                        reviewer=_REVIEWER_NAME,
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
        description=(
            "Run a fail-closed any-primary->Grok review gate "
            "(headless grok --prompt-file, no plugin dependency)"
        )
    )
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--cd", required=True, help="trusted repository/working dir Grok reviews")
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
    result = grok_review_gate(
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
