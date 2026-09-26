#!/usr/bin/env python3
"""Non-blocking staleness reminder for the end of a turn.

Runs on the Claude Code `Stop` hook. If the working tree has changes that are
newer than the last snapshot, or a superpowers execution ledger advanced past
it (tasks committed, tree clean), it prints a reminder to flush state to the MRS.
It NEVER blocks: it always exits 0, so the session can end normally.

Contract: no MRS / clean tree / completed task -> print nothing, exit 0.

Usage:
    python gate_check.py [start_dir] [--hook stop]
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
    newest_mtime,
    ledger_root_for,
    work_root_for,
    read_state,
    snapshot_mtime,
    sdd_ledgers,
    source_changes,
)

MARKER = "🗂  context-resilient-task"


def stale_reminder(mrs_dir: Path, start: Path | None = None) -> str | None:
    """Return a reminder if the MRS is behind the working tree or a superpowers ledger."""
    state = read_state(mrs_dir)
    if state.get("exists") and state["status"].strip().lower() == "completed":
        return None  # nothing to nag about on a finished task

    root = work_root_for(mrs_dir, start)  # the worktree being worked in, not the MRS owner
    snap = snapshot_mtime(mrs_dir)
    reminders = []

    changes = source_changes(root)
    newest = newest_mtime(root, changes) if changes else 0.0
    # newest == 0 means deletions/missing files -> still drift, don't suppress.
    if changes and not (snap is not None and 0 < newest <= snap):
        preview = ", ".join(changes[:5]) + (" …" if len(changes) > 5 else "")
        reason = "snapshot.md is missing" if snap is None else "snapshot.md is older than your latest changes"
        reminders.append(
            f"{MARKER} — before ending: {reason}. "
            f"{len(changes)} uncommitted change(s): {preview}. "
            f"Update {mrs_dir.name}/snapshot.md and append to progress.md so the next session can recover."
        )

    # Checked independently of source drift: SDD commits every task, so its
    # progress may exist only in the ledger, clean tree or not.
    ahead = [item for item in sdd_ledgers(mrs_dir, ledger_root_for(mrs_dir, start))
             if snap is None or item["mtime"] > snap]
    if ahead:
        reminders.append(
            f"{MARKER} — before ending: superpowers ledger for '{ahead[0]['plan']}' is newer than "
            f"{mrs_dir.name}/snapshot.md. Record plan-level progress in task_state.md / progress.md "
            "and regenerate the snapshot; the ledger is deleted when the plan finishes."
        )
    return "\n".join(reminders) or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-blocking MRS staleness reminder")
    parser.add_argument("start", nargs="?", default=".", help="Starting directory (default: CWD)")
    parser.add_argument("--hook", default=None, help="Hook event name; forces exit 0 on any error")
    parser.add_argument("--tag", default=None, help="Ignored; detection marker embedded by install_hooks.py")
    args = parser.parse_args()
    configure_utf8_stdout()

    try:
        start = Path(args.start).resolve()
        if not start.is_dir():
            return 0
        reminders = [r for mrs in find_mrs_dirs(start) if (r := stale_reminder(mrs, start))]
        if reminders:
            print("\n".join(reminders))
        return 0
    except Exception:  # noqa: BLE001 — hook safety: a Stop hook must never block
        return 0


if __name__ == "__main__":
    sys.exit(main())
