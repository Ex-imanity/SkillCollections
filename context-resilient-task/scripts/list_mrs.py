#!/usr/bin/env python3
"""List MRS directories discoverable from a starting directory."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _mrs_discovery import find_mrs_dirs  # noqa: E402


def extract_section(content: str, header: str) -> str:
    """Extract content under a markdown section such as `## Goal`."""
    target = f"## {header}".lower()
    in_section = False
    section_lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if stripped.lower() == target:
                in_section = True
                continue
            if in_section:
                break
        elif in_section:
            section_lines.append(line)
    value = "\n".join(section_lines).strip()
    return value or "(unknown)"


def extract_legacy_field(content: str, label: str) -> str:
    """Extract legacy single-line fields like `**Goal:** ...`."""
    for line in content.splitlines():
        stripped = line.strip()
        bold_prefix = f"**{label}:**"
        plain_prefix = f"{label}:"
        if stripped.lower().startswith(bold_prefix.lower()):
            value = stripped[len(bold_prefix):].strip()
            if value:
                return value
        if stripped.lower().startswith(plain_prefix.lower()):
            value = stripped[len(plain_prefix):].strip()
            value = value.rstrip("*").strip()
            if value:
                return value
    return "(unknown)"


def extract_field(content: str, label: str) -> str:
    """Extract current section fields, falling back to legacy single-line fields."""
    section_value = extract_section(content, label)
    if section_value != "(unknown)":
        return section_value
    return extract_legacy_field(content, label)


def read_mrs_metadata(mrs_dir: Path) -> dict:
    """Read goal, status, and updated time from task_state.md."""
    task_state = mrs_dir / "task_state.md"
    if not task_state.exists():
        return {
            "name": mrs_dir.name,
            "path": str(mrs_dir),
            "goal": "(task_state.md missing)",
            "status": "unknown",
            "updated": None,
            "updated_human": "(unknown)",
        }

    content = task_state.read_text(encoding="utf-8")
    mtime = task_state.stat().st_mtime
    return {
        "name": mrs_dir.name,
        "path": str(mrs_dir),
        "goal": extract_field(content, "Goal"),
        "status": extract_field(content, "Status"),
        "updated": mtime,
        "updated_human": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
    }


def render_table(entries: list[dict]) -> str:
    if not entries:
        return "(No MRS found in current directory or any ancestor)"

    lines = [f"{'*':<2} {'Name':<32} {'Status':<10} {'Updated':<18} Goal"]
    lines.append("-" * 100)
    for index, entry in enumerate(entries):
        marker = "*" if index == 0 and len(entries) > 1 else " "
        goal = entry["goal"][:50] + ("..." if len(entry["goal"]) > 50 else "")
        lines.append(
            f"{marker:<2} {entry['name']:<32} {entry['status']:<10} "
            f"{entry['updated_human']:<18} {goal}"
        )
    if len(entries) > 1:
        lines.append("")
        lines.append("* = most recently updated (recommended). ASK the user before assuming current task.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="List MRS directories discoverable from a path")
    parser.add_argument("start", nargs="?", default=".", help="Starting directory (default: CWD)")
    parser.add_argument("--json", action="store_true", help="Emit JSON for agent consumption")
    args = parser.parse_args()

    start = Path(args.start).resolve()
    if not start.is_dir():
        print(f"Error: {start} is not a directory", file=sys.stderr)
        return 1

    entries = [read_mrs_metadata(path) for path in find_mrs_dirs(start)]
    entries.sort(key=lambda entry: entry["updated"] or 0, reverse=True)

    if args.json:
        print(json.dumps({"mrs": entries, "count": len(entries)}, indent=2))
    else:
        print(render_table(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
