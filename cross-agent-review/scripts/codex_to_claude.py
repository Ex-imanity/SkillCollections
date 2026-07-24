"""Codex -> ClaudeCode review adapter.

A narrow, fail-closed bridge that lets a Codex-primary turn ask a fresh,
read-only ClaudeCode reviewer for a verdict via `claude -p`, without
mutating auth state or fabricating reviewer output.

Design decisions (user-confirmed 2026-07-21, see the plan):
- Credential = verify-then-fallback: prefer the persisted ~/.claude/settings.json
  `env` block; only inject explicit proxy vars if that block is missing.
- Readiness is judged by a real result envelope, never by `claude auth status`.
- Cost is treated as real: cap rounds tightly and log total_cost_usd per gate.
- Fail closed: any non-success writes a durable handoff and returns no text.

Pure stdlib. The subprocess boundary is injectable (`runner`) so unit tests
never make real model calls.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Optional

DEFAULT_ALLOWED_TOOLS = "Read,Grep,Glob"
DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
PROXY_ENV_KEYS = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN")
_AUTH_ERROR_STATUSES = {401, 403}
_AUTH_ERROR_PHRASES = (
    "failed to authenticate",
    "authentication failed",
    "unauthorized",
    "forbidden",
)
_SECRET_PATTERNS = (
    (re.compile(r"(?i)(ANTHROPIC_AUTH_TOKEN\s*[=:]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(ANTHROPIC_BASE_URL\s*[=:]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)\S+"), r"\1[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{6,}\b"), "[REDACTED]"),
    (
        re.compile(
            r"(?i)https?://(?:"
            r"localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|"
            r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
            r"(?:[A-Za-z0-9-]+\.)*(?:internal|local)"
            r")(?::\d+)?(?:[/\w.%?=&+#~-]*)"
        ),
        "[REDACTED]",
    ),
)


# --- readiness ---------------------------------------------------------------


@dataclass
class Readiness:
    """Where the live credential comes from. Never carries the token value."""

    credential_source: str  # 'settings-env' | 'explicit-inject' | 'missing'
    base_url: Optional[str]
    token_present: bool

    def __repr__(self) -> str:  # defensive: keep token out of any dump
        return (
            f"Readiness(credential_source={self.credential_source!r}, "
            f"base_url={'[REDACTED]' if self.base_url else None}, "
            f"token_present={self.token_present!r})"
        )


def _read_env_block(settings_path: str) -> dict:
    try:
        with open(settings_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    env = data.get("env")
    return env if isinstance(env, dict) else {}


def check_readiness(
    settings_path: str = DEFAULT_SETTINGS_PATH,
    explicit_env: Optional[dict] = None,
) -> Readiness:
    """Verify-then-fallback credential source.

    1. If both proxy keys are non-empty in settings.json, use 'settings-env'.
    2. Else if explicit_env supplies both non-empty keys, use 'explicit-inject'.
    3. Else 'missing' (caller must fail closed before invoking the model).
    """
    env = _read_env_block(settings_path)
    if env.get("ANTHROPIC_BASE_URL") and env.get("ANTHROPIC_AUTH_TOKEN"):
        return Readiness(
            credential_source="settings-env",
            base_url=env.get("ANTHROPIC_BASE_URL"),
            token_present=True,
        )
    if (
        explicit_env
        and explicit_env.get("ANTHROPIC_BASE_URL")
        and explicit_env.get("ANTHROPIC_AUTH_TOKEN")
    ):
        return Readiness(
            credential_source="explicit-inject",
            base_url=explicit_env.get("ANTHROPIC_BASE_URL"),
            token_present=True,
        )
    return Readiness(credential_source="missing", base_url=None, token_present=False)


def resolve_subprocess_env(readiness: Readiness, explicit_env: Optional[dict] = None) -> dict:
    """Build the child env. Only injects proxy vars when not already persisted."""
    child = dict(os.environ)
    if readiness.credential_source == "settings-env":
        for key in PROXY_ENV_KEYS:
            child.pop(key, None)
    elif readiness.credential_source == "explicit-inject" and explicit_env:
        for key in PROXY_ENV_KEYS:
            if explicit_env.get(key):
                child[key] = explicit_env[key]
    return child


# --- command assembly --------------------------------------------------------


def build_command(
    request_prompt: str,
    add_dirs: Optional[list] = None,
    max_budget_usd: Optional[float] = None,
) -> list:
    """Assemble the read-only `claude -p` argv.

    The request prompt is intentionally excluded from argv and sent through
    stdin by `run_review`, avoiding argument-size and flag-parsing hazards.
    Every gate starts a fresh session. Re-review requests must carry prior
    findings and new evidence explicitly rather than resuming hidden context.
    """
    argv = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--input-format",
        "text",
        "--permission-mode",
        "plan",
        "--allowedTools",
        DEFAULT_ALLOWED_TOOLS,
    ]
    for d in add_dirs or []:
        argv += ["--add-dir", d]
    if max_budget_usd is not None:
        if max_budget_usd <= 0:
            raise ValueError("max_budget_usd must be positive")
        argv += ["--max-budget-usd", str(max_budget_usd)]
    return argv


# --- envelope classification -------------------------------------------------


def classify_envelope(exit_code: int, envelope: dict) -> str:
    """Classify a `claude -p --output-format json` result.

    Returns 'success' | 'auth_failure' | 'other_error'. Readiness is decided
    here on the real envelope, never on `claude auth status`.
    """
    raw_status = envelope.get("api_error_status")
    try:
        status = int(raw_status) if raw_status is not None else None
    except (TypeError, ValueError):
        status = raw_status
    result = envelope.get("result")
    result_text = result if isinstance(result, str) else ""
    is_error = envelope.get("is_error") is True
    has_auth_phrase = any(phrase in result_text.lower() for phrase in _AUTH_ERROR_PHRASES)
    if status in _AUTH_ERROR_STATUSES or ((exit_code != 0 or is_error) and has_auth_phrase):
        return "auth_failure"
    if (
        exit_code == 0
        and envelope.get("is_error") is False
        and status is None
        and isinstance(result, str)
        and bool(result.strip())
    ):
        return "success"
    return "other_error"


# --- run ---------------------------------------------------------------------


@dataclass
class ReviewResult:
    status: str  # 'success' | 'auth_failure' | 'other_error'
    text: Optional[str]
    envelope: dict
    exit_code: int


def run_review(
    argv: list,
    runner: Callable = subprocess.run,
    env: Optional[dict] = None,
    timeout_seconds: float = 600,
    request_prompt: Optional[str] = None,
) -> ReviewResult:
    """Invoke `claude -p` with prompt on stdin and classify the envelope."""
    try:
        completed = runner(
            argv,
            env=env,
            input=request_prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ReviewResult(
            status="other_error",
            text=None,
            envelope={"error_type": type(exc).__name__},
            exit_code=1,
        )
    exit_code = getattr(completed, "returncode", 1)
    stdout = getattr(completed, "stdout", "") or ""
    try:
        envelope = json.loads(stdout)
        if not isinstance(envelope, dict):
            raise ValueError("envelope is not an object")
    except (ValueError, TypeError):
        return ReviewResult(status="other_error", text=None, envelope={}, exit_code=exit_code or 1)

    status = classify_envelope(exit_code, envelope)
    text = envelope.get("result") if status == "success" else None
    effective_exit_code = exit_code if status == "success" or exit_code != 0 else 1
    return ReviewResult(
        status=status,
        text=text,
        envelope=envelope,
        exit_code=effective_exit_code,
    )


# --- round cap ---------------------------------------------------------------


@dataclass
class RoundDecision:
    allowed: bool
    current: int
    max_rounds: int
    reason: Optional[str] = None


def _load_counts(marker_path: str) -> tuple:
    """Return (counts, valid). counts is {} when the marker is absent.

    valid is False when the marker exists but is not a {str: non-negative int}
    object, so callers can fail closed without resetting a tampered marker.
    """
    if not os.path.exists(marker_path):
        return {}, True
    try:
        with open(marker_path, encoding="utf-8") as fh:
            counts = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}, False
    valid = isinstance(counts, dict) and all(
        isinstance(key, str)
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        for key, value in counts.items()
    )
    return (counts, True) if valid else ({}, False)


def check_round_cap(marker_path: str, artifact_key: str, max_rounds: int = 2) -> RoundDecision:
    """Read-only round-cap check. Never writes the marker.

    Returns allowed=True only while the committed count for this artifact is
    still below max_rounds. A tampered/malformed marker fails closed
    (`invalid_marker`) without being reset. Callers must invoke `commit_round`
    only after a verified successful review, so a failed model call consumes no
    round (P2-2).
    """
    if max_rounds < 1:
        raise ValueError("max_rounds must be at least 1")
    counts, valid = _load_counts(marker_path)
    if not valid:
        return RoundDecision(
            allowed=False,
            current=max_rounds + 1,
            max_rounds=max_rounds,
            reason="invalid_marker",
        )
    current = counts.get(artifact_key, 0)
    allowed = current < max_rounds
    return RoundDecision(
        allowed=allowed,
        current=current,
        max_rounds=max_rounds,
        reason=None if allowed else "round_cap_exceeded",
    )


@contextmanager
def round_cap_guard(marker_path: str, artifact_key: str, max_rounds: int = 2):
    """Hold the marker lock from cap check through the caller's commit.

    Gate callers must keep this context open for the complete paid review. That
    serialization prevents two processes from both passing the same cap before
    either one commits.
    """
    marker_dir = os.path.dirname(os.path.abspath(marker_path))
    os.makedirs(marker_dir, exist_ok=True)
    lock_path = f"{marker_path}.lock"
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield check_round_cap(marker_path, artifact_key, max_rounds=max_rounds)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _commit_round_unlocked(
    marker_path: str,
    artifact_key: str,
    max_rounds: Optional[int] = None,
) -> int:
    """Increment while the caller holds the marker lock."""
    counts, valid = _load_counts(marker_path)
    if not valid:
        raise ValueError("cannot commit a round over an invalid marker")
    previous = counts.get(artifact_key, 0)
    if max_rounds is not None and previous >= max_rounds:
        raise ValueError("cannot commit a round beyond max_rounds")
    current = previous + 1
    counts[artifact_key] = current
    marker_dir = os.path.dirname(os.path.abspath(marker_path))
    os.makedirs(marker_dir, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".rounds-", suffix=".json", dir=marker_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(counts, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary_path, marker_path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return current


def commit_round(
    marker_path: str,
    artifact_key: str,
    max_rounds: Optional[int] = None,
) -> int:
    """Lock and atomically increment the committed count for artifact_key.

    Call only after a verified successful review. Refuses to write over a
    malformed marker rather than resetting it. When max_rounds is supplied,
    the cap is rechecked under the same lock used for the increment.
    """
    effective_cap = max_rounds if max_rounds is not None else 2**63 - 1
    with round_cap_guard(marker_path, artifact_key, max_rounds=effective_cap):
        return _commit_round_unlocked(marker_path, artifact_key, max_rounds=max_rounds)


# --- fail closed -------------------------------------------------------------


def _known_sensitive_values(settings_path: str, explicit_env: Optional[dict]) -> list:
    """Collect configured endpoint/token values without persisting them."""
    candidates = []
    for source in (_read_env_block(settings_path), explicit_env or {}):
        for key in PROXY_ENV_KEYS:
            value = source.get(key)
            if isinstance(value, str) and value and value not in candidates:
                candidates.append(value)
    return candidates


def _redact_sensitive_text(value: str, sensitive_values: Optional[list] = None) -> str:
    redacted = value
    for sensitive_value in sorted(sensitive_values or [], key=len, reverse=True):
        if isinstance(sensitive_value, str) and sensitive_value:
            redacted = redacted.replace(sensitive_value, "[REDACTED]")
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _safe_gate_id(gate_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", gate_id).strip("-.")
    return safe or "review-gate"


def _atomic_write_text(path: str, body: str) -> None:
    target_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(target_dir, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix=".review-", suffix=".tmp", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def fail_closed(
    handoff_dir: str,
    gate_id: str,
    status: str,
    detail: str,
    request_prompt: str,
    sensitive_values: Optional[list] = None,
) -> str:
    """Write a durable handoff instead of fabricating a reviewer response.

    The primary must NOT invent reviewer output and must NOT mutate auth state.
    A human continues the review in an interactive ClaudeCode session.
    """
    os.makedirs(handoff_dir, exist_ok=True)
    path = os.path.join(handoff_dir, f"handoff-{_safe_gate_id(gate_id)}.md")
    safe_detail = _redact_sensitive_text(str(detail), sensitive_values)
    safe_request = _redact_sensitive_text(str(request_prompt), sensitive_values)
    body = (
        f"# Cross-Agent Review Handoff — {gate_id}\n\n"
        f"Status: **{status}** (fail-closed)\n\n"
        f"Detail: {safe_detail}\n\n"
        "The Codex->ClaudeCode adapter could not obtain a verified reviewer "
        "envelope, so it did NOT fabricate a review and did NOT change auth "
        "state. A human should continue this review in an interactive "
        "ClaudeCode session (handoff), then hand the verdict back to the "
        "primary.\n\n"
        "## Original review request (verbatim)\n\n"
        f"{safe_request}\n"
    )
    _atomic_write_text(path, _redact_sensitive_text(body, sensitive_values))
    return path


def gate_failure_result(
    handoff_dir: str,
    gate_id: str,
    status: str,
    detail: str,
    request_prompt: str,
    sensitive_values: Optional[list] = None,
    envelope: Optional[dict] = None,
) -> ReviewResult:
    """Return a structured failure and make a best effort to persist handoff."""
    failure_envelope = dict(envelope or {})
    failure_envelope["detail"] = detail
    try:
        fail_closed(
            handoff_dir,
            gate_id,
            status,
            detail,
            request_prompt,
            sensitive_values,
        )
    except (OSError, ValueError) as exc:
        failure_envelope["handoff_error"] = f"{type(exc).__name__}: {exc}"
    return ReviewResult(status, None, failure_envelope, exit_code=1)


def persist_success(
    output_path: str,
    gate_id: str,
    result: ReviewResult,
    sensitive_values: Optional[list] = None,
    reviewer: str = "ClaudeCode",
) -> str:
    """Persist a verified reviewer result without serializing the raw envelope.

    `reviewer` names the agent that produced the review (ClaudeCode for the
    codex->claude direction, Codex for the claude->codex direction).
    """
    if result.status != "success" or not isinstance(result.text, str) or not result.text.strip():
        raise ValueError("only a verified non-empty review can be persisted")
    session_id = result.envelope.get("session_id") or "unknown"
    total_cost = result.envelope.get("total_cost_usd", "unknown")
    safe_text = _redact_sensitive_text(result.text, sensitive_values)
    body = (
        f"# Cross-Agent Review - {_safe_gate_id(gate_id)}\n\n"
        f"Reviewer: {reviewer}\n"
        f"Gate: `{_safe_gate_id(gate_id)}`\n"
        f"Reviewer session: `{session_id}`\n"
        f"Reported cost USD: `{total_cost}`\n\n"
        "## Review\n\n"
        f"{safe_text.rstrip()}\n"
    )
    _atomic_write_text(output_path, _redact_sensitive_text(body, sensitive_values))
    return output_path


# --- cost logging ------------------------------------------------------------


def log_cost(
    envelope: dict,
    log_path: str,
    gate_id: str,
    wall_seconds: float,
    extra: Optional[dict] = None,
) -> None:
    """Append one cost/latency record per review gate.

    `total_cost_usd` is recorded verbatim from the envelope (may be None when a
    provider like Codex reports token usage but no USD — never fabricate 0).
    `extra` merges provider-specific fields such as token usage.
    """
    record = {
        "gate_id": gate_id,
        "total_cost_usd": envelope.get("total_cost_usd"),
        "wall_seconds": round(float(wall_seconds), 3),
    }
    if extra:
        record.update(extra)
    line = json.dumps(record, sort_keys=True)
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# --- orchestration helper ----------------------------------------------------


def review_gate(
    request_prompt: str,
    add_dirs: list,
    handoff_dir: str,
    marker_path: str,
    gate_id: str,
    artifact_key: str,
    cost_log_path: str,
    output_path: Optional[str] = None,
    settings_path: str = DEFAULT_SETTINGS_PATH,
    explicit_env: Optional[dict] = None,
    max_rounds: int = 2,
    runner: Callable = subprocess.run,
    timeout_seconds: float = 600,
    max_budget_usd: Optional[float] = None,
) -> ReviewResult:
    """End-to-end single review gate with all guards applied.

    Order: readiness -> round-cap CHECK (read-only) -> invoke -> classify ->
    log cost -> commit round ONLY on success. A failed model call therefore
    consumes no round (P2-2). Fails closed on refusal, missing credential, or
    any non-success.
    """
    sensitive_values = _known_sensitive_values(settings_path, explicit_env)
    readiness = check_readiness(settings_path=settings_path, explicit_env=explicit_env)
    if readiness.credential_source == "missing":
        fail_closed(
            handoff_dir,
            gate_id,
            "credential_missing",
            "no proxy token",
            request_prompt,
            sensitive_values,
        )
        return ReviewResult("credential_missing", None, {}, exit_code=1)

    try:
        with round_cap_guard(marker_path, artifact_key, max_rounds=max_rounds) as decision:
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

            argv = build_command(
                request_prompt,
                add_dirs,
                max_budget_usd=max_budget_usd,
            )
            child_env = resolve_subprocess_env(readiness, explicit_env)

            start = time.monotonic()
            result = run_review(
                argv,
                runner=runner,
                env=child_env,
                timeout_seconds=timeout_seconds,
                request_prompt=request_prompt,
            )
            try:
                log_cost(result.envelope, cost_log_path, gate_id, time.monotonic() - start)
            except (OSError, ValueError) as exc:
                detail = f"{type(exc).__name__}: {exc}"
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
                # Consume no round on failure: only a completed review commits (P2-2).
                return gate_failure_result(
                    handoff_dir,
                    gate_id,
                    result.status,
                    str(result.envelope.get("result", "no result")),
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
                _commit_round_unlocked(marker_path, artifact_key, max_rounds=max_rounds)
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
    parser = argparse.ArgumentParser(description="Run a fail-closed Codex to ClaudeCode review gate")
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--add-dir", action="append", default=[])
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--marker-path", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--artifact-key", required=True)
    parser.add_argument("--cost-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--max-budget-usd", type=float)
    return parser


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    with open(args.request_file, encoding="utf-8") as fh:
        request_prompt = fh.read()
    explicit_env = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
    result = review_gate(
        request_prompt=request_prompt,
        add_dirs=args.add_dir,
        handoff_dir=args.handoff_dir,
        marker_path=args.marker_path,
        gate_id=args.gate_id,
        artifact_key=args.artifact_key,
        cost_log_path=args.cost_log,
        output_path=args.output,
        settings_path=args.settings,
        explicit_env=explicit_env,
        max_rounds=args.max_rounds,
        timeout_seconds=args.timeout_seconds,
        max_budget_usd=args.max_budget_usd,
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
