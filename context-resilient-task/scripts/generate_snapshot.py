#!/usr/bin/env python3
"""
Generate a timestamped snapshot of current task state.

Usage:
    python generate_snapshot.py [--archive] [directory]

Options:
    --archive    Save to snapshots/ directory with timestamp, keep snapshot.md updated
"""

from __future__ import annotations  # Python 3.7+ compatible type hints

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

SKILL_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_TEMPLATE_PATH = SKILL_ROOT / "assets" / "snapshot.template.md"
TEMPLATE_DOCS_MARKER = "<!--END_TEMPLATE_DOCS-->\n"


def extract_section(content: str, section_header: str) -> str:
    """Extract content under a specific markdown header.

    Matches the header exactly (after stripping) to avoid false matches
    like '## Goal Statement' when looking for '## Goal'.
    """
    lines = content.split("\n")
    in_section = False
    section_content = []
    target = section_header.strip()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if stripped == target:
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
            "open_questions": "(unknown)",
        }

    content = task_state_path.read_text(encoding="utf-8")

    return {
        "goal": extract_section(content, "## Goal"),
        "current_phase": extract_section(content, "## Current Phase"),
        "next_action": extract_section(content, "## Next Action"),
        "open_questions": extract_section(content, "## Open Questions"),
    }


def read_progress(mrs_dir: Path, last_n_lines: int = 10) -> str:
    """Read recent progress entries."""
    progress_path = mrs_dir / "progress.md"

    if not progress_path.exists():
        return "(progress.md not found)"

    content = progress_path.read_text(encoding="utf-8")
    lines = [
        line
        for line in content.split("\n")
        if line.strip()
        and not line.lstrip().startswith("#")
        and not line.lstrip().startswith("<!--")
    ]
    recent = lines[-last_n_lines:] if len(lines) > last_n_lines else lines

    return "\n".join(recent) or "- (No recent progress)"


def list_recent_files(project_root: Path, hours: int = 24) -> list[str]:
    """List files modified in last N hours."""

    cutoff = datetime.now() - timedelta(hours=hours)
    recent_files = []

    # Look for common code directories
    search_dirs = ["src", "tests", "lib", "app", "backend", "frontend"]

    for search_dir in search_dirs:
        dir_path = project_root / search_dir
        if not dir_path.exists():
            continue

        for item in dir_path.rglob("*"):
            if item.is_file():
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime > cutoff:
                    recent_files.append(str(item.relative_to(project_root)))

    return recent_files[:20]  # Limit to 20 files


def build_next_session_notes(state: dict) -> str:
    """Build Next Session Should Know from task state fields."""
    notes = []

    # Include open questions
    open_q = state.get("open_questions", "")
    normalized_open_q = open_q.strip().lower()
    if normalized_open_q and normalized_open_q not in {
        "(no content)",
        "(unknown)",
        "_(none)_",
        "none",
        "(none)",
    }:
        for line in open_q.split("\n"):
            line = line.strip()
            if line and line != "(No content)":
                notes.append(line if line.startswith("- ") else f"- {line}")

    # Include next action
    next_action = state.get("next_action", "")
    if next_action and next_action != "(No content)" and next_action != "(unknown)":
        notes.append(f"- Next action: {next_action.strip()}")

    return "\n".join(notes) if notes else "- (No specific notes — review task_state.md)"


def load_snapshot_template() -> str:
    """Load snapshot template from assets/. Strips internal docs preamble."""
    if not SNAPSHOT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Snapshot template missing at {SNAPSHOT_TEMPLATE_PATH}. "
            "Reinstall context-resilient-task skill."
        )
    raw = SNAPSHOT_TEMPLATE_PATH.read_text(encoding="utf-8")
    if TEMPLATE_DOCS_MARKER in raw:
        _, _, body = raw.partition(TEMPLATE_DOCS_MARKER)
        return body
    return raw


def normalize_blockers(raw: str) -> str:
    """Normalize Open Questions content into a Blockers bullet list."""
    normalized = raw.strip().lower()
    if not normalized or normalized in {"(no content)", "(unknown)", "_(none)_", "none", "(none)"}:
        return "- (None)"
    return raw


def infer_project_root(mrs_dir: Path) -> Path:
    """Infer project root from an MRS directory.

    Directories named .task-state or .task-state-<slug> scan the parent
    project. Otherwise preserve the historical behavior and scan the
    provided directory.
    """
    if mrs_dir.name == ".task-state" or mrs_dir.name.startswith(".task-state-"):
        return mrs_dir.parent
    return mrs_dir


def generate_snapshot(mrs_dir: Path, project_root: Path | None = None) -> str:
    """Generate snapshot content from current state."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    project_root = project_root or infer_project_root(mrs_dir)

    # Read task state
    state = read_task_state(mrs_dir)

    # Read recent progress
    recent_progress = read_progress(mrs_dir)

    # List recent files
    files = list_recent_files(project_root)
    files_str = "\n".join(f"- {f}" for f in files) if files else "- (No recent changes detected)"

    # Build context
    context = f"Working on {state['current_phase']} - Goal: {state['goal']}"

    # Build next session notes from actual state
    next_session_notes = build_next_session_notes(state)

    # Render via assets/snapshot.template.md (no inline duplication)
    template = load_snapshot_template()
    return template.format(
        timestamp=timestamp,
        context=context,
        recent_progress=recent_progress,
        current_focus=state["next_action"],
        blockers=normalize_blockers(state.get("open_questions", "")),
        files_modified=files_str,
        next_session_notes=next_session_notes,
    )


def save_snapshot(directory: Path, content: str, archive: bool = False):
    """Save snapshot to file."""
    # Always overwrite snapshot.md
    snapshot_path = directory / "snapshot.md"
    snapshot_path.write_text(content, encoding="utf-8")
    print(f"Updated: {snapshot_path}")

    # Optionally archive
    if archive:
        snapshots_dir = directory / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        archive_path = snapshots_dir / f"snapshot_{timestamp}.md"
        archive_path.write_text(content, encoding="utf-8")
        print(f"Archived: {archive_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate task snapshot")
    parser.add_argument("--archive", action="store_true", help="Archive snapshot to snapshots/ directory")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root for scanning modified source files (default: parent of .task-state)",
    )
    parser.add_argument("directory", nargs="?", default=".", help="MRS directory (default: current)")

    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    project_root = Path(args.project_root).resolve() if args.project_root else None

    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)
    if project_root and not project_root.is_dir():
        print(f"Error: {project_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Generating snapshot for: {directory}\n")

    # Generate snapshot
    snapshot = generate_snapshot(directory, project_root=project_root)

    # Save (overwrites existing snapshot.md)
    save_snapshot(directory, snapshot, archive=args.archive)

    print("\nSnapshot generated successfully")
    print("\nPreview:")
    print("=" * 60)
    print(snapshot[:500] + "..." if len(snapshot) > 500 else snapshot)
    print("=" * 60)


if __name__ == "__main__":
    main()
