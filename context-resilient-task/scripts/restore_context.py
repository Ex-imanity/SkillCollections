#!/usr/bin/env python3
"""Reconstruct task state from the on-disk MRS.

Designed to run at session start (Claude Code `SessionStart` hook), after
`/clear`, or manually. Discovers the MRS from the current directory, then
prints a compact "Reconstructed Task State" block that any agent can read.

Contract (so it is safe to install globally):
- No MRS discoverable  -> print nothing, exit 0.
- Any unexpected error in --hook mode -> swallow, exit 0 (never break a session).

Usage:
    python restore_context.py [start_dir] [--hook session-start] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _state_probe import (  # noqa: E402
    configure_utf8_stdout,
    find_mrs_dirs,
    is_meaningful,
    list_artifacts,
    newest_mtime,
    project_root_for,
    read_mrs_metadata,
    read_state,
    snapshot_mtime,
    source_changes,
)

MARKER = "🗂  context-resilient-task"


def drift_note(mrs_dir: Path) -> str | None:
    """Warn when source files changed after the last snapshot."""
    root = project_root_for(mrs_dir)
    changes = source_changes(root)
    if not changes:
        return None
    snap = snapshot_mtime(mrs_dir)
    newest = newest_mtime(root, changes)
    # Suppress only when we can positively confirm the snapshot is newer than
    # every changed file. newest == 0 means the changes are deletions/missing
    # files, which still count as drift.
    if snap is not None and 0 < newest <= snap:
        return None
    preview = ", ".join(changes[:5]) + (" …" if len(changes) > 5 else "")
    return (
        f"⚠ {len(changes)} uncommitted change(s) since the last snapshot "
        f"({preview}). Reconcile progress.md / snapshot.md against the working tree."
    )


def render_single(mrs_dir: Path) -> str:
    state = read_state(mrs_dir)
    lines = [f"{MARKER} — restored from disk: {mrs_dir}", ""]

    if not state["exists"]:
        lines.append("task_state.md is MISSING — Tier 0 incomplete. Run the initialization wizard.")
        return "\n".join(lines)

    lines.append("## Reconstructed Task State")
    lines.append("")
    lines.append(f"### Goal (from task_state.md, updated {state['updated']})")
    lines.append(state["goal"])
    lines.append("")
    lines.append(f"### Status\n{state['status']}")
    lines.append("")
    lines.append("### Active Todos (from task_state.md)")
    lines.append(state["active_todos"] if is_meaningful(state["active_todos"]) else "_(none)_")
    lines.append("")
    if is_meaningful(state["current_phase"]):
        lines.append(f"### Current Phase\n{state['current_phase']}")
        lines.append("")
    lines.append("### Next Required Action")
    lines.append(state["next_action"] if is_meaningful(state["next_action"]) else "(not recorded — read plan.md)")
    lines.append("")

    artifacts = list_artifacts(mrs_dir)
    lines.append("### Current Artifacts")
    lines.extend(f"- {name} (updated: {ts})" for name, ts in artifacts)
    missing_tier0 = [n for n in ("task_state.md", "plan.md", "snapshot.md") if not (mrs_dir / n).exists()]
    if missing_tier0:
        lines.append("")
        lines.append(f"⚠ Missing Tier 0: {', '.join(missing_tier0)} — recovery is incomplete.")

    drift = drift_note(mrs_dir)
    if drift:
        lines.append("")
        lines.append(drift)

    if state["status"].strip().lower() == "completed":
        lines.append("")
        lines.append("ℹ Task is marked COMPLETED — prompt to archive, start a new task, or reopen.")

    lines.append("")
    lines.append("Reminder: reconstruct facts from these artifacts, cite sources, mark unknowns as Unknown.")
    return "\n".join(lines)


def render_multiple(mrs_dirs: list[Path]) -> str:
    entries = sorted(
        (read_mrs_metadata(p) for p in mrs_dirs),
        key=lambda e: e["updated"] or 0,
        reverse=True,
    )
    lines = [
        f"{MARKER} — {len(entries)} task states found; DO NOT assume which is current.",
        "",
        "| * | Name | Status | Updated | Goal |",
        "|---|------|--------|---------|------|",
    ]
    for index, entry in enumerate(entries):
        marker = "*" if index == 0 else " "
        goal = entry["goal"][:60] + ("…" if len(entry["goal"]) > 60 else "")
        lines.append(
            f"| {marker} | {entry['name']} | {entry['status']} | {entry['updated_human']} | {goal} |"
        )
    lines.append("")
    lines.append("* = most recently updated (recommended). ASK the user which task to resume before continuing.")
    return "\n".join(lines)


def build_output(start: Path, as_json: bool) -> str:
    mrs_dirs = find_mrs_dirs(start)
    if not mrs_dirs:
        return ""

    if as_json:
        payload = {
            "count": len(mrs_dirs),
            "mrs": [read_mrs_metadata(p) for p in mrs_dirs],
        }
        if len(mrs_dirs) == 1:
            payload["state"] = read_state(mrs_dirs[0])
            payload["artifacts"] = [
                {"name": n, "updated": t} for n, t in list_artifacts(mrs_dirs[0])
            ]
            payload["drift"] = drift_note(mrs_dirs[0])
        return json.dumps(payload, indent=2, ensure_ascii=False)

    if len(mrs_dirs) == 1:
        return render_single(mrs_dirs[0])
    return render_multiple(mrs_dirs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruct task state from the on-disk MRS")
    parser.add_argument("start", nargs="?", default=".", help="Starting directory (default: CWD)")
    parser.add_argument("--hook", default=None, help="Hook event name; forces exit 0 on any error")
    parser.add_argument("--json", action="store_true", help="Emit JSON for agent consumption")
    args = parser.parse_args()
    configure_utf8_stdout()

    try:
        start = Path(args.start).resolve()
        if not start.is_dir():
            return 0 if args.hook else 1
        output = build_output(start, args.json)
        if output:
            print(output)
        return 0
    except Exception as exc:  # noqa: BLE001 — hook safety: never break a session
        if args.hook:
            return 0
        print(f"restore_context error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
