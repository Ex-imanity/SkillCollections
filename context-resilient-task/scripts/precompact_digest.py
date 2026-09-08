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
    read_context_entries,
    read_context_entry_records,
    format_context_entry,
    mrs_updated_mtime,
    bounded_text,
)

MARKER = "🗂  context-resilient-task"
MAX_DIGEST_CHARS = 4000


def render(mrs_dir: Path) -> str:
    state = read_state(mrs_dir)
    lines = [
        f"{MARKER} — pre-compaction digest. Full state persists on disk at {mrs_dir}.",
        "Preserve the following across compaction:",
    ]
    if not state["exists"]:
        lines.append(f"- task_state.md missing; recover from {mrs_dir} after compaction.")
        return "\n".join(lines)

    lines.append(f"- Goal: {bounded_text(state['goal'], 700)}")
    lines.append(f"- Status: {bounded_text(state['status'], 200)}")
    if is_meaningful(state["current_phase"]):
        lines.append(f"- Current phase: {bounded_text(state['current_phase'], 500)}")
    todos = bounded_text(state["active_todos"], 1200) if is_meaningful(state["active_todos"]) else "_(none)_"
    lines.append("- Active todos:")
    lines.extend(f"    {line.rstrip()}" for line in todos.splitlines() if line.strip())
    if is_meaningful(state["next_action"]):
        lines.append(f"- Next action: {bounded_text(state['next_action'], 700)}")
    for title, filename in (
        ("Stable decisions", "decisions.md"),
        ("Key findings", "findings.md"),
        ("Utilities", "utils.md"),
    ):
        if filename == "utils.md":
            records = [r for r in read_context_entry_records(mrs_dir, filename, limit=2, max_chars=500) if r["sensitivity"] in {"public", "internal"}]
            entries = [format_context_entry(r, 500) for r in records]
        else:
            entries = read_context_entries(mrs_dir, filename, limit=2, max_chars=500)
        if entries:
            lines.append(f"- {title} (latest):")
            for entry in entries:
                lines.extend(f"    {line}" for line in entry.splitlines())
    lines.append(f"- After compaction, run restore_context.py in {mrs_dir.parent} to rehydrate.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a pre-compaction survival digest from the MRS")
    parser.add_argument("start", nargs="?", default=".", help="Starting directory (default: CWD)")
    parser.add_argument("--hook", default=None, help="Hook event name; forces exit 0 on any error")
    parser.add_argument("--tag", default=None, help="Ignored; detection marker embedded by install_hooks.py")
    args = parser.parse_args()
    configure_utf8_stdout()

    try:
        start = Path(args.start).resolve()
        if not start.is_dir():
            return 0 if args.hook else 1
        mrs_dirs = find_mrs_dirs(start)
        if not mrs_dirs:
            return 0
        ordered = sorted(mrs_dirs, key=mrs_updated_mtime, reverse=True)
        latest = render(ordered[0])
        footer: list[str] = []
        if len(ordered) > 1:
            compact_rows = ["Other MRS (metadata only):"]
            for mrs_dir in ordered[1:]:
                state = read_state(mrs_dir)
                compact_rows.append(f"- {mrs_dir.name}: {state.get('status', '(unknown)')} — {state.get('goal', '(unknown)')[:80]}")
            footer.extend(compact_rows)
        footer.append(f"After compaction, run restore_context.py in {ordered[0].parent} to rehydrate.")
        footer_text = "\n".join(footer)
        available = max(500, MAX_DIGEST_CHARS - len(footer_text) - 2)
        print(bounded_text(latest, available).rstrip() + "\n\n" + footer_text)
        return 0
    except Exception as exc:  # noqa: BLE001 — hook safety
        if args.hook:
            return 0
        print(f"precompact_digest error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
