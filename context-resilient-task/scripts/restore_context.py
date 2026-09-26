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
    python restore_context.py [start_dir] --mrs <mrs_dir>   # restore one chosen MRS
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
    work_root_for,
    ledger_root_for,
    read_mrs_metadata,
    read_state,
    read_context_entries,
    read_context_entry_records,
    utils_records,
    format_context_entry,
    snapshot_mtime,
    source_changes,
    mrs_updated_mtime,
    bounded_text,
    ledger_label,
    ledger_tail,
    sdd_ledgers,
)

MARKER = "🗂  context-resilient-task"
SDD_HINT = ".superpowers/sdd/"


def drift_note(mrs_dir: Path, root: Path) -> str | None:
    """Warn when source files in the current worktree changed after the last snapshot."""
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


def render_single(mrs_dir: Path, start: Path | None = None) -> str:
    state = read_state(mrs_dir)
    root = work_root_for(mrs_dir, start)
    lines = [f"{MARKER} — restored from disk: {mrs_dir}", ""]
    if root != mrs_dir.parent:
        lines.append(f"(shared MRS; current worktree: {root})")
        lines.append("")

    if not state["exists"]:
        lines.append("task_state.md is MISSING — Tier 0 incomplete. Run the initialization wizard.")
        return "\n".join(lines)

    lines.append("## Reconstructed Task State")
    lines.append("")
    lines.append(f"### Goal (from task_state.md, updated {state['updated']})")
    lines.append(bounded_text(state["goal"], 700))
    lines.append("")
    lines.append(f"### Status\n{state['status']}")
    lines.append("")
    lines.append("### Active Todos (from task_state.md)")
    todos = state["active_todos"] if is_meaningful(state["active_todos"]) else "_(none)_"
    lines.append(bounded_text(todos, 1200))
    lines.append("")
    if is_meaningful(state["current_phase"]):
        lines.append(f"### Current Phase\n{state['current_phase']}")
        lines.append("")
    lines.append("### Next Required Action")
    lines.append(bounded_text(state["next_action"], 700) if is_meaningful(state["next_action"]) else "(not recorded — read plan.md)")
    lines.append("")

    artifacts = list_artifacts(mrs_dir)
    lines.append("### Current Artifacts")
    lines.extend(f"- {name} (updated: {ts})" for name, ts in artifacts)
    missing_tier0 = [n for n in ("task_state.md", "plan.md", "snapshot.md") if not (mrs_dir / n).exists()]
    if missing_tier0:
        lines.append("")
        lines.append(f"⚠ Missing Tier 0: {', '.join(missing_tier0)} — recovery is incomplete.")

    drift = drift_note(mrs_dir, root)
    if drift:
        lines.append("")
        lines.append(drift)

    ledgers = sdd_ledgers(mrs_dir, ledger_root_for(mrs_dir, start))
    if ledgers:
        lines.append("")
        lines.append("### superpowers Execution Ledger (in-plan task progress: ledger + git log win over MRS prose)")
        for item in ledgers[:2]:
            lines.append(f"- {ledger_label(item)}")
            lines.extend(f"    {line}" for line in ledger_tail(item["ledger"]).splitlines())
        if len(ledgers) > 2:
            lines.append(f"- … {len(ledgers) - 2} more in-flight ledger(s) under {ledgers[0]['ledger'].parent.parent}")

    context_blocks = (
        ("Stable Decisions", "decisions.md"),
        ("Key Findings", "findings.md"),
        ("Utilities", "utils.md"),
    )
    for title, filename in context_blocks:
        if filename == "utils.md":
            entries = [format_context_entry(record) for record in utils_records(mrs_dir)]
        else:
            entries = read_context_entries(mrs_dir, filename)
        if entries:
            lines.append("")
            lines.append(f"### {title} (latest entries from {filename})")
            for entry in entries:
                lines.append("\n".join("### " + line.lstrip("#").strip() if line.startswith("# ") else ("### " + line[3:] if line.startswith("## ") else line) for line in entry.splitlines()))

    if state["status"].strip().lower() == "completed":
        lines.append("")
        lines.append("ℹ Task is marked COMPLETED — prompt to archive, start a new task, or reopen.")

    lines.append("")
    lines.append("Reminder: reconstruct facts from these artifacts, cite sources, mark unknowns as Unknown.")
    return bounded_text("\n".join(lines))


def render_multiple(mrs_dirs: list[Path], start: Path | None = None) -> str:
    mrs_dirs = sorted(mrs_dirs, key=mrs_updated_mtime, reverse=True)
    entries = [read_mrs_metadata(p) for p in mrs_dirs]
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
    where = start or mrs_dirs[0].parent
    lines.append(f"After choosing, restore it fully: python restore_context.py {where} --mrs <mrs_dir>")
    if mrs_dirs:
        # Ledgers belong to plans, not to a specific MRS; index them without
        # deciding which task they serve.
        ledgers = sdd_ledgers(mrs_dirs[0], ledger_root_for(mrs_dirs[0], start))
        if ledgers:
            lines.append("")
            lines.append("### In-flight superpowers ledgers (match to the chosen task)")
            for item in ledgers[:3]:
                last = ledger_tail(item["ledger"], max_lines=1, max_chars=160)
                lines.append(f"- {item['plan']} — {SDD_HINT}{item['ledger'].parent.name}/progress.md — last: {last}")
            if len(ledgers) > 3:
                lines.append(f"- … {len(ledgers) - 3} more")
    if entries:
        latest = mrs_dirs[0]
        lines.append("")
        lines.append("### Latest MRS Context (bounded)")
        for filename, title in (("decisions.md", "Stable Decisions"), ("findings.md", "Key Findings"), ("utils.md", "Utilities")):
            records = (utils_records(latest, max_chars=900) if filename == "utils.md"
                       else read_context_entry_records(latest, filename, limit=2, max_chars=700))
            if records:
                lines.append(f"#### {title}")
                for record in records:
                    formatted = format_context_entry(record, 700)
                    lines.append("\n".join("### " + line[3:] if line.startswith("## ") else line for line in formatted.splitlines()))
    output = "\n".join(lines)
    if len(output) > 4000:
        return output[:3957].rstrip() + "\n… (digest truncated to 4000 characters)"
    return output


def build_output(start: Path, as_json: bool, mrs: Path | None = None) -> str:
    mrs_dirs = [mrs] if mrs is not None else find_mrs_dirs(start)
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
            payload["drift"] = drift_note(mrs_dirs[0], work_root_for(mrs_dirs[0], start))
        return json.dumps(payload, indent=2, ensure_ascii=False)

    if len(mrs_dirs) == 1:
        return render_single(mrs_dirs[0], start)
    return render_multiple(mrs_dirs, start)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconstruct task state from the on-disk MRS")
    parser.add_argument("start", nargs="?", default=".", help="Starting directory (default: CWD)")
    parser.add_argument("--hook", default=None, help="Hook event name; forces exit 0 on any error")
    parser.add_argument("--json", action="store_true", help="Emit JSON for agent consumption")
    parser.add_argument("--mrs", default=None, help="Restore this MRS directory instead of discovering one")
    parser.add_argument("--tag", default=None, help="Ignored; detection marker embedded by install_hooks.py")
    args = parser.parse_args()
    configure_utf8_stdout()

    try:
        start = Path(args.start).resolve()
        if not start.is_dir():
            return 0 if args.hook else 1
        mrs = Path(args.mrs).resolve() if args.mrs else None
        if mrs is not None and not mrs.is_dir():
            print(f"restore_context error: {mrs} is not a directory", file=sys.stderr)
            return 0 if args.hook else 1
        output = build_output(start, args.json, mrs)
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
