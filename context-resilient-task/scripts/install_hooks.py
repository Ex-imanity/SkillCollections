#!/usr/bin/env python3
"""Install / remove the context-resilient-task auto-hooks for Claude Code or Codex.

Registers three non-blocking hooks that call this skill's own scripts:
  SessionStart -> restore_context.py    (rehydrate task state from the MRS)
  PreCompact   -> precompact_digest.py  (surface survival digest before compaction)
  Stop         -> gate_check.py         (remind to flush state if the tree drifted)

All three no-op silently when no `.task-state/` exists. Claude Code uses
settings.json; Codex uses a project-local .codex/hooks.json.

Usage:
    python install_hooks.py                 # install into ~/.claude/settings.json (global)
    python install_hooks.py --project       # install into ./.claude/settings.json
    python install_hooks.py --settings PATH # install into an explicit file
    python install_hooks.py --codex          # install into ./.codex/hooks.json
    python install_hooks.py --codex --dry-run
    python install_hooks.py --codex --uninstall
    python install_hooks.py --uninstall     # remove our hooks (respects the same target flags)
    python install_hooks.py --dry-run       # print the resulting JSON, write nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Stable token embedded in each command (as a --tag arg) so we can
# find/replace/remove our own hooks regardless of interpreter or install path.
TOKEN = "crt-auto-hook:"

# event -> script filename
EVENT_SCRIPTS = {
    "SessionStart": "restore_context.py",
    "PreCompact": "precompact_digest.py",
    "Stop": "gate_check.py",
}


def launcher() -> str:
    """Interpreter name to invoke, chosen for cross-shell portability.

    A bare name (not the quoted absolute sys.executable) is used on purpose:
    PowerShell — a possible Windows hook shell — treats a quoted first token as
    a string literal, not a command. A bare launcher runs correctly in sh, Git
    Bash, PowerShell, and cmd. The scripts are stdlib-only, so any Python 3.8+
    on PATH runs them.
    """
    return "python" if os.name == "nt" else "python3"


def build_command(event: str, script: str) -> str:
    script_path = SCRIPT_DIR / script
    hook_arg = event.lower()
    # No shell operators (no `2>/dev/null`, `; exit 0`, or `#` comment): the
    # scripts already always exit 0 in --hook mode and emit nothing on stderr,
    # so the command is a plain, portable invocation. The --tag arg carries our
    # detection token and is ignored by the scripts.
    return f'{launcher()} "{script_path}" --hook {hook_arg} --tag {TOKEN}{event}'


def is_ours(command: str) -> bool:
    return TOKEN in command


def resolve_target(args: argparse.Namespace) -> Path:
    if args.settings:
        return Path(args.settings).expanduser().resolve()
    if args.codex:
        return (Path.cwd() / ".codex" / "hooks.json").resolve()
    if args.project:
        return (Path.cwd() / ".claude" / "settings.json").resolve()
    return (Path.home() / ".claude" / "settings.json").resolve()


def target_name(args: argparse.Namespace) -> str:
    return "Codex" if args.codex else "Claude Code"


def load_settings(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Refusing to touch invalid JSON at {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"Refusing to touch {path}: top-level JSON is not an object")
    return data


def strip_ours(hooks: dict) -> None:
    """Remove only OUR individual hook commands, in place.

    Filters our commands out of each group's inner ``hooks`` list rather than
    dropping the whole group, so a group that also holds a user's hook keeps
    that hook. A group is removed only if it becomes empty.
    """
    for event in list(hooks.keys()):
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            inner = group.get("hooks")
            if isinstance(inner, list):
                filtered = [
                    h for h in inner
                    if not (isinstance(h, dict) and is_ours(h.get("command", "")))
                ]
                if not filtered and len(inner) > 0:
                    continue  # every hook in the group was ours -> drop empty group
                if len(filtered) != len(inner):
                    group = {**group, "hooks": filtered}
            kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event, None)


def add_ours(hooks: dict) -> None:
    """Append a fresh group per event (call after strip_ours for idempotency)."""
    for event, script in EVENT_SCRIPTS.items():
        group = {"hooks": [{"type": "command", "command": build_command(event, script)}]}
        hooks.setdefault(event, [])
        if not isinstance(hooks[event], list):
            raise SystemExit(f"Refusing to touch settings: hooks.{event} is not a list")
        hooks[event].append(group)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install context-resilient-task auto-hooks")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--codex", action="store_true", help="Target ./.codex/hooks.json")
    scope.add_argument("--project", action="store_true", help="Target ./.claude/settings.json")
    scope.add_argument("--global", dest="global_", action="store_true", help="Target ~/.claude/settings.json (default)")
    parser.add_argument("--settings", default=None, help="Explicit settings.json path")
    parser.add_argument("--uninstall", action="store_true", help="Remove our hooks instead of adding")
    parser.add_argument("--dry-run", action="store_true", help="Print the result, write nothing")
    args = parser.parse_args()

    target = resolve_target(args)
    settings = load_settings(target)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SystemExit(f"Refusing to touch {target}: `hooks` is not an object")

    strip_ours(hooks)  # always clear prior copies first (idempotent refresh)
    action = "Uninstalled"
    if not args.uninstall:
        add_ours(hooks)
        action = "Installed"
    if not hooks:
        settings.pop("hooks", None)

    rendered = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"

    if args.dry_run:
        print(f"# {action} {target_name(args)} hooks (dry-run) -> {target}\n")
        print(rendered)
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: never leave a truncated settings.json on crash/concurrent edit.
    tmp = target.with_name(target.name + ".crt-tmp")
    tmp.write_text(rendered, encoding="utf-8")
    tmp.replace(target)
    print(f"{action} context-resilient-task {target_name(args)} hooks -> {target}")
    if not args.uninstall:
        for event, script in EVENT_SCRIPTS.items():
            print(f"  {event:<13} -> {script}")
        print("\nHooks no-op silently when no .task-state/ exists. Remove with: --uninstall")
    return 0


if __name__ == "__main__":
    sys.exit(main())
