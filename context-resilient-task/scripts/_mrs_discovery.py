"""Shared MRS discovery primitives."""

from __future__ import annotations

from pathlib import Path


MRS_PREFIX = ".task-state"


def is_mrs_dir(path: Path) -> bool:
    """True for `.task-state` or `.task-state-<slug>` directories."""
    return path.is_dir() and (
        path.name == MRS_PREFIX or path.name.startswith(f"{MRS_PREFIX}-")
    )


def find_mrs_dirs(start: Path) -> list[Path]:
    """Walk up from start and return MRS dirs at the first ancestor containing any."""
    current = start.resolve()
    while True:
        try:
            matches = sorted(p for p in current.iterdir() if is_mrs_dir(p))
        except PermissionError:
            matches = []
        if matches:
            return matches
        if current.parent == current:
            return []
        current = current.parent
