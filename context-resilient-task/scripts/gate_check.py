#!/usr/bin/env python3
"""Non-blocking staleness reminder for the end of a turn.

Runs on the Claude Code `Stop` hook. If the working tree has changes that are
newer than the last snapshot, it prints a reminder to flush state to the MRS.
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
    project_root_for,
    read_state,
    snapshot_mtime,
    source_changes,
)

MARKER = "🗂  context-resilient-task"


def stale_reminder(mrs_dir: Path) -> str | None:
    """Return a reminder string if the MRS is behind the working tree."""
    state = read_state(mrs_dir)
    if state.get("exists") and state["status"].strip().lower() == "completed":
        return None  # nothing to nag about on a finished task

    root = project_root_for(mrs_dir)
    changes = source_changes(root)
    if not changes:
        return None

    snap = snapshot_mtime(mrs_dir)
    newest = newest_mtime(root, changes)
    # newest == 0 means deletions/missing files -> still drift, don't suppress.
    if snap is not None and 0 < newest <= snap:
        return None  # snapshot already newer than every changed file

    preview = ", ".join(changes[:5]) + (" …" if len(changes) > 5 else "")
    reason = "snapshot.md is missing" if snap is None else "snapshot.md is older than your latest changes"
    return (
        f"{MARKER} — before ending: {reason}. "
        f"{len(changes)} uncommitted change(s): {preview}. "
        f"Update {mrs_dir.name}/snapshot.md and append to progress.md so the next session can recover."
    )


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
        reminders = [r for mrs in find_mrs_dirs(start) if (r := stale_reminder(mrs))]
        if reminders:
            print("\n".join(reminders))
        return 0
    except Exception:  # noqa: BLE001 — hook safety: a Stop hook must never block
        return 0


if __name__ == "__main__":
    sys.exit(main())
