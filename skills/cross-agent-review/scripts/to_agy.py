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
import errno
import json
import math
import os
import re
import selectors
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

from .continuation import ReviewContinuation

from .common import (
    DEFAULT_SETTINGS_PATH,
    MODEL_FLAG,
    ReviewResult,
    _known_sensitive_values,
    _redact_sensitive_text,
    build_reviewer_prompt,
    gate_failure_result as _gate_failure_result,
    has_review_verdict,
    run_review_gate,
    validate_requested_model,
)

_REVIEWER_NAME = "Antigravity"
POST_EXIT_DRAIN_SECONDS = 5.0
CLEANUP_TIMEOUT_SECONDS = 5.0

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
_OPTIONAL_USAGE_KEYS = ("thinking_tokens", "cache_read_tokens", "total_tokens")
_DIAGNOSTIC_SESSION_KEYS = ("session_id", "sessionId", "thread_id", "threadId")
_DIAGNOSTIC_USAGE_KEYS = ("prompt_tokens", "completion_tokens")

_USAGE_HEADER_RE = re.compile(r"(?i)\bUsage(?:\s+of\s+agy)?\s*:")
_FLAG_TOKEN_RE = re.compile(r"(?<!\S)(--[a-z][a-z0-9-]*)(?=\s|=|,|$)")


def gate_failure_result(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _gate_failure_result(*args, **kwargs)


def resolve_agy_executable() -> Optional[str]:
    """Resolve local `agy` once and return its absolute path, or None."""
    found = shutil.which("agy")
    if not found:
        return None
    return os.path.abspath(found)


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


def _run_agy_help_probe(
    argv: list,
    *,
    capture_output: bool = True,
    text: bool = False,
    timeout: float = 5,
    env: Optional[dict] = None,
):
    """Run `agy --help` via the strictly bounded subprocess runner."""
    return _run_agy_subprocess(
        argv,
        env=env,
        input=b"",
        capture_output=capture_output,
        text=text,
        timeout=timeout,
    )


def agy_supported_flags(
    executable: Optional[str] = None,
    help_runner: Optional[Callable] = None,
    timeout_seconds: float = 5,
    env: Optional[dict] = None,
) -> Optional[dict]:
    """Probe local `agy --help` for required flags and stream-json I/O support.

    Returns ``{"flags": set[str], "input_stream_json": bool, "output_stream_json": bool}``
    only on a conclusive exit-0 usage page; errors, non-zero exit, undecodable
    UTF-8 bytes, missing usage header, empty output, or timeouts return
    ``None`` (inconclusive).
    """
    exe = os.path.abspath(executable) if executable else resolve_agy_executable()
    if not exe:
        return None
    probe_runner = _run_agy_help_probe if help_runner is None else help_runner
    probe_kwargs: dict = {
        "capture_output": True,
        "text": False,
        "timeout": timeout_seconds,
    }
    if env is not None:
        probe_kwargs["env"] = env
    try:
        completed = probe_runner([exe, "--help"], **probe_kwargs)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    if getattr(completed, "returncode", 1) != 0:
        return None
    raw_stdout = getattr(completed, "stdout", b"") or b""
    raw_stderr = getattr(completed, "stderr", b"") or b""
    try:
        stdout = raw_stdout.decode("utf-8") if isinstance(raw_stdout, bytes) else str(raw_stdout)
        stderr = raw_stderr.decode("utf-8") if isinstance(raw_stderr, bytes) else str(raw_stderr)
    except UnicodeDecodeError:
        return None
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
    strings containing unescaped U+2028/U+2029) and preserves LF termination per
    segment. Only an unterminated trailing line may be tolerated on timeout.
    All field inspections are defensively type-checked and RecursionError-safe.
    """
    raw_bytes = _to_utf8_bytes(raw_stdout)
    segments: list = []
    pos = 0
    total_len = len(raw_bytes)
    while pos < total_len:
        nl = raw_bytes.find(b"\n", pos)
        if nl == -1:
            seg = raw_bytes[pos:]
            terminated = False
            pos = total_len
        else:
            seg = raw_bytes[pos:nl]
            terminated = True
            pos = nl + 1
        if seg.endswith(b"\r"):
            seg = seg[:-1]
        if seg.strip():
            segments.append((seg, terminated))

    total_init_events = 0
    valid_init_ids: list = []
    init_index: Optional[int] = None
    total_result_events = 0
    results: list = []
    result_index: Optional[int] = None
    unterminated_result_event = False
    unterminated_results: list = []
    non_trailing_parse_errors = 0
    trailing_parse_error = False
    malformed_events = 0
    observed_events: list = []
    drift_hints: set = set()

    last_pos = len(segments) - 1
    for idx, (line_bytes, terminated) in enumerate(segments):
        is_last = idx == last_pos
        try:
            text = line_bytes.decode("utf-8")
            obj = json.loads(text)
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
            if allow_trailing_truncation and is_last and not terminated:
                trailing_parse_error = True
            else:
                non_trailing_parse_errors += 1
            continue
        if not terminated:
            # Strict LF framing: never accept an unterminated trailing line as a
            # complete NDJSON record on normal exit or as a resumable init on timeout.
            # On timeout, explicitly flag decodable terminal `result` records so they
            # are never silently dropped to grant resumability.
            if allow_trailing_truncation and is_last:
                if isinstance(obj, dict) and obj.get("event") == "result":
                    unterminated_result_event = True
                    payload = obj.get("result")
                    if isinstance(payload, dict):
                        unterminated_results.append(payload)
                else:
                    trailing_parse_error = True
            else:
                trailing_parse_error = True
            continue
        if not isinstance(obj, dict):
            malformed_events += 1
            continue

        ev_name = obj.get("event")
        alt_type = obj.get("type")
        if isinstance(ev_name, str) and ev_name:
            observed_events.append(ev_name)
            label = ev_name
        else:
            malformed_events += 1
            if isinstance(alt_type, str) and alt_type:
                observed_events.append(f"type:{alt_type}")
                label = f"type:{alt_type}"
            else:
                label = "<untyped>"
        _collect_drift_hints(obj, label, drift_hints)

        if ev_name == "init":
            total_init_events += 1
            if init_index is None:
                init_index = idx
            conv_id = _validate_uuid(obj.get("conversation_id"))
            if conv_id is not None:
                valid_init_ids.append(conv_id)
            else:
                malformed_events += 1
        elif ev_name == "result":
            total_result_events += 1
            if result_index is None:
                result_index = idx
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
        "unterminated_result_event": unterminated_result_event,
        "unterminated_results": unterminated_results,
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


def _redact_and_truncate(
    text: str, sensitive_values: Optional[list] = None, limit: int = 200
) -> str:
    return _redact_sensitive_text(text, sensitive_values)[:limit]


def _is_sensitive_id(session_id: Optional[str], sensitive_values: Optional[list]) -> bool:
    if session_id is None:
        return False
    return _redact_sensitive_text(session_id, sensitive_values) != session_id


def _safe_stdout_path(path: object, sensitive_values: Optional[list]) -> Optional[str]:
    if not isinstance(path, str) or not path:
        return None
    if _redact_sensitive_text(path, sensitive_values) != path:
        return None
    return path


def _classify_terminal_result_failure(
    result_payload: dict,
    stderr_text: str,
    sensitive_values: Optional[list] = None,
) -> tuple:
    raw_status = result_payload.get("status")
    status_str = raw_status if isinstance(raw_status, str) else ""
    raw_error = result_payload.get("error")
    error_text = raw_error if isinstance(raw_error, str) else ""
    if _is_auth_failure_text(error_text, stderr_text):
        raw_detail = error_text or stderr_text or "authentication failed"
        return "auth_failure", _redact_and_truncate(raw_detail, sensitive_values, 200)
    if status_str in _INCOMPLETE_STATUSES:
        safe_err = _redact_and_truncate(error_text, sensitive_values, 160) if error_text else ""
        return "completion_failure", (
            f"agy completion incomplete: status={status_str!r}"
            + (f" ({safe_err})" if safe_err else "")
        )
    detail = error_text or stderr_text or f"agy terminal status={status_str or '<missing>'!r}"
    return "other_error", _redact_and_truncate(detail, sensitive_values, 200)


def _provenance_failure_detail(parsed: dict, reason: str) -> str:
    seen = sorted(set(parsed.get("observed_events") or []))[:20]
    hints = parsed.get("drift_hints") or []
    hint_text = f"; drift_hints={hints}" if hints else ""
    return f"agy provenance incomplete: {reason}; observed_events={seen or 'none'}{hint_text}"


class _AgyContinuation(ReviewContinuation):
    """Capture CLI-issued conversation UUID and require resumed-segment receipt."""

    def __init__(self, *args, sensitive_values: Optional[list] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sensitive_values = list(sensitive_values) if sensitive_values else None

    def check(
        self,
        *,
        marker_path: str,
        gate_id: str,
        artifact_key: str,
        request_prompt: str,
        reviewer: str,
        requested_model: Optional[str],
        output_path: Optional[str],
        cost_log_path: str,
    ) -> None:
        if self.resume and not self.artifact_paths:
            raise ValueError("Antigravity --resume requires --artifact-path for reviewed files")
        super().check(
            marker_path=marker_path,
            gate_id=gate_id,
            artifact_key=artifact_key,
            request_prompt=request_prompt,
            reviewer=reviewer,
            requested_model=requested_model,
            output_path=output_path,
            cost_log_path=cost_log_path,
        )
        if self.resume and _is_sensitive_id(self.session_id, self.sensitive_values):
            raise ValueError(
                "recorded Antigravity conversation UUID matches a known sensitive value; refusing to resume"
            )

    def finish(self, result: ReviewResult) -> ReviewResult:
        if _is_sensitive_id(self.data.get("session_id"), self.sensitive_values):
            self.data["session_id"] = "[REDACTED]"
            if result.status in {"success", "timeout"}:
                result = ReviewResult(
                    "provenance_failure",
                    None,
                    {
                        **result.envelope,
                        "session_id": None,
                        "observed_session_id": None,
                        "detail": "Antigravity conversation_id matches a known sensitive value; refusing to persist session identity",
                    },
                    1,
                )
        return super().finish(result)

    def decorate(self, result: ReviewResult) -> ReviewResult:
        observed_id = _validate_uuid(result.envelope.get("observed_session_id"))
        if observed_id is not None and _is_sensitive_id(observed_id, self.sensitive_values):
            result = ReviewResult(
                "provenance_failure",
                None,
                {
                    **result.envelope,
                    "session_id": None,
                    "observed_session_id": None,
                    "detail": "Antigravity conversation_id matches a known sensitive value; refusing to adopt session identity",
                },
                1,
            )
            return super().decorate(result)
        if result.status in {"timeout", "success"}:
            if self.resume:
                if observed_id is None or observed_id != self.session_id:
                    result = ReviewResult(
                        "provenance_failure",
                        None,
                        {
                            **result.envelope,
                            "detail": "resumed Antigravity segment did not return a matching native conversation UUID",
                        },
                        1,
                    )
            else:
                if observed_id is None:
                    result = ReviewResult(
                        "provenance_failure",
                        None,
                        {
                            **result.envelope,
                            "detail": "Antigravity did not return a verified native conversation UUID; timeout cannot be resumed",
                        },
                        1,
                    )
                else:
                    self.data["session_id"] = observed_id
                    if result.status == "timeout" and not self.artifact_paths:
                        result = ReviewResult(
                            "other_error",
                            None,
                            {
                                **result.envelope,
                                "detail": "review subprocess timed out without --artifact-path; Antigravity timeout continuation requires registered reviewed files",
                            },
                            1,
                        )
        return super().decorate(result)

    def require_history(self) -> None:
        """Require an existing, non-empty regular `.db` strictly inside session_store."""
        store_root = Path(self.session_store).resolve()
        conversations_dir = store_root / "conversations"
        if conversations_dir.is_symlink():
            raise ValueError("original Antigravity native history is missing; cannot resume this gate")
        db_path = conversations_dir / f"{self.session_id}.db"
        if db_path.is_symlink() or not db_path.exists() or not db_path.is_file():
            raise ValueError("original Antigravity native history is missing; cannot resume this gate")
        try:
            resolved = db_path.resolve(strict=True)
        except OSError as exc:
            raise ValueError("original Antigravity native history is missing; cannot resume this gate") from exc
        if store_root not in resolved.parents:
            raise ValueError("original Antigravity native history escapes session store; cannot resume this gate")
        if resolved.stat().st_size <= 0:
            raise ValueError("original Antigravity native history is empty; cannot resume this gate")


def _safe_close_stream(stream: Any) -> None:
    if stream is None:
        return
    try:
        stream.close()
    except OSError:
        pass


def _killpg_strict(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return
        raise OSError(
            f"Antigravity POSIX process-group cleanup failed (pgid={pgid}): {exc}"
        ) from exc


def _run_agy_subprocess_posix(
    argv: list,
    *,
    env: Optional[dict],
    input_bytes: bytes,
    timeout: float,
    cwd: Optional[str],
):
    sel = selectors.DefaultSelector()
    process = None
    stdin_stream = None
    completed_cleanly = False
    killpg_error: Optional[OSError] = None
    raising_timeout = False
    try:
        process = subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
            **({"cwd": cwd} if cwd is not None else {}),
        )
        stdout_chunks: list = []
        stderr_chunks: list = []
        open_readers: set = set()
        stdin_stream = process.stdin
        stdin_view = memoryview(input_bytes)
        stdin_offset = 0
        stdin_complete = len(input_bytes) == 0

        if stdin_stream is not None:
            if not input_bytes:
                _safe_close_stream(stdin_stream)
                stdin_stream = None
            else:
                os.set_blocking(stdin_stream.fileno(), False)
                sel.register(stdin_stream, selectors.EVENT_WRITE, "stdin")

        for tag, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if stream is not None:
                os.set_blocking(stream.fileno(), False)
                sel.register(stream, selectors.EVENT_READ, tag)
                open_readers.add(tag)

        overall_deadline = time.monotonic() + float(timeout)
        exit_time: Optional[float] = None
        drain_deadline: Optional[float] = None

        while True:
            now = time.monotonic()
            if exit_time is None and process.poll() is not None:
                exit_time = now
                drain_deadline = min(overall_deadline, exit_time + POST_EXIT_DRAIN_SECONDS)
            if exit_time is not None and not open_readers:
                break
            ceiling = drain_deadline if drain_deadline is not None else overall_deadline
            remaining = ceiling - now
            if remaining <= 0:
                break
            events = sel.select(timeout=min(remaining, 0.05))
            for key, _mask in events:
                tag = key.data
                stream = key.fileobj
                if tag == "stdin":
                    broken_pipe = False
                    try:
                        written = os.write(stream.fileno(), stdin_view[stdin_offset : stdin_offset + 65536])
                    except (BlockingIOError, InterruptedError):
                        continue
                    except BrokenPipeError:
                        broken_pipe = True
                    except OSError as exc:
                        if exc.errno == errno.EPIPE:
                            broken_pipe = True
                        else:
                            raise OSError(f"Antigravity stdin pipe write failed: {exc}") from exc
                    if broken_pipe:
                        sel.unregister(stream)
                        _safe_close_stream(stream)
                        stdin_stream = None
                    else:
                        if written <= 0:
                            raise OSError("Antigravity stdin pipe write returned 0 bytes")
                        stdin_offset += written
                        if stdin_offset >= len(input_bytes):
                            stdin_complete = True
                            sel.unregister(stream)
                            _safe_close_stream(stream)
                            stdin_stream = None
                else:
                    try:
                        chunk = os.read(stream.fileno(), 65536)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except OSError as exc:
                        raise OSError(f"Antigravity {tag} pipe read failed: {exc}") from exc
                    if not chunk:
                        sel.unregister(stream)
                        _safe_close_stream(stream)
                        open_readers.discard(tag)
                    elif tag == "stdout":
                        stdout_chunks.append(chunk)
                    else:
                        stderr_chunks.append(chunk)

        if exit_time is None and process.poll() is not None:
            exit_time = time.monotonic()

        if exit_time is not None:
            if open_readers:
                # Launcher exited, but a descendant kept stdout/stderr open past drain deadline.
                try:
                    _killpg_strict(process.pid)
                except OSError:
                    pass
                raise OSError("Antigravity post-exit pipe drain timed out; descendant held output open")
            rc = process.wait(timeout=1.0)
            if not stdin_complete and rc == 0:
                raise OSError("Antigravity stdin prompt delivery was incomplete before exit 0")
            completed_cleanly = True
            return subprocess.CompletedProcess(
                argv, rc, b"".join(stdout_chunks), b"".join(stderr_chunks)
            )

        # Timeout path: terminate adapter-owned process group, wait bounded, drain bounded.
        if stdin_stream is not None:
            try:
                sel.unregister(stdin_stream)
            except KeyError:
                pass
            _safe_close_stream(stdin_stream)
            stdin_stream = None

        try:
            _killpg_strict(process.pid)
        except OSError as exc:
            killpg_error = exc
            raise

        cleanup_deadline = time.monotonic() + CLEANUP_TIMEOUT_SECONDS
        try:
            process.wait(timeout=max(0.01, cleanup_deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            raise OSError("Antigravity timeout cleanup did not terminate owned process") from exc

        while open_readers:
            rem = cleanup_deadline - time.monotonic()
            if rem <= 0:
                break
            events = sel.select(timeout=min(rem, 0.05))
            for key, _mask in events:
                tag = key.data
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError as exc:
                    raise OSError(f"Antigravity timeout drain {tag} pipe read failed: {exc}") from exc
                if not chunk:
                    sel.unregister(stream)
                    _safe_close_stream(stream)
                    open_readers.discard(tag)
                elif tag == "stdout":
                    stdout_chunks.append(chunk)
                else:
                    stderr_chunks.append(chunk)

        if open_readers:
            raise OSError("Antigravity timeout cleanup did not close owned process pipes")
        if not stdin_complete:
            raise OSError("Antigravity stdin prompt delivery was incomplete before timeout")

        raising_timeout = True
        raise subprocess.TimeoutExpired(
            argv,
            timeout,
            output=b"".join(stdout_chunks),
            stderr=b"".join(stderr_chunks),
        )
    finally:
        # Ensure any I/O, selector, or timeout exit after Popen terminates the
        # entire owned PGID, even if the direct launcher already exited with 0.
        if process is not None and not completed_cleanly:
            try:
                _killpg_strict(process.pid)
            except OSError as exc:
                if killpg_error is None:
                    killpg_error = exc
            if process.poll() is None:
                try:
                    process.kill()
                except (ProcessLookupError, OSError):
                    pass
                try:
                    process.wait(timeout=CLEANUP_TIMEOUT_SECONDS)
                except (subprocess.TimeoutExpired, OSError):
                    pass
        for key in list(sel.get_map().values()):
            try:
                sel.unregister(key.fileobj)
            except (KeyError, ValueError):
                pass
            _safe_close_stream(key.fileobj)
        sel.close()
        _safe_close_stream(stdin_stream)
        if process is not None:
            _safe_close_stream(process.stdout)
            _safe_close_stream(process.stderr)
        if killpg_error is not None and raising_timeout:
            raise killpg_error


def _run_agy_subprocess_windows(
    argv: list,
    *,
    env: Optional[dict],
    input_bytes: bytes,
    timeout: float,
    cwd: Optional[str],
):
    process = subprocess.Popen(
        argv,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        **({"cwd": cwd} if cwd is not None else {}),
    )
    stdout_chunks: list = []
    stderr_chunks: list = []
    read_errors: list = []
    write_errors: list = []
    stdin_complete = [len(input_bytes) == 0]

    def _write_stdin() -> None:
        stream = process.stdin
        if stream is None:
            return
        try:
            view = memoryview(input_bytes)
            offset = 0
            while offset < len(input_bytes):
                written = stream.write(view[offset : offset + 65536])
                if not written or written <= 0:
                    write_errors.append("stdin: zero-byte write")
                    break
                offset += written
            else:
                stdin_complete[0] = True
        except BrokenPipeError:
            pass
        except OSError as exc:
            # On Windows, writing to a pipe after the child exits early can raise
            # EINVAL as well as BrokenPipeError/EPIPE (see CPython subprocess.py).
            if getattr(exc, "errno", None) not in (errno.EPIPE, errno.EINVAL):
                write_errors.append(f"stdin: {exc}")
        finally:
            _safe_close_stream(stream)

    def _read_pipe(stream: Any, sink: list, tag: str) -> None:
        if stream is None:
            return
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                sink.append(chunk)
        except OSError as exc:
            read_errors.append(f"{tag}: {exc}")

    def _taskkill_tree() -> bool:
        try:
            killer = subprocess.Popen(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        try:
            killer.wait(timeout=CLEANUP_TIMEOUT_SECONDS)
            return killer.returncode == 0
        except subprocess.TimeoutExpired:
            try:
                killer.kill()
            except OSError:
                pass
            try:
                killer.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, OSError):
                pass
            return False

    def _terminate_bounded() -> bool:
        cleanup_ok = False
        try:
            cleanup_ok = _taskkill_tree()
        finally:
            try:
                process.kill()
            except (ProcessLookupError, OSError):
                pass
            try:
                process.wait(timeout=CLEANUP_TIMEOUT_SECONDS)
            except (subprocess.TimeoutExpired, OSError):
                cleanup_ok = False
        return cleanup_ok

    writer = threading.Thread(target=_write_stdin, daemon=True)
    out_reader = threading.Thread(
        target=_read_pipe, args=(process.stdout, stdout_chunks, "stdout"), daemon=True
    )
    err_reader = threading.Thread(
        target=_read_pipe, args=(process.stderr, stderr_chunks, "stderr"), daemon=True
    )
    started_threads: list = []
    try:
        for thread in (writer, out_reader, err_reader):
            thread.start()
            started_threads.append(thread)
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        cleanup_ok = _terminate_bounded()
        drain_deadline = time.monotonic() + CLEANUP_TIMEOUT_SECONDS
        for thread in started_threads:
            rem = max(0.0, drain_deadline - time.monotonic())
            thread.join(timeout=rem)
        threads_done = not any(t.is_alive() for t in started_threads)
        if threads_done:
            _safe_close_stream(process.stdout)
            _safe_close_stream(process.stderr)
        if not cleanup_ok or not threads_done or read_errors or write_errors or not stdin_complete[0]:
            # Never call blocking close() on hung Windows pipes; fail closed and release lock.
            io_errors = read_errors + write_errors
            if io_errors:
                detail = "; ".join(io_errors)
            elif not stdin_complete[0]:
                detail = "stdin prompt delivery was incomplete before timeout"
            else:
                detail = "closure is unverified"
            raise OSError(f"Antigravity Windows process-tree cleanup/I/O failed: {detail}")
        raise subprocess.TimeoutExpired(
            argv,
            timeout,
            output=b"".join(stdout_chunks),
            stderr=b"".join(stderr_chunks),
        ) from None
    except BaseException as exc:
        _terminate_bounded()
        drain_deadline = time.monotonic() + CLEANUP_TIMEOUT_SECONDS
        for thread in started_threads:
            rem = max(0.0, drain_deadline - time.monotonic())
            thread.join(timeout=rem)
        if not any(t.is_alive() for t in started_threads):
            _safe_close_stream(process.stdin)
            _safe_close_stream(process.stdout)
            _safe_close_stream(process.stderr)
        if isinstance(exc, RuntimeError):
            raise OSError(f"Antigravity Windows I/O thread startup failed: {exc}") from exc
        raise

    # Normal exit: drain ALL pipe threads (readers + stdin writer) within POST_EXIT_DRAIN_SECONDS.
    drain_deadline = time.monotonic() + POST_EXIT_DRAIN_SECONDS
    for thread in started_threads:
        rem = max(0.0, drain_deadline - time.monotonic())
        thread.join(timeout=rem)
    if any(t.is_alive() for t in started_threads):
        _terminate_bounded()
        raise OSError("Antigravity post-exit pipe drain timed out; pipe thread stayed active")
    _safe_close_stream(process.stdout)
    _safe_close_stream(process.stderr)
    io_errors = read_errors + write_errors
    if io_errors:
        raise OSError(f"Antigravity Windows pipe I/O failed: {'; '.join(io_errors)}")
    if not stdin_complete[0] and process.returncode == 0:
        raise OSError("Antigravity stdin prompt delivery was incomplete before exit 0")
    return subprocess.CompletedProcess(
        argv, process.returncode, b"".join(stdout_chunks), b"".join(stderr_chunks)
    )


def _run_agy_subprocess(
    argv: list,
    *,
    env: Optional[dict],
    input: bytes,
    capture_output: bool,
    text: bool,
    timeout: float,
    cwd: Optional[str] = None,
):
    """Strictly bounded subprocess runner for `agy` (never holds marker lock unboundedly)."""
    input_bytes = _to_utf8_bytes(input)
    if os.name == "posix":
        return _run_agy_subprocess_posix(
            argv, env=env, input_bytes=input_bytes, timeout=timeout, cwd=cwd
        )
    return _run_agy_subprocess_windows(
        argv, env=env, input_bytes=input_bytes, timeout=timeout, cwd=cwd
    )


def run_agy_review(
    argv: list,
    *,
    runner: Optional[Callable] = None,
    env: Optional[dict] = None,
    timeout_seconds: float = 600,
    prompt: Optional[str] = None,
    cwd: Optional[str] = None,
    sensitive_values: Optional[list] = None,
) -> ReviewResult:
    """Invoke `agy` stream-json headless mode and classify the result."""
    encoded_input = encode_agy_prompt(prompt or "")
    invoke_runner = _run_agy_subprocess if runner is None else runner

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
                fail_status, fail_detail = _classify_terminal_result_failure(
                    last_res, partial_err, sensitive_values
                )
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

        if parsed["unterminated_result_event"]:
            if parsed["unterminated_results"]:
                last_unterm = parsed["unterminated_results"][-1]
                if last_unterm.get("status") != "SUCCESS":
                    fail_status, fail_detail = _classify_terminal_result_failure(
                        last_unterm, partial_err, sensitive_values
                    )
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
                    "detail": _provenance_failure_detail(
                        parsed, "unterminated terminal result before timeout"
                    ),
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
        if _is_sensitive_id(observed_id, sensitive_values):
            return ReviewResult(
                "provenance_failure",
                None,
                {
                    "error_type": "TimeoutExpired",
                    "session_id": None,
                    "observed_session_id": None,
                    "total_cost_usd": None,
                    "detail": "Antigravity conversation_id matches a known sensitive value; refusing to adopt session identity",
                },
                1,
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
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return ReviewResult(
            status="other_error",
            text=None,
            envelope={
                "error_type": type(exc).__name__,
                "detail": _redact_and_truncate(str(exc), sensitive_values, 200),
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

    # Auth failure check on non-success (inspecting error/stderr only; redact before truncating).
    if exit_code != 0 or result_status != "SUCCESS":
        if _is_auth_failure_text(result_error, stderr_text):
            raw_detail = (
                result_error
                if isinstance(result_error, str) and result_error.strip()
                else stderr_text.strip() or "authentication required"
            )
            return ReviewResult(
                "auth_failure",
                None,
                {
                    "detail": _redact_and_truncate(raw_detail, sensitive_values, 200),
                    "session_id": None,
                    "total_cost_usd": None,
                },
                exit_code if exit_code != 0 else 1,
            )

    # Terminal non-SUCCESS status from a parsed result payload.
    if isinstance(last_result, dict) and result_status != "SUCCESS":
        fail_status, fail_detail = _classify_terminal_result_failure(
            last_result, stderr_text, sensitive_values
        )
        err_session_id = _validate_uuid(last_result.get("conversation_id"))
        if _is_sensitive_id(err_session_id, sensitive_values):
            err_session_id = None
        return ReviewResult(
            fail_status,
            None,
            {
                "detail": fail_detail,
                "session_id": err_session_id,
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
                "detail": _redact_and_truncate(
                    stderr_text.strip() or f"agy exited with status {exit_code}",
                    sensitive_values,
                    200,
                ),
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
    if _is_sensitive_id(init_id, sensitive_values):
        return ReviewResult(
            "provenance_failure",
            None,
            {
                "detail": "Antigravity conversation_id matches a known sensitive value; refusing to adopt session identity",
                "session_id": None,
                "observed_session_id": None,
                "total_cost_usd": None,
            },
            1,
        )
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

    store_path = os.path.realpath(
        os.path.expanduser(agy_home or "~/.gemini/antigravity-cli")
    )
    continuation = _AgyContinuation(
        resume=resume,
        cwd=working_dir,
        artifact_paths=artifact_paths or [],
        session_store=store_path,
        binding_context={"add_dirs": resolved_add_dirs},
        sensitive_values=sensitive_values,
    )

    def prepare(_marker_dir: str) -> dict:
        if resume:
            continuation.require_history()
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
            session_id=continuation.session_id if resume else None,
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
            sensitive_values=sensitive_values,
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
        continuation=continuation,
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
        help_runner=_run_agy_help_probe,
        resume=args.resume,
        artifact_paths=args.artifact_paths,
    )
    raw_session_id = result.envelope.get("session_id")
    valid_session_id = _validate_uuid(raw_session_id)
    safe_session_id = (
        valid_session_id
        if valid_session_id is not None and not _is_sensitive_id(valid_session_id, sensitive_values)
        else None
    )
    raw_handoff = result.envelope.get("handoff_path")
    safe_handoff = (
        None
        if result.status == "success"
        else _safe_stdout_path(raw_handoff, sensitive_values)
    )
    safe_cont_path = _safe_stdout_path(result.envelope.get("continuation_state_path"), sensitive_values)
    safe_output = (
        _safe_stdout_path(args.output, sensitive_values)
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
