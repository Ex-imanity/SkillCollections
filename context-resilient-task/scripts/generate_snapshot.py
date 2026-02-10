#!/usr/bin/env python3
"""
Generate a timestamped snapshot of current task state.

Usage:
    python generate_snapshot.py [--archive]

Options:
    --archive    Save to snapshots/ directory with timestamp, keep snapshot.md updated
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse


SNAPSHOT_TEMPLATE = """# Snapshot: {timestamp}

## Context
{context}

## Recent Progress
{progress}

## Current Focus
{current_focus}

## Blockers
{blockers}

## Files Modified
{files_modified}

## Next Session Should Know
{next_session_notes}
"""


def extract_section(content: str, section_header: str) -> str:
    """Extract content under a specific markdown header."""
    lines = content.split("\n")
    in_section = False
    section_content = []

    for line in lines:
        if line.startswith("#"):
            if section_header in line:
                in_section = True
                continue
            elif in_section:
                # Hit next section, stop
                break
        elif in_section:
            section_content.append(line)

    return "\n".join(section_content).strip() or "(No content)"


def read_task_state(directory: Path) -> dict:
    """Read task_state.md and extract key information."""
    task_state_path = directory / "task_state.md"

    if not task_state_path.exists():
        return {
            "goal": "(task_state.md not found)",
            "current_phase": "(unknown)",
            "next_action": "(unknown)",
        }

    content = task_state_path.read_text(encoding="utf-8")

    return {
        "goal": extract_section(content, "## Goal"),
        "current_phase": extract_section(content, "## Current Phase"),
        "next_action": extract_section(content, "## Next Action"),
        "open_questions": extract_section(content, "## Open Questions"),
    }


def read_progress(directory: Path, last_n_lines: int = 10) -> str:
    """Read recent progress entries."""
    progress_path = directory / "progress.md"

    if not progress_path.exists():
        return "(progress.md not found)"

    content = progress_path.read_text(encoding="utf-8")
    lines = [l for l in content.split("\n") if l.strip()]
    recent = lines[-last_n_lines:] if len(lines) > last_n_lines else lines

    return "\n".join(recent) or "(No recent progress)"


def list_recent_files(directory: Path, hours: int = 24) -> list[str]:
    """List files modified in last N hours."""
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(hours=hours)
    recent_files = []

    # Look for common code directories
    search_dirs = ["src", "tests", "lib", "app", "backend", "frontend"]

    for search_dir in search_dirs:
        dir_path = directory / search_dir
        if not dir_path.exists():
            continue

        for item in dir_path.rglob("*"):
            if item.is_file():
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime > cutoff:
                    recent_files.append(str(item.relative_to(directory)))

    return recent_files[:20]  # Limit to 20 files


def generate_snapshot(directory: Path) -> str:
    """Generate snapshot content from current state."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Read task state
    state = read_task_state(directory)

    # Read recent progress
    recent_progress = read_progress(directory)

    # List recent files
    files = list_recent_files(directory)
    files_str = "\n".join(f"- {f}" for f in files) if files else "(No recent changes detected)"

    # Build context
    context = f"Working on {state['current_phase']} - Goal: {state['goal']}"

    # Build snapshot
    snapshot = SNAPSHOT_TEMPLATE.format(
        timestamp=timestamp,
        context=context,
        progress=recent_progress,
        current_focus=state["next_action"],
        blockers=state.get("open_questions", "(None)"),
        files_modified=files_str,
        next_session_notes="(To be filled by user or AI)",
    )

    return snapshot


def save_snapshot(directory: Path, content: str, archive: bool = False):
    """Save snapshot to file."""
    # Always update snapshot.md
    snapshot_path = directory / "snapshot.md"
    snapshot_path.write_text(content, encoding="utf-8")
    print(f"✅ Updated: {snapshot_path}")

    # Optionally archive
    if archive:
        snapshots_dir = directory / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        archive_path = snapshots_dir / f"snapshot_{timestamp}.md"
        archive_path.write_text(content, encoding="utf-8")
        print(f"✅ Archived: {archive_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate task snapshot")
    parser.add_argument("--archive", action="store_true", help="Archive snapshot to snapshots/ directory")
    parser.add_argument("directory", nargs="?", default=".", help="Project directory (default: current)")

    args = parser.parse_args()
    directory = Path(args.directory).resolve()

    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Generating snapshot for: {directory}\n")

    # Generate snapshot
    snapshot = generate_snapshot(directory)

    # Save
    save_snapshot(directory, snapshot, archive=args.archive)

    print("\n✅ Snapshot generated successfully")
    print("\nPreview:")
    print("=" * 60)
    print(snapshot[:500] + "..." if len(snapshot) > 500 else snapshot)
    print("=" * 60)


if __name__ == "__main__":
    main()
