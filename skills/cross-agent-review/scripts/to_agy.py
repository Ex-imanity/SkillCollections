"""Any-primary -> Antigravity (`agy`) review adapter.

Fail-closed bridge that asks the local Antigravity CLI (`agy`) for an unattended
full-access review via headless `stream-json` mode, WITHOUT depending on any
plugin or standalone `gemini` CLI.

Prompt text is sent on stdin as a single UTF-8 NDJSON `user` message (never
argv). `agy` assigns its own `conversation_id` UUID in the `init` stream event;
this adapter validates single-turn `stream-json` framing and provenance, logs
wall time and usage with `total_cost_usd: null`, and supports explicit timeout
continuation via `--conversation=<UUID>`.

Shared protocol helpers live in `common` and `continuation`. Pure stdlib
(Python 3.8+). The subprocess boundary is injectable (`runner`) so unit tests
never make real model calls.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

from .common import (
    DEFAULT_SETTINGS_PATH,
    MODEL_FLAG,
    ReviewResult,
    _known_sensitive_values,
    _redact_sensitive_text,
    build_reviewer_prompt,
    fail_closed as _fail_closed,
    gate_failure_result as _gate_failure_result,
    has_review_verdict,
    run_review_gate,
    validate_requested_model,
)

_REVIEWER_NAME = "Antigravity"
_ORIGINAL_SUBPROCESS_RUN = subprocess.run

_AGY_SENSITIVE_ENV_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_CLOUD_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "GROK_API_KEY",
)

# Specific CLI/API auth-error phrases checked strictly against `result.error`
# and `stderr` on non-success runs (never against normal review response text,
# and never bare "401"/"403"/"forbidden"/"authentication").
_AGY_AUTH_PHRASES = (
    "authentication required",
    "not authenticated",
    "not logged in",
    "unauthenticated",
    "invalid api key",
    "invalid_api_key",
    "api key not valid",
    "missing api key",
    "credentials required",
    "http 401",
    "http 403",
    "status 401",
    "status 403",
    "unauthorized",
)

_INCOMPLETE_STATUSES = frozenset({"CANCELED", "INTERRUPTED", "WAITING", "RUNNING"})
_REQUIRED_FLAGS = frozenset(
    {
        "--input-format",
        "--output-format",
        "--dangerously-skip-permissions",
        "--disable-slash-commands",
        "--conversation",
    }
)
_REQUIRED_USAGE_KEYS = ("input_tokens", "output_tokens")
_OPTIONAL_USAGE_KEYS = ("thinking_tokens", "cache_read_tokens", "total_tokens")
_DIAGNOSTIC_SESSION_KEYS = ("session_id", "sessionId", "thread_id", "threadId")
_DIAGNOSTIC_USAGE_KEYS = ("prompt_tokens", "completion_tokens")

_USAGE_HEADER_RE = re.compile(r"(?i)\bUsage(?:\s+of\s+agy)?\s*:")
_FLAG_TOKEN_RE = re.compile(r"(?<!\S)(--[a-z][a-z0-9-]*)(?=\s|=|,|$)")


def fail_closed(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _fail_closed(*args, **kwargs)


def gate_failure_result(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _gate_failure_result(*args, **kwargs)


def resolve_agy_executable() -> Optional[str]:
    """Resolve local `agy` once and return its absolute path, or None."""
    found = shutil.which("agy")
    if not found:
        return None
    return os.path.abspath(found)


def agy_available() -> bool:
    """True when the `agy` CLI is on PATH."""
    return resolve_agy_executable() is not None


def _flag_description_mentions(help_text: str, flag_name: str, needle: str) -> bool:
    lines = help_text.splitlines()
    flag_start_re = re.compile(rf"^\s*{re.escape(flag_name)}(?:\s|=|,|$)")
    next_flag_re = re.compile(r"^\s*-[A-Za-z0-9-]")
    for idx, line in enumerate(lines):
        if flag_start_re.match(line):
            block = [line]
            for follow in lines[idx + 1 :]:
                if not follow.strip() or next_flag_re.match(follow):
                    break
                block.append(follow)
            return needle in "\n".join(block)
    return False


def agy_supported_flags(
    executable: Optional[str] = None,
    help_runner: Callable = subprocess.run,
    timeout_seconds: float = 5,
    env: Optional[dict] = None,
) -> Optional[dict]:
    """Probe local `agy --help` for required flags and stream-json I/O support.

    Returns ``{"flags": set[str], "input_stream_json": bool, "output_stream_json": bool}``
    only on a conclusive exit-0 usage page; errors, non-zero exit, missing usage
    header, empty output, or timeouts return ``None`` (inconclusive).
    """
    exe = os.path.abspath(executable) if executable else resolve_agy_executable()
    if not exe:
        return None
    probe_kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": timeout_seconds,
    }
    if env is not None:
        probe_kwargs["env"] = env
    try:
        completed = help_runner([exe, "--help"], **probe_kwargs)
    except (OSError, subprocess.SubprocessError):
        return None
    if getattr(completed, "returncode", 1) != 0:
        return None
    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    text = (stdout + "\n" + stderr).strip()
    if not text or not _USAGE_HEADER_RE.search(text):
        return None
    flags = set(_FLAG_TOKEN_RE.findall(text))
    if not flags:
        return None
    return {
        "flags": flags,
        "input_stream_json": _flag_description_mentions(text, "--input-format", "stream-json"),
        "output_stream_json": _flag_description_mentions(text, "--output-format", "stream-json"),
    }


def _validate_uuid(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        UUID(text)
    except (ValueError, TypeError, AttributeError):
        return None
    return text


def build_agy_command(
    agy_executable: str = "agy",
    add_dirs: Optional[list] = None,
    model: Optional[str] = None,
    session_id: Optional[str] = None,
    resume: bool = False,
) -> list:
    """Assemble the unattended full-access `agy` stream-json argv.

    Prompt text is intentionally excluded from argv and sent on stdin via
    `encode_agy_prompt`. Never passes `--continue`, `-c`, `--print-timeout`,
    or reasoning/mode/sandbox overrides.
    """
    if not isinstance(agy_executable, str) or not agy_executable.strip():
        raise ValueError("agy_executable must be a non-empty path")
    argv = [
        agy_executable,
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--dangerously-skip-permissions",
        "--disable-slash-commands",
    ]
    for directory in add_dirs or []:
        if not isinstance(directory, str) or not directory.strip():
            raise ValueError("add_dirs entries must be non-empty paths")
        argv += ["--add-dir", directory]
    requested_model = validate_requested_model(model)
    if requested_model is not None:
        argv.append(f"--model={requested_model}")
    if resume:
        valid_id = _validate_uuid(session_id)
        if valid_id is None:
            raise ValueError("resume requires an exact recorded conversation UUID")
        argv.append(f"--conversation={valid_id}")
    elif session_id is not None:
        raise ValueError("fresh agy runs do not accept a caller-assigned session_id")
    return argv


def encode_agy_prompt(prompt: str) -> bytes:
    """Encode one `agy --input-format stream-json` user message as UTF-8 NDJSON."""
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    payload = {"event": "user", "message": {"content": prompt}}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _strict_nonneg_int(value: object) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _extract_usage(usage_obj: object) -> Optional[dict]:
    if not isinstance(usage_obj, dict):
        return None
    input_tokens = _strict_nonneg_int(usage_obj.get("input_tokens"))
    output_tokens = _strict_nonneg_int(usage_obj.get("output_tokens"))
    if input_tokens is None or output_tokens is None:
        return None
    normalized = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    for key in _OPTIONAL_USAGE_KEYS:
        val = _strict_nonneg_int(usage_obj.get(key))
        if val is not None:
            normalized[key] = val
    return normalized


def _collect_drift_hints(event: dict, label: str, hints: set) -> None:
    for key in _DIAGNOSTIC_SESSION_KEYS:
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            hints.add(f"{label}:{key}")
    for container_key in ("usage", "stats", "token_usage"):
        container = event.get(container_key)
        if isinstance(container, dict):
            for key in _DIAGNOSTIC_USAGE_KEYS:
                if key in container:
                    hints.add(f"{label}:{container_key}.{key}")


def _to_utf8_bytes(raw: object) -> bytes:
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        return raw.encode("utf-8", errors="replace")
    return b""


def parse_agy_stream(raw_stdout: Any, *, allow_trailing_truncation: bool = False) -> dict:
    """Parse `agy --output-format stream-json` using strict UTF-8 LF framing.

    Splits strictly on ``b"\\n"`` (never ``str.splitlines()``, which breaks JSON
    strings containing unescaped U+2028/U+2029). All field inspections are
    defensively type-checked so malformed payloads never raise TypeError.
    """
    raw_bytes = _to_utf8_bytes(raw_stdout)
    raw_lines = raw_bytes.split(b"\n")
    # Strip a single trailing empty element produced by a final LF.
    if raw_lines and raw_lines[-1] == b"":
        raw_lines = raw_lines[:-1]
    non_empty = [line[:-1] if line.endswith(b"\r") else line for line in raw_lines]
    indexed_lines = [(idx, line) for idx, line in enumerate(non_empty) if line.strip()]

    total_init_events = 0
    valid_init_ids: list = []
    init_index: Optional[int] = None
    total_result_events = 0
    results: list = []
    result_index: Optional[int] = None
    non_trailing_parse_errors = 0
    trailing_parse_error = False
    malformed_events = 0
    observed_events: list = []
    drift_hints: set = set()

    last_pos = len(indexed_lines) - 1
    for pos, (_orig_idx, line_bytes) in enumerate(indexed_lines):
        is_last = pos == last_pos
        try:
            text = line_bytes.decode("utf-8")
            obj = json.loads(text)
        except (UnicodeDecodeError, ValueError, TypeError):
            if allow_trailing_truncation and is_last:
                trailing_parse_error = True
            else:
                non_trailing_parse_errors += 1
            continue
        if not isinstance(obj, dict):
            malformed_events += 1
            continue

        ev_name = obj.get("event")
        alt_type = obj.get("type")
        if isinstance(ev_name, str) and ev_name:
            observed_events.append(ev_name)
            label = ev_name
        elif isinstance(alt_type, str) and alt_type:
            observed_events.append(f"type:{alt_type}")
            label = f"type:{alt_type}"
        else:
            label = "<untyped>"
        _collect_drift_hints(obj, label, drift_hints)

        if ev_name == "init":
            total_init_events += 1
            if init_index is None:
                init_index = pos
            conv_id = _validate_uuid(obj.get("conversation_id"))
            if conv_id is not None:
                valid_init_ids.append(conv_id)
            else:
                malformed_events += 1
        elif ev_name == "result":
            total_result_events += 1
            if result_index is None:
                result_index = pos
            payload = obj.get("result")
            if isinstance(payload, dict):
                _collect_drift_hints(payload, "result.payload", drift_hints)
                results.append(payload)
            else:
                malformed_events += 1

    return {
        "total_init_events": total_init_events,
        "valid_init_ids": valid_init_ids,
        "init_index": init_index,
        "total_result_events": total_result_events,
        "results": results,
        "result_index": result_index,
        "non_trailing_parse_errors": non_trailing_parse_errors,
        "trailing_parse_error": trailing_parse_error,
        "malformed_events": malformed_events,
        "observed_events": observed_events,
        "drift_hints": sorted(drift_hints),
    }


def _is_auth_failure_text(*parts: object) -> bool:
    blob = " ".join(p for p in parts if isinstance(p, str) and p).lower()
    if not blob:
        return False
    return any(phrase in blob for phrase in _AGY_AUTH_PHRASES)


def _classify_terminal_result_failure(
    result_payload: dict, stderr_text: str
) -> tuple:
    raw_status = result_payload.get("status")
    status_str = raw_status if isinstance(raw_status, str) else ""
    raw_error = result_payload.get("error")
    error_text = raw_error if isinstance(raw_error, str) else ""
    if _is_auth_failure_text(error_text, stderr_text):
        return "auth_failure", (error_text or stderr_text or "authentication failed")[:200]
    if status_str in _INCOMPLETE_STATUSES:
        return "completion_failure", (
            f"agy completion incomplete: status={status_str!r}"
            + (f" ({error_text[:160]})" if error_text else "")
        )
    detail = error_text or stderr_text or f"agy terminal status={status_str or '<missing>'!r}"
    return "other_error", detail[:200]


def _provenance_failure_detail(parsed: dict, reason: str) -> str:
    seen = sorted(set(parsed.get("observed_events") or []))[:20]
    hints = parsed.get("drift_hints") or []
    hint_text = f"; drift_hints={hints}" if hints else ""
    return f"agy provenance incomplete: {reason}; observed_events={seen or 'none'}{hint_text}"


def _default_agy_runner(
    argv: list,
    *,
    env: Optional[dict],
    input: bytes,
    capture_output: bool,
    text: bool,
    timeout: float,
    cwd: Optional[str],
):
    return subprocess.run(
        argv,
        env=env,
        input=input,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        **({"cwd": cwd} if cwd is not None else {}),
    )


def run_agy_review(
    argv: list,
    *,
    runner: Optional[Callable] = None,
    env: Optional[dict] = None,
    timeout_seconds: float = 600,
    prompt: Optional[str] = None,
    cwd: Optional[str] = None,
) -> ReviewResult:
    """Invoke `agy` stream-json headless mode and classify the result."""
    encoded_input = encode_agy_prompt(prompt or "")
    if runner is None:
        invoke_runner = (
            _default_agy_runner
            if subprocess.run is _ORIGINAL_SUBPROCESS_RUN
            else subprocess.run
        )
    else:
        invoke_runner = runner

    try:
        completed = invoke_runner(
            argv,
            env=env,
            input=encoded_input,
            capture_output=True,
            text=False,
            timeout=timeout_seconds,
            **({"cwd": cwd} if cwd is not None else {}),
        )
    except subprocess.TimeoutExpired as exc:
        partial_out = getattr(exc, "stdout", None)
        if partial_out is None:
            partial_out = getattr(exc, "output", b"")
        partial_err = _to_utf8_bytes(getattr(exc, "stderr", b"")).decode("utf-8", errors="replace")
        parsed = parse_agy_stream(partial_out, allow_trailing_truncation=True)
        # If any complete terminal result already arrived before timeout, never
        # reopen resumability; preserve explicit failure or fail closed.
        if parsed["total_result_events"] > 0:
            if parsed["results"]:
                last_res = parsed["results"][-1]
                res_status = last_res.get("status")
                if res_status == "SUCCESS":
                    return ReviewResult(
                        "other_error",
                        None,
                        {
                            "error_type": "TimeoutExpired",
                            "total_cost_usd": None,
                            "detail": "agy emitted a terminal result before timing out; process did not exit cleanly",
                        },
                        1,
                    )
                fail_status, fail_detail = _classify_terminal_result_failure(last_res, partial_err)
                return ReviewResult(
                    fail_status,
                    None,
                    {
                        "error_type": "TimeoutExpired",
                        "total_cost_usd": None,
                        "detail": fail_detail,
                    },
                    1,
                )
            return ReviewResult(
                "provenance_failure",
                None,
                {
                    "error_type": "TimeoutExpired",
                    "total_cost_usd": None,
                    "detail": _provenance_failure_detail(parsed, "malformed terminal result before timeout"),
                },
                1,
            )

        if (
            parsed["non_trailing_parse_errors"] > 0
            or parsed["malformed_events"] > 0
            or parsed["total_init_events"] > 1
        ):
            return ReviewResult(
                "provenance_failure",
                None,
                {
                    "error_type": "TimeoutExpired",
                    "total_cost_usd": None,
                    "detail": _provenance_failure_detail(
                        parsed, "invalid or duplicate init/stream lines before timeout"
                    ),
                },
                1,
            )

        observed_id = (
            parsed["valid_init_ids"][0]
            if parsed["total_init_events"] == 1 and len(parsed["valid_init_ids"]) == 1
            else None
        )
        return ReviewResult(
            "timeout",
            None,
            {
                "error_type": "TimeoutExpired",
                "session_id": observed_id,
                "observed_session_id": observed_id,
                "total_cost_usd": None,
                "detail": "review subprocess timed out; no completed review",
            },
            1,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ReviewResult(
            status="other_error",
            text=None,
            envelope={
                "error_type": type(exc).__name__,
                "detail": str(exc)[:200],
                "total_cost_usd": None,
            },
            exit_code=1,
        )

    exit_code = getattr(completed, "returncode", 1)
    raw_stdout = getattr(completed, "stdout", b"")
    stderr_text = _to_utf8_bytes(getattr(completed, "stderr", b"")).decode("utf-8", errors="replace")
    parsed = parse_agy_stream(raw_stdout, allow_trailing_truncation=False)

    last_result = parsed["results"][-1] if parsed["results"] else None
    result_status = last_result.get("status") if isinstance(last_result, dict) else None
    result_error = last_result.get("error") if isinstance(last_result, dict) else None

    # Auth failure check on non-success (inspecting error/stderr only).
    if exit_code != 0 or result_status != "SUCCESS":
        if _is_auth_failure_text(result_error, stderr_text):
            detail = (
                result_error
                if isinstance(result_error, str) and result_error.strip()
                else stderr_text.strip() or "authentication required"
            )
            return ReviewResult(
                "auth_failure",
                None,
                {"detail": detail[:200], "session_id": None, "total_cost_usd": None},
                exit_code if exit_code != 0 else 1,
            )

    # Terminal non-SUCCESS status from a parsed result payload.
    if isinstance(last_result, dict) and result_status != "SUCCESS":
        fail_status, fail_detail = _classify_terminal_result_failure(last_result, stderr_text)
        return ReviewResult(
            fail_status,
            None,
            {
                "detail": fail_detail,
                "session_id": _validate_uuid(last_result.get("conversation_id")),
                "status": result_status if isinstance(result_status, str) else None,
                "total_cost_usd": None,
            },
            exit_code if exit_code != 0 else 1,
        )

    if exit_code != 0:
        return ReviewResult(
            "other_error",
            None,
            {
                "detail": (stderr_text.strip() or f"agy exited with status {exit_code}")[:200],
                "session_id": None,
                "total_cost_usd": None,
            },
            exit_code,
        )

    # Strict single-turn framing & provenance checks on exit 0.
    if (
        parsed["non_trailing_parse_errors"] > 0
        or parsed["trailing_parse_error"]
        or parsed["malformed_events"] > 0
    ):
        return ReviewResult(
            "provenance_failure",
            None,
            {
                "detail": _provenance_failure_detail(parsed, "unparseable or malformed NDJSON event on exit 0"),
                "session_id": None,
                "total_cost_usd": None,
            },
            1,
        )

    if (
        parsed["total_init_events"] != 1
        or len(parsed["valid_init_ids"]) != 1
        or parsed["total_result_events"] != 1
        or len(parsed["results"]) != 1
        or parsed["init_index"] is None
        or parsed["result_index"] is None
        or parsed["init_index"] >= parsed["result_index"]
    ):
        return ReviewResult(
            "provenance_failure",
            None,
            {
                "detail": _provenance_failure_detail(
                    parsed, "expected single init event before single result event"
                ),
                "session_id": None,
                "total_cost_usd": None,
            },
            1,
        )

    init_id = parsed["valid_init_ids"][0]
    result_payload = parsed["results"][0]
    result_id = _validate_uuid(result_payload.get("conversation_id"))
    if result_id is None or result_id != init_id:
        return ReviewResult(
            "provenance_failure",
            None,
            {
                "detail": _provenance_failure_detail(parsed, "init/result conversation_id missing or mismatched"),
                "session_id": None,
                "total_cost_usd": None,
            },
            1,
        )

    usage = _extract_usage(result_payload.get("usage"))
    if usage is None:
        return ReviewResult(
            "provenance_failure",
            None,
            {
                "detail": _provenance_failure_detail(parsed, "missing strict non-negative usage input_tokens/output_tokens"),
                "session_id": init_id,
                "total_cost_usd": None,
            },
            1,
        )

    response_text = result_payload.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        return ReviewResult(
            "other_error",
            None,
            {
                "detail": "agy returned an empty response",
                "session_id": init_id,
                "usage": usage,
                "total_cost_usd": None,
            },
            1,
        )
    if not has_review_verdict(response_text):
        return ReviewResult(
            "other_error",
            None,
            {
                "detail": "agy response lacked a standard review verdict",
                "session_id": init_id,
                "usage": usage,
                "total_cost_usd": None,
            },
            1,
        )

    num_turns = _strict_nonneg_int(result_payload.get("num_turns"))
    return ReviewResult(
        status="success",
        text=response_text,
        envelope={
            "detail": "",
            "session_id": init_id,
            "observed_session_id": init_id,
            "usage": usage,
            "total_cost_usd": None,  # agy reports token usage, not USD; never fake 0.
            "num_turns": num_turns,
            "status": "SUCCESS",
        },
        exit_code=0,
    )


def _agy_sensitive_values(settings_path: str, explicit_env: Optional[dict]) -> list:
    values = list(_known_sensitive_values(settings_path, explicit_env))
    for source in (os.environ, explicit_env or {}):
        for key in _AGY_SENSITIVE_ENV_KEYS:
            val = source.get(key) if hasattr(source, "get") else None
            if isinstance(val, str) and val and val not in values:
                values.append(val)
    return values


def _canonicalize_directories(cd: str, add_dirs: Optional[list]) -> tuple:
    if not isinstance(cd, str) or not cd.strip() or not os.path.isdir(cd):
        raise ValueError("cd must reference an existing working directory")
    working_dir = os.path.realpath(cd)
    resolved_set: set = set()
    for entry in add_dirs or []:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError("add_dir must be a non-empty existing directory")
        candidate = entry if os.path.isabs(entry) else os.path.join(working_dir, entry)
        if not os.path.isdir(candidate):
            raise ValueError(f"add_dir must reference an existing directory: {entry}")
        resolved_set.add(os.path.realpath(candidate))
    return working_dir, sorted(resolved_set)


def agy_review_gate(
    request_prompt: str,
    cd: str,
    handoff_dir: str,
    marker_path: str,
    gate_id: str,
    artifact_key: str,
    cost_log_path: str,
    output_path: Optional[str] = None,
    add_dirs: Optional[list] = None,
    settings_path: str = DEFAULT_SETTINGS_PATH,
    runner: Optional[Callable] = None,
    timeout_seconds: float = 600,
    model: Optional[str] = None,
    help_runner: Optional[Callable] = None,
    explicit_env: Optional[dict] = None,
    resume: bool = False,
    artifact_paths: Optional[list] = None,
    agy_home: Optional[str] = None,
) -> ReviewResult:
    """End-to-end single Antigravity reviewer gate (any primary -> Antigravity)."""
    sensitive_values = _agy_sensitive_values(settings_path, explicit_env)
    try:
        requested_model = validate_requested_model(model)
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        working_dir, resolved_add_dirs = _canonicalize_directories(cd, add_dirs)
    except ValueError as exc:
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "setup_failure",
            str(exc),
            request_prompt,
            sensitive_values,
            resumable=False,
        )

    agy_executable = resolve_agy_executable()
    if agy_executable is None:
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "agy_unavailable",
            "agy CLI not found on PATH",
            request_prompt,
            sensitive_values,
            resumable=False,
        )

    if help_runner is not None:
        probed = agy_supported_flags(executable=agy_executable, help_runner=help_runner)
        if probed is not None:
            missing_flags = sorted(_REQUIRED_FLAGS - probed["flags"])
            if requested_model is not None and MODEL_FLAG not in probed["flags"]:
                missing_flags.append(MODEL_FLAG)
            if resolved_add_dirs and "--add-dir" not in probed["flags"]:
                missing_flags.append("--add-dir")
            if missing_flags:
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    "setup_failure",
                    f"local agy does not support required flags {missing_flags}; upgrade the agy CLI",
                    request_prompt,
                    sensitive_values,
                    resumable=False,
                )
            if not probed["input_stream_json"] or not probed["output_stream_json"]:
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    "setup_failure",
                    "local agy must support stream-json for both --input-format and --output-format; upgrade the agy CLI",
                    request_prompt,
                    sensitive_values,
                    resumable=False,
                )

    def prepare(_marker_dir: str) -> dict:
        prompt = request_prompt
        if resume:
            prompt = (
                "Continue the SAME unfinished review in this original session. "
                "Reuse your inspection progress and findings, check any remaining evidence, "
                "and finish with the self-contained verdict. This is a timeout continuation; "
                "the original scope and reviewed files are unchanged. Do not start a new review "
                "or modify primary-owned files.\n\nOriginal request (unchanged):\n\n" + prompt
            )
        argv = build_agy_command(
            agy_executable=agy_executable,
            add_dirs=resolved_add_dirs,
            model=requested_model,
            session_id=None,
            resume=resume,
        )
        child_env = dict(os.environ)
        if explicit_env:
            for key, value in explicit_env.items():
                if value is not None:
                    child_env[key] = value
        return {
            "argv": argv,
            "env": child_env,
            "prompt": build_reviewer_prompt(prompt),
        }

    def invoke(state: object) -> ReviewResult:
        payload = state if isinstance(state, dict) else {}
        return run_agy_review(
            list(payload.get("argv") or []),
            runner=runner,
            env=payload.get("env"),
            timeout_seconds=timeout_seconds,
            prompt=payload.get("prompt"),
            cwd=working_dir,
        )

    return run_review_gate(
        request_prompt=request_prompt,
        handoff_dir=handoff_dir,
        marker_path=marker_path,
        gate_id=gate_id,
        artifact_key=artifact_key,
        cost_log_path=cost_log_path,
        sensitive_values=sensitive_values,
        reviewer=_REVIEWER_NAME,
        invoke=invoke,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
        requested_model=requested_model,
        provider="agy",
        prepare=prepare,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a fail-closed any-primary -> Antigravity (`agy`) review gate"
    )
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--cd", required=True, help="trusted repository/working dir Antigravity reviews")
    parser.add_argument("--add-dir", action="append", default=[], help="additional workspace directory (repeatable)")
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--marker-path", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--artifact-key", required=True)
    parser.add_argument("--cost-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--model")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue this gate's recorded timeout in its original conversation; requires --artifact-path",
    )
    parser.add_argument(
        "--artifact-path",
        action="append",
        default=[],
        dest="artifact_paths",
        help="File under review, relative to --cd; required for Antigravity timeout continuation (repeatable)",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    with open(args.request_file, encoding="utf-8") as fh:
        request_prompt = fh.read()
    sensitive_values = _agy_sensitive_values(args.settings, None)
    result = agy_review_gate(
        request_prompt=request_prompt,
        cd=args.cd,
        add_dirs=args.add_dir,
        handoff_dir=args.handoff_dir,
        marker_path=args.marker_path,
        gate_id=args.gate_id,
        artifact_key=args.artifact_key,
        cost_log_path=args.cost_log,
        output_path=args.output,
        settings_path=args.settings,
        timeout_seconds=args.timeout_seconds,
        model=args.model,
        help_runner=subprocess.run,
        resume=args.resume,
        artifact_paths=args.artifact_paths,
    )
    raw_session_id = result.envelope.get("session_id")
    safe_session_id = _validate_uuid(raw_session_id)
    raw_handoff = result.envelope.get("handoff_path")
    safe_handoff = (
        None
        if result.status == "success" or not isinstance(raw_handoff, str)
        else _redact_sensitive_text(raw_handoff, sensitive_values)
    )
    raw_cont_path = result.envelope.get("continuation_state_path")
    safe_cont_path = (
        _redact_sensitive_text(raw_cont_path, sensitive_values)
        if isinstance(raw_cont_path, str)
        else None
    )
    safe_output = (
        _redact_sensitive_text(args.output, sensitive_values)
        if result.status == "success"
        else None
    )
    payload = {
        "status": result.status,
        "exit_code": result.exit_code,
        "session_id": safe_session_id,
        "resumable": bool(result.envelope.get("resumable", False)),
        "continuation_state_path": safe_cont_path,
        "attempt": result.envelope.get("attempt"),
        "continuation": result.envelope.get("continuation"),
        "output_path": safe_output,
        "handoff_path": safe_handoff,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
