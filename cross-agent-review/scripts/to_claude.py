"""Any primary -> ClaudeCode review adapter.

Fail-closed bridge that asks a fresh ClaudeCode reviewer for a verdict via
`claude -p`, without mutating auth state or fabricating reviewer output.

Design decisions (user-confirmed 2026-07-21):
- Credential = verify-then-fallback: prefer the persisted ~/.claude/settings.json
  `env` block; only inject explicit proxy vars if that block is missing.
- Readiness is judged by a real result envelope, never by `claude auth status`.
- Cost is treated as real: cap rounds tightly and log total_cost_usd per gate.
- Fail closed: any non-success writes a durable handoff and returns no text.

Shared protocol helpers live in `common`. Pure stdlib. The subprocess boundary
is injectable (`runner`) so unit tests never make real model calls.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .common import (
    DEFAULT_SETTINGS_PATH,
    _read_env_block,
    MAX_BUDGET_FLAG,
    MODEL_FLAG,
    PROXY_ENV_KEYS,
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

_REVIEWER_NAME = "ClaudeCode"


def fail_closed(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _fail_closed(*args, **kwargs)


def gate_failure_result(*args, **kwargs):
    kwargs.setdefault("reviewer", _REVIEWER_NAME)
    return _gate_failure_result(*args, **kwargs)

INHERITED_CLAUDE_IDENTITY_KEYS = (
    "ANTHROPIC_CUSTOM_HEADERS",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_AGENT_SDK_VERSION",
)
_TRUTHFUL_CLAUDE_CLI_USER_AGENT = re.compile(
    r"^claude-cli/[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$"
)
_CLAUDE_CLI_VERSION = re.compile(
    r"\b([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)\b"
)
_AUTH_ERROR_STATUSES = {401, 403}
_AUTH_ERROR_PHRASES = (
    "failed to authenticate",
    "authentication failed",
    "unauthorized",
    "forbidden",
)


def claude_available() -> bool:
    """True when the `claude` CLI is on PATH. Portability precheck."""
    return shutil.which("claude") is not None


def claude_supported_flags(
    executable: Optional[str] = None,
    help_runner: Callable = subprocess.run,
    timeout_seconds: float = 5,
    env: Optional[dict] = None,
) -> Optional[set[str]]:
    """Return recognized model/budget flags from local Claude help, or ``None``.

    A missing or unreadable help result is inconclusive rather than a failure.
    Callers use this one probe to avoid an extra subprocess when checking both
    the required budget flag and an explicitly requested model flag.
    """
    exe = executable or shutil.which("claude")
    if not exe:
        return None
    probe_kwargs: dict = {"capture_output": True, "text": True, "timeout": timeout_seconds}
    if env is not None:
        probe_kwargs["env"] = env
    try:
        completed = help_runner([exe, "--help"], **probe_kwargs)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (getattr(completed, "stdout", "") or "") + (getattr(completed, "stderr", "") or "")
    if not text.strip():
        return None
    return {flag for flag in (MAX_BUDGET_FLAG, MODEL_FLAG) if flag in text}


def claude_supports_max_budget(
    executable: Optional[str] = None,
    help_runner: Callable = subprocess.run,
    timeout_seconds: float = 5,
    env: Optional[dict] = None,
) -> Optional[bool]:
    """Best-effort check that the local `claude` accepts ``--max-budget-usd``."""
    flags = claude_supported_flags(executable, help_runner, timeout_seconds, env)
    return None if flags is None else MAX_BUDGET_FLAG in flags


@dataclass(frozen=True)
class ClaudeCliIdentity:
    """A version proven to come from the exact binary that will be invoked."""

    executable: str
    version: str

    @property
    def user_agent(self) -> str:
        return f"claude-cli/{self.version}"


def discover_claude_cli_identity(
    version_runner: Callable = subprocess.run,
    timeout_seconds: float = 5,
) -> ClaudeCliIdentity:
    """Resolve local `claude` and derive its truthful compatibility identity.

    This is a local version probe only. It never sends a model request or reads
    credentials. The returned executable is also used for the review command,
    preventing a PATH change from separating the advertised version and caller.
    """
    executable = shutil.which("claude")
    if not executable:
        raise ValueError("claude CLI is not available on PATH")
    try:
        completed = version_runner(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"unable to read local claude version: {exc}") from exc
    if completed.returncode != 0:
        raise ValueError("local claude --version exited non-zero")
    version_match = _CLAUDE_CLI_VERSION.search(completed.stdout or "")
    if not version_match:
        raise ValueError("local claude --version did not contain a semantic version")
    identity = ClaudeCliIdentity(executable=executable, version=version_match.group(1))
    if not _TRUTHFUL_CLAUDE_CLI_USER_AGENT.fullmatch(identity.user_agent):
        raise ValueError("local claude version is not a supported semantic version")
    return identity


@dataclass
class Readiness:
    """Where the live credential comes from. Never carries the token value."""

    credential_source: str  # 'settings-env' | 'explicit-inject' | 'inherited'
    base_url: Optional[str]
    token_present: bool

    def __repr__(self) -> str:  # defensive: keep token out of any dump
        return (
            f"Readiness(credential_source={self.credential_source!r}, "
            f"base_url={'[REDACTED]' if self.base_url else None}, "
            f"token_present={self.token_present!r})"
        )



def check_readiness(
    settings_path: str = DEFAULT_SETTINGS_PATH,
    explicit_env: Optional[dict] = None,
) -> Readiness:
    """Verify-then-fallback credential source.

    1. If both proxy keys are non-empty in settings.json, use 'settings-env'.
    2. Else if explicit_env supplies both non-empty keys, use 'explicit-inject'.
    3. Else 'inherited': no proxy gateway is configured, so let the local
       `claude` CLI use whatever auth it already holds (subscription/OAuth
       login in the default config dir, or an ambient ANTHROPIC_API_KEY). This
       is the common case for installers not behind a custom gateway. Actual
       auth is still judged on the real result envelope, never pre-asserted;
       an unauthenticated CLI classifies as `auth_failure` and fails closed.
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
    return Readiness(credential_source="inherited", base_url=None, token_present=False)


def resolve_subprocess_env(
    readiness: Readiness,
    explicit_env: Optional[dict] = None,
    settings_path: str = DEFAULT_SETTINGS_PATH,
    claude_config_dir: Optional[str] = None,
    claude_cli_identity: Optional[str] = None,
) -> dict:
    """Build a deterministic child environment without exposing credentials in artifacts."""
    child = dict(os.environ)
    for key in INHERITED_CLAUDE_IDENTITY_KEYS:
        child.pop(key, None)
    if claude_cli_identity is not None:
        if not _TRUTHFUL_CLAUDE_CLI_USER_AGENT.fullmatch(claude_cli_identity):
            raise ValueError(
                "claude_cli_identity must identify the real CLI as claude-cli/<semantic-version>"
            )
        child["ANTHROPIC_CUSTOM_HEADERS"] = f"User-Agent: {claude_cli_identity}"
    if readiness.credential_source == "settings-env":
        settings_env = _read_env_block(settings_path)
        for key in PROXY_ENV_KEYS:
            value = settings_env.get(key)
            if not value:
                raise ValueError(f"configured {key} disappeared before invocation")
            child[key] = value
        if claude_config_dir:
            child["CLAUDE_CONFIG_DIR"] = claude_config_dir
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
    claude_executable: str = "claude",
    model: Optional[str] = None,
) -> list:
    """Assemble the unattended full-access `claude -p` argv.

    The request prompt is intentionally excluded from argv and sent through
    stdin by `run_review`, avoiding argument-size and flag-parsing hazards.
    Every gate starts a fresh session. Re-review requests must carry prior
    findings and new evidence explicitly rather than resuming hidden context.
    """
    argv = [
        claude_executable,
        "-p",
        "--output-format",
        "json",
        "--input-format",
        "text",
        "--permission-mode",
        "bypassPermissions",
        "--dangerously-skip-permissions",
    ]
    requested_model = validate_requested_model(model)
    if requested_model is not None:
        argv.append(f"--model={requested_model}")
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
    if status == "success" and not has_review_verdict(envelope.get("result")):
        status = "other_error"
    text = envelope.get("result") if status == "success" else None
    effective_exit_code = exit_code if status == "success" or exit_code != 0 else 1
    return ReviewResult(
        status=status,
        text=text,
        envelope=envelope,
        exit_code=effective_exit_code,
    )

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
    runner: Callable = subprocess.run,
    version_runner: Callable = subprocess.run,
    timeout_seconds: float = 600,
    max_budget_usd: Optional[float] = None,
    use_local_claude_cli_identity: bool = False,
    budget_help_runner: Optional[Callable] = None,
    model: Optional[str] = None,
) -> ReviewResult:
    """End-to-end single review gate with all guards applied.

    Order: readiness -> fixed caps -> reserve attempt -> invoke -> classify ->
    log cost -> commit success. A started call consumes an attempt even when
    the provider fails, preventing unbounded billable retries.
    """
    sensitive_values = _known_sensitive_values(settings_path, explicit_env)
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
    if (
        not isinstance(max_budget_usd, (int, float))
        or isinstance(max_budget_usd, bool)
        or max_budget_usd <= 0
    ):
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "budget_required",
            "a positive user-approved max_budget_usd is required before invocation",
            request_prompt,
            sensitive_values,
        )
    if not claude_available():
        return gate_failure_result(
            handoff_dir,
            gate_id,
            "claude_unavailable",
            "claude CLI is not available on PATH",
            request_prompt,
            sensitive_values,
        )
    claude_identity = None
    claude_executable = "claude"
    if use_local_claude_cli_identity:
        try:
            local_cli = discover_claude_cli_identity(version_runner=version_runner)
        except ValueError as exc:
            return gate_failure_result(
                handoff_dir,
                gate_id,
                "setup_failure",
                str(exc),
                request_prompt,
                sensitive_values,
            )
        claude_identity = local_cli.user_agent
        claude_executable = local_cli.executable
    # Optional preflight: only run when the caller injects a help runner (the
    # CLI does; hermetic unit tests do not). A conclusive "unsupported" turns a
    # cryptic non-success envelope into a clear upgrade message; an
    # inconclusive probe never blocks.
    if budget_help_runner is not None:
        supported_flags = claude_supported_flags(
            executable=claude_executable, help_runner=budget_help_runner
        )
        if supported_flags is not None and MAX_BUDGET_FLAG not in supported_flags:
            return gate_failure_result(
                handoff_dir,
                gate_id,
                "setup_failure",
                f"local claude does not support {MAX_BUDGET_FLAG}; upgrade the claude CLI",
                request_prompt,
                sensitive_values,
            )
        if requested_model is not None and supported_flags is not None and MODEL_FLAG not in supported_flags:
            return gate_failure_result(
                handoff_dir,
                gate_id,
                "setup_failure",
                f"local claude does not support {MODEL_FLAG}; upgrade the claude CLI",
                request_prompt,
                sensitive_values,
            )
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

            argv = build_command(
                request_prompt,
                add_dirs,
                max_budget_usd=max_budget_usd,
                claude_executable=claude_executable,
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
            with tempfile.TemporaryDirectory(prefix="cross-agent-review-claude-") as config_dir:
                child_env = resolve_subprocess_env(
                    readiness,
                    explicit_env,
                    settings_path=settings_path,
                    claude_config_dir=config_dir,
                    claude_cli_identity=claude_identity,
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
                result = run_review(
                    argv,
                    runner=runner,
                    env=child_env,
                    timeout_seconds=timeout_seconds,
                    request_prompt=build_reviewer_prompt(request_prompt),
                )
            try:
                log_cost(
                    result.envelope,
                    cost_log_path,
                    gate_id,
                    time.monotonic() - start,
                    extra={"requested_model": requested_model},
                )
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
    parser = argparse.ArgumentParser(description="Run a fail-closed any-primary -> ClaudeCode review gate")
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--add-dir", action="append", default=[])
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--marker-path", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--artifact-key", required=True)
    parser.add_argument("--cost-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--settings", default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--max-budget-usd", type=float, required=True)
    parser.add_argument("--model")
    parser.add_argument(
        "--gateway-compat-cli-identity",
        action="store_true",
        help=(
            "After explicit approval, derive a truthful plain claude-cli identity "
            "from the locally resolved claude binary; omitted by default"
        ),
    )
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
        timeout_seconds=args.timeout_seconds,
        max_budget_usd=args.max_budget_usd,
        use_local_claude_cli_identity=args.gateway_compat_cli_identity,
        budget_help_runner=subprocess.run,
        model=args.model,
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
