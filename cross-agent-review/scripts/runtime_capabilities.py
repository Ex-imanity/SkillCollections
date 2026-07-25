"""Report locally installed agent CLIs without starting a review or model call."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from typing import Callable, Optional


_AGENT_CLI_CATALOG = (
    ("claude", True, ("codex_to_claude",)),
    ("codex", True, ("claude_to_codex",)),
    ("gemini", False, ()),
    ("aider", False, ()),
    ("opencode", False, ()),
    ("goose", False, ()),
    ("amp", False, ()),
    ("copilot", False, ()),
    ("cursor-agent", False, ()),
    ("cline", False, ()),
    ("droid", False, ()),
)


def _version_line(
    executable: str,
    version_runner: Callable,
    path_env: str,
) -> tuple[Optional[str], Optional[str]]:
    """Return a bounded local version string or a diagnostic reason."""
    try:
        completed = version_runner(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            env={"PATH": path_env},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"version_probe_failed:{type(exc).__name__}"
    if completed.returncode != 0:
        return None, "version_probe_nonzero"
    output = (completed.stdout or completed.stderr or "").strip()
    if not output:
        return None, "version_probe_empty"
    return output.splitlines()[0].strip()[:160], None


def _probe_claude_max_budget(
    executable: str, version_runner: Callable, path_env: str
) -> Optional[bool]:
    """Best-effort `--max-budget-usd` support probe, isolated from import cycles.

    Imported lazily so the capability doctor keeps a minimal import surface and
    never fails just because the adapter module is unavailable. The probe runs
    with the same PATH-only environment as the version probe.
    """
    try:
        from .codex_to_claude import claude_supports_max_budget
    except Exception:  # pragma: no cover - defensive: doctor must still report
        return None
    return claude_supports_max_budget(
        executable=executable, help_runner=version_runner, env={"PATH": path_env}
    )


def discover_local_agents(
    which: Callable[[str], Optional[str]] = shutil.which,
    version_runner: Callable = subprocess.run,
    path_env: Optional[str] = None,
) -> dict:
    """Discover known local CLIs and state which ones this skill can use.

    The catalog is intentionally explicit. Finding an unsupported CLI is useful
    diagnostic evidence, but it does not grant a new review route or execute a
    model request. Version probes receive only ``PATH`` and invoke ``--version``.
    For a supported ``claude`` the doctor also checks (via ``--help``) whether
    the forward gate's required ``--max-budget-usd`` flag exists, so an
    out-of-date CLI is flagged before a gate fails closed cryptically.
    """
    resolved_path = path_env if path_env is not None else os.environ.get("PATH", "")
    agents = []
    for command, review_supported, directions in _AGENT_CLI_CATALOG:
        executable = which(command)
        entry = {
            "command": command,
            "path": executable,
            "version": None,
            "review_supported": review_supported,
            "review_directions": list(directions),
            "status": "not_found",
        }
        if executable:
            version, reason = _version_line(executable, version_runner, resolved_path)
            entry["version"] = version
            if reason:
                entry["status"] = reason
            elif review_supported:
                entry["status"] = "supported"
            else:
                entry["status"] = "detected_not_supported"
            if command == "claude" and entry["status"] == "supported":
                entry["max_budget_supported"] = _probe_claude_max_budget(
                    executable, version_runner, resolved_path
                )
        agents.append(entry)
    return {"agents": agents}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report local agent CLI capabilities without running a review"
    )
    parser.add_argument("--json", action="store_true", help="emit the capability report as JSON")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    report = discover_local_agents()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    for entry in report["agents"]:
        version = entry["version"] or "-"
        line = (
            f"{entry['command']}: {entry['status']} "
            f"version={version} path={entry['path'] or '-'}"
        )
        if "max_budget_supported" in entry:
            supported = entry["max_budget_supported"]
            label = {True: "yes", False: "NO(upgrade)", None: "unknown"}[supported]
            line += f" max-budget-usd={label}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
