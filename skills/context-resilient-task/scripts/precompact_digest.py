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
    resolve_start,
    find_mrs_dirs,
    is_meaningful,
    read_state,
    mrs_updated_mtime,
    bounded_text,
    ledger_root_for,
    ledger_label,
    ledger_tail,
    sdd_ledgers,
)
from _context_recall import balanced_sections, clip, context_sections  # noqa: E402

MARKER = "🗂  context-resilient-task"
MAX_DIGEST_CHARS = 4000


def render(mrs_dir: Path, start: Path | None = None, budget: int = 3999) -> str:
    state = read_state(mrs_dir)
    lines = [
        f"{MARKER} — pre-compaction digest. Full state persists on disk at {mrs_dir}.",
        "Preserve the following across compaction:",
    ]
    if not state["exists"]:
        lines.append(f"- task_state.md missing; recover from {mrs_dir} after compaction.")
        return "\n".join(lines)

    sections = [("", "\n".join(lines), ""),
                ("### Goal", state['goal'], "task_state.md"),
                ("### Status", state['status'], "task_state.md")]
    if is_meaningful(state["current_phase"]):
        sections.append(("### Current Phase", state['current_phase'], "task_state.md"))
    todos = bounded_text(state["active_todos"], 1200) if is_meaningful(state["active_todos"]) else "_(none)_"
    sections.append(("### Active Todos", todos, "task_state.md"))
    if is_meaningful(state["next_action"]):
        sections.append(("### Next action", state['next_action'], "task_state.md"))
    ledger_lines = []
    ledgers = sdd_ledgers(mrs_dir, ledger_root_for(mrs_dir, start))
    for item in ledgers[:1]:
        ledger_lines.append(f"- superpowers ledger (in-plan progress): {ledger_label(item)}")
        ledger_lines.extend(f"    {line}" for line in ledger_tail(item["ledger"], max_lines=3, max_chars=300).splitlines())
    if len(ledgers) > 1:
        ledger_lines.append(f"- … {len(ledgers) - 1} more in-flight ledger(s); restore_context.py lists them")
    if ledger_lines:
        sections.append(("### Execution Ledger", "\n".join(ledger_lines), ".superpowers/sdd/"))
    return balanced_sections(sections + context_sections(mrs_dir), budget)


def restore_hint(mrs_dir: Path, start: Path) -> str:
    # Keep the current worktree as the start: drift and ledgers are read from
    # there, while the (possibly shared) MRS is named explicitly.
    return f"After compaction, run: python restore_context.py {start} --mrs {mrs_dir}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a pre-compaction survival digest from the MRS")
    parser.add_argument(
        "start",
        nargs="?",
        default=None,
        help="Starting directory (default: CWD; if no MRS is found there, "
             "$GROK_WORKSPACE_ROOT then $CLAUDE_PROJECT_DIR)",
    )
    parser.add_argument("--hook", default=None, help="Hook event name; forces exit 0 on any error")
    parser.add_argument("--tag", default=None, help="Ignored; detection marker embedded by install_hooks.py")
    args = parser.parse_args()
    configure_utf8_stdout()

    try:
        start = resolve_start(args.start)
        if not start.is_dir():
            return 0 if args.hook else 1
        mrs_dirs = find_mrs_dirs(start)
        if not mrs_dirs:
            return 0
        ordered = sorted(mrs_dirs, key=mrs_updated_mtime, reverse=True)
        footer: list[str] = []
        if len(ordered) > 1:
            compact_rows = ["Other MRS (metadata only):"]
            for mrs_dir in ordered[1:]:
                state = read_state(mrs_dir)
                compact_rows.append(f"- {mrs_dir.name}: {state.get('status', '(unknown)')} — {state.get('goal', '(unknown)')[:80]}")
            footer.append(clip("\n".join(compact_rows), 500, "other task_state.md files"))
        footer.append(restore_hint(ordered[0], start))
        footer_text = "\n".join(footer)
        available = max(0, MAX_DIGEST_CHARS - len(footer_text) - 3)
        latest = render(ordered[0], start, budget=available)
        print(latest.rstrip() + "\n\n" + footer_text)
        return 0
    except Exception as exc:  # noqa: BLE001 — hook safety
        if args.hook:
            return 0
        print(f"precompact_digest error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
