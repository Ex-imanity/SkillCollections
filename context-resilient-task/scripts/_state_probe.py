"""Shared probes for the auto-hook scripts.

Provides MRS field parsing, artifact listing, and git-drift detection so that
restore_context.py / precompact_digest.py / gate_check.py stay small and DRY.

All helpers are read-only and defensive: they never raise on a missing file,
a non-git directory, or a malformed MRS. Hook scripts rely on this so they can
run globally and stay silent when there is nothing to report.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _mrs_discovery import find_mrs_dirs  # noqa: E402
from list_mrs import extract_field, read_mrs_metadata  # noqa: E402

# Re-exported so hook scripts import everything MRS-related from one place.
__all__ = [
    "configure_utf8_stdout",
    "find_mrs_dirs",
    "read_mrs_metadata",
    "TIER0",
    "TIER1",
    "project_root_for",
    "read_state",
    "list_artifacts",
    "snapshot_mtime",
    "git_changes",
    "source_changes",
    "newest_mtime",
    "human_time",
]

TIER0 = ["task_state.md", "plan.md", "snapshot.md"]
TIER1 = ["findings.md", "progress.md", "decisions.md", "architecture.md"]

_UNKNOWN = "(unknown)"
_EMPTY_MARKERS = {"", "(unknown)", "(no content)", "_(none)_", "none", "(none)"}


def configure_utf8_stdout() -> None:
    """Best-effort force UTF-8 stdout so emoji/glyphs never raise under a `C`
    or ASCII locale (which, in hook mode, would silently drop all output)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def human_time(mtime: float | None) -> str:
    if not mtime:
        return _UNKNOWN
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def project_root_for(mrs_dir: Path) -> Path:
    """Project root that owns an MRS directory.

    `.task-state` / `.task-state-<slug>` live inside the project; any other
    directory is treated as its own root (mirrors generate_snapshot.py).
    """
    if mrs_dir.name == ".task-state" or mrs_dir.name.startswith(".task-state-"):
        return mrs_dir.parent
    return mrs_dir


def is_meaningful(value: str) -> bool:
    return value.strip().lower() not in _EMPTY_MARKERS


def read_state(mrs_dir: Path) -> dict:
    """Read the key fields from task_state.md. Never raises."""
    task_state = mrs_dir / "task_state.md"
    if not task_state.exists():
        return {"exists": False}
    try:
        content = task_state.read_text(encoding="utf-8")
    except OSError:
        return {"exists": False}
    return {
        "exists": True,
        "goal": extract_field(content, "Goal"),
        "status": extract_field(content, "Status"),
        "active_todos": extract_field(content, "Active Todos"),
        "current_phase": extract_field(content, "Current Phase"),
        "next_action": extract_field(content, "Next Action"),
        "updated": human_time(task_state.stat().st_mtime),
    }


def list_artifacts(mrs_dir: Path) -> list[tuple[str, str]]:
    """Present MRS files (Tier 0 + Tier 1) with human-readable mtimes."""
    artifacts: list[tuple[str, str]] = []
    for name in TIER0 + TIER1:
        path = mrs_dir / name
        if path.exists():
            artifacts.append((name, human_time(path.stat().st_mtime)))
    return artifacts


def snapshot_mtime(mrs_dir: Path) -> float | None:
    path = mrs_dir / "snapshot.md"
    return path.stat().st_mtime if path.exists() else None


# Directory prefixes that are the agent's own bookkeeping, not "source drift".
_IGNORED_CHANGE_PREFIXES = (".git/", ".omc/", ".task-state/")


def _parse_porcelain_z(data: str) -> list[str]:
    """Parse `git status --porcelain -z` output into current-path strings.

    NUL-delimited format needs no unquoting and preserves spaces/Unicode. For a
    rename/copy the record is ``XY <new>\\0<old>\\0``; we keep <new> and consume
    the trailing <old> token.
    """
    tokens = data.split("\0")
    changes: list[str] = []
    i = 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        if status and (status[0] in ("R", "C") or status[1] in ("R", "C")):
            i += 1  # skip the original-path token that follows a rename/copy
        if path:
            changes.append(path)
    return changes


def git_changes(root: Path) -> list[str]:
    """Relative paths of uncommitted changes; [] when not a git repo or clean.

    Uses ``-z`` (robust to spaces/Unicode/renames) and ``-uall`` so untracked
    *files* are listed individually instead of git collapsing a new directory
    into a single ``dir/`` entry (which would hide real file mtimes).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "-z", "-uall"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return _parse_porcelain_z(result.stdout)


def _is_own_bookkeeping(rel: str) -> bool:
    return (
        rel.startswith(_IGNORED_CHANGE_PREFIXES)
        or rel == ".task-state"
        or rel.startswith(".task-state-")  # sibling MRS dirs, not `.task-stateful.py`
    )


def source_changes(root: Path) -> list[str]:
    """git_changes minus the agent's own state dirs (.task-state*, .omc, .git)."""
    return [c for c in git_changes(root) if not _is_own_bookkeeping(c)]


def newest_mtime(root: Path, rel_paths: list[str]) -> float:
    """Newest mtime among the given relative paths (0.0 if none exist)."""
    latest = 0.0
    for rel in rel_paths:
        candidate = root / rel
        try:
            if candidate.is_file():
                latest = max(latest, candidate.stat().st_mtime)
        except OSError:
            continue
    return latest
