"""Shared MRS discovery primitives.

Git worktrees share one MRS: a task spans the main checkout and every linked
worktree (superpowers `using-git-worktrees`, Claude Code native worktrees), so
the MRS stays wherever it was created. What is per-worktree is the *work*:
uncommitted changes live in the worktree you are in (`work_root_for`), and
superpowers `.superpowers/sdd/` ledgers live at that worktree's git toplevel
(`ledger_root_for`).
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


MRS_PREFIX = ".task-state"


def is_mrs_dir(path: Path) -> bool:
    """True for `.task-state` or `.task-state-<slug>` directories."""
    return path.is_dir() and (
        path.name == MRS_PREFIX or path.name.startswith(f"{MRS_PREFIX}-")
    )


def _mrs_dirs_in(directory: Path) -> list[Path]:
    try:
        return sorted(p for p in directory.iterdir() if is_mrs_dir(p))
    except OSError:
        return []


@lru_cache(maxsize=128)
def _git_cached(start: str, args: tuple[str, ...]) -> str | None:
    # One hook run asks the same few questions for several MRS dirs; cache so
    # each distinct probe costs at most one short subprocess.
    try:
        result = subprocess.run(
            ["git", "-C", start, *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = result.stdout.strip()
    return out if result.returncode == 0 and out else None


def _git(start: Path, *args: str) -> str | None:
    try:
        key = str(Path(start).resolve())
    except OSError:
        return None
    return _git_cached(key, args)


def git_toplevel(start: Path) -> Path | None:
    """Top of the git worktree containing start (a linked worktree's own root)."""
    top = _git(start, "rev-parse", "--show-toplevel")
    return Path(top).resolve() if top else None


def git_common_dir(start: Path) -> Path | None:
    """The repository's shared git dir; identical for every worktree of one repo."""
    common = _git(start, "rev-parse", "--git-common-dir")
    if not common:
        return None
    path = Path(common)
    return (path if path.is_absolute() else Path(start).resolve() / path).resolve()


def other_worktrees(start: Path) -> list[Path]:
    """Checked-out worktrees of start's repository except its own, main checkout first.

    Taken from `git worktree list`, so separate-git-dir, bare and submodule
    layouts resolve without guessing from the git dir's name.
    """
    listing = _git(start, "worktree", "list", "--porcelain")
    top, common = git_toplevel(start), git_common_dir(start)
    if not listing or top is None:
        return []
    worktrees: list[Path] = []
    for block in listing.split("\n\n"):
        fields = block.splitlines()
        if not fields or not fields[0].startswith("worktree ") or "bare" in fields[1:]:
            continue
        path = Path(fields[0][len("worktree "):]).resolve()
        if path == common:
            # Git reports the git dir itself as the main worktree when the
            # checkout is not its parent. Submodules record the checkout in
            # core.worktree; a --separate-git-dir checkout records nothing, so
            # it cannot be found (use restore_context.py --mrs).
            configured = _git(common, "config", "--get", "core.worktree")
            if not configured:
                continue
            path = (common / configured).resolve()
        if path != top and path.is_dir():
            worktrees.append(path)
    return worktrees


def _walk_up(start: Path, stop: Path | None = None) -> list[Path]:
    """MRS dirs at the first ancestor of start (up to stop, inclusive) containing any."""
    current = start
    while True:
        matches = _mrs_dirs_in(current)
        if matches or current == stop or current.parent == current:
            return matches
        current = current.parent


def find_mrs_dirs(start: Path) -> list[Path]:
    """Return MRS dirs at the first ancestor of start containing any.

    A linked worktree outside the checkout that owns the MRS has none among its
    ancestors. Then the same relative location is searched in the repository's
    other worktrees (main checkout first); every candidate found is returned so
    ambiguous layouts (e.g. several worktrees of a bare repo) ask the user
    instead of picking one.
    """
    start = start.resolve()
    matches = _walk_up(start)
    if matches:
        return matches
    top = git_toplevel(start)
    if top is None:
        return []
    try:
        rel = start.relative_to(top)
    except ValueError:
        return []
    found: list[Path] = []
    for worktree in other_worktrees(start):
        mapped = worktree / rel
        while not mapped.is_dir() and mapped != worktree:
            mapped = mapped.parent
        found.extend(p for p in _walk_up(mapped, stop=worktree) if p not in found)
    return found


def mrs_project_root(mrs_dir: Path) -> Path:
    """Project that owns an MRS directory (its parent for `.task-state*`)."""
    if mrs_dir.name == MRS_PREFIX or mrs_dir.name.startswith(f"{MRS_PREFIX}-"):
        return mrs_dir.parent
    return mrs_dir


def work_root_for(mrs_dir: Path, start: Path | None = None) -> Path:
    """Directory whose uncommitted changes belong to the current work.

    Same worktree as the MRS project (including a project that is a
    subdirectory of the repo): the MRS project itself, as before. A different
    worktree of the same repository: the project's counterpart inside the
    current worktree (its top when the counterpart does not exist). Anything
    else (no start, no git, an unrelated repository): the MRS project.
    """
    project = mrs_project_root(mrs_dir)
    if start is None:
        return project
    top, project_top = git_toplevel(start), git_toplevel(project)
    if top is None or project_top is None or top == project_top:
        return project
    if git_common_dir(start) != git_common_dir(project):
        return project
    try:
        counterpart = top / project.resolve().relative_to(project_top)
    except ValueError:
        return top
    return counterpart if counterpart.is_dir() else top


def ledger_root_for(mrs_dir: Path, start: Path | None = None) -> Path:
    """Where superpowers keeps SDD workspaces for the current work.

    Upstream `sdd-workspace` creates them under the git toplevel of the
    worktree it runs in, never under a project subdirectory.
    """
    work = work_root_for(mrs_dir, start)
    return git_toplevel(work) or work
