#!/usr/bin/env python3
"""Emit a minimal survival digest right before context compaction.

Runs on the Claude Code `PreCompact` hook. It is READ-ONLY: it never rewrites
snapshot.md (that stays the agent's job), it just surfaces the few facts the
compaction summarizer must preserve so they survive into the compacted context.
The authoritative state already lives on disk in the MRS.

Contract: no MRS -> print nothing, exit 0. Any error in --hook mode -> exit 0.

Usage:
    python precompact_digest.py [start_dir] [--hook precompact]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _state_probe import (  # noqa: E402
    configure_utf8_stdout,
    find_mrs_dirs,
    is_meaningful,
    read_state,
)

MARKER = "🗂  context-resilient-task"


def render(mrs_dir: Path) -> str:
    state = read_state(mrs_dir)
    lines = [
        f"{MARKER} — pre-compaction digest. Full state persists on disk at {mrs_dir}.",
        "Preserve the following across compaction:",
    ]
    if not state["exists"]:
        lines.append(f"- task_state.md missing; recover from {mrs_dir} after compaction.")
        return "\n".join(lines)

    lines.append(f"- Goal: {state['goal']}")
    lines.append(f"- Status: {state['status']}")
    if is_meaningful(state["current_phase"]):
        lines.append(f"- Current phase: {state['current_phase']}")
    todos = state["active_todos"] if is_meaningful(state["active_todos"]) else "_(none)_"
    lines.append("- Active todos:")
    lines.extend(f"    {line.rstrip()}" for line in todos.splitlines() if line.strip())
    if is_meaningful(state["next_action"]):
        lines.append(f"- Next action: {state['next_action']}")
    lines.append(f"- After compaction, run restore_context.py in {mrs_dir.parent} to rehydrate.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a pre-compaction survival digest from the MRS")
    parser.add_argument("start", nargs="?", default=".", help="Starting directory (default: CWD)")
    parser.add_argument("--hook", default=None, help="Hook event name; forces exit 0 on any error")
    args = parser.parse_args()
    configure_utf8_stdout()

    try:
        start = Path(args.start).resolve()
        if not start.is_dir():
            return 0 if args.hook else 1
        mrs_dirs = find_mrs_dirs(start)
        if not mrs_dirs:
            return 0
        blocks = [render(mrs_dir) for mrs_dir in mrs_dirs]
        print("\n\n".join(blocks))
        return 0
    except Exception as exc:  # noqa: BLE001 — hook safety
        if args.hook:
            return 0
        print(f"precompact_digest error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
