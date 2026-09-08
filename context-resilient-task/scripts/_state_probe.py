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
import re
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
    "read_context_entries",
    "read_context_entry_records",
    "format_context_entry",
    "context_sensitivity",
    "has_sensitive_value",
    "mrs_updated_mtime",
    "bounded_text",
]

TIER0 = ["task_state.md", "plan.md", "snapshot.md"]
TIER1 = ["findings.md", "progress.md", "decisions.md", "architecture.md", "utils.md"]

_UNKNOWN = "(unknown)"
_EMPTY_MARKERS = {"", "(unknown)", "(no content)", "_(none)_", "none", "(none)"}
_NONE_CONTENT = {"(none recorded)", "- (none recorded)", "(none)", "- (none)", "_(none)_"}
_SENSITIVITY_RE = re.compile(r"(?:\*\*)?\s*(?:sensitivity|敏感度|敏感级别)\s*(?:\*\*)?\s*[:=：]\s*(?:\*\*)?\s*([\w-]+)", re.I)
_TABLE_SENSITIVITY_RE = re.compile(r"\|[^\n|]*\|\s*(public|internal|restricted|secret|confidential|top-secret|highly\s+confidential|受限)\b", re.I)
_SECRET_RE = re.compile(r"(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+|(?:AKIA|ghp_|github_pat_)[A-Za-z0-9_-]{8,})", re.I)


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


def mrs_updated_mtime(mrs_dir: Path) -> float:
    """Use the newest MRS markdown file as the canonical recency signal."""
    try:
        return max((item.stat().st_mtime for item in mrs_dir.glob("*.md")), default=0.0)
    except OSError:
        return 0.0


def bounded_text(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n… (output truncated to 4000 characters)"
    return text[: max_chars - len(suffix)].rstrip() + suffix


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


def read_context_entries(
    mrs_dir: Path,
    filename: str,
    limit: int = 3,
    max_chars: int = 1200,
) -> list[str]:
    """Read a bounded tail of markdown ``##`` entries for recovery output.

    Append-only context files can grow for months. Recovery needs the newest
    entries, but must not flood a fresh context with the entire history.
    Files without entry headings are treated as one bounded document.
    """
    return [format_context_entry(record, max_chars) for record in read_context_entry_records(mrs_dir, filename, limit, max_chars)]


def _visible_lines(lines: list[str]) -> tuple[list[tuple[str, int, bool]], set[int]]:
    """Remove HTML comments and ignore markdown headings inside fenced code.

    The returned line numbers remain those from the original file so source
    pointers are not shifted by removed template comments.
    """
    visible: list[tuple[str, int, bool]] = []
    in_comment = False
    in_fence = False
    for index, line in enumerate(lines):
        if in_comment:
            end = line.find("-->")
            if end < 0:
                continue
            line = line[end + 3:]
            in_comment = False
        while "<!--" in line:
            start = line.find("<!--")
            end = line.find("-->", start + 4)
            if end < 0:
                line = line[:start]
                in_comment = True
                break
            line = line[:start] + line[end + 3:]
        stripped = line.strip()
        was_fenced = in_fence
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            was_fenced = False
        visible.append((line, index, was_fenced))
    return visible, set()


def context_sensitivity(text: str) -> str:
    levels = {group.lower() for match in _SENSITIVITY_RE.finditer(text) for group in match.groups() if group}
    levels.update(match.group(1).lower() for match in _TABLE_SENSITIVITY_RE.finditer(text))
    if re.search(r"(?:\bsensitivity\b|敏感度|敏感级别)", text, re.I) and not levels:
        return "restricted"
    if levels & {"restricted", "secret", "confidential", "top-secret", "highly confidential", "受限"} or (levels and not levels <= {"public", "internal"}):
        return "restricted"
    if "public" in levels:
        return "public"
    return "internal"


def has_sensitive_value(text: str) -> bool:
    return bool(_SECRET_RE.search(text))


def read_context_entry_records(
    mrs_dir: Path, filename: str, limit: int = 3, max_chars: int = 1200
) -> list[dict]:
    path = mrs_dir / filename
    if not path.exists() or limit <= 0 or max_chars <= 0:
        return []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    visible, _ = _visible_lines(raw_lines)
    lines = [item[0] for item in visible]
    starts = [i for i, (_, _, fenced) in enumerate(visible) if not fenced and re.match(r"^##\s+", lines[i])]
    records: list[dict] = []
    if starts:
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            chunk = "\n".join(lines[start:end]).strip()
            body = "\n".join(chunk.splitlines()[1:]).strip()
            if not body or body.lower() in _NONE_CONTENT:
                continue
            records.append({
                "text": chunk,
                "line": visible[start][1] + 1,
                "filename": filename,
                "pinned": bool(re.match(r"^##\s+invariants\s*\(pinned\)", lines[start], re.I)) or bool(re.search(r"^\s*(?:[-*]\s*)?(?:\*\*)?pinned(?:\*\*)?\s*:?\s*(?:\*\*)?\s*yes\b|^\s*(?:[-*]\s*)?pinned\s*:\s*yes\b", body, re.I | re.M)),
                "sensitivity": context_sensitivity(chunk) if filename == "utils.md" else "internal",
            })
    else:
        text = "\n".join(lines).strip()
        body = "\n".join(text.splitlines()[1:]).strip() if text.startswith("# ") else text
        if body and body.lower() not in _NONE_CONTENT:
            records.append({"text": text, "line": 1, "filename": filename, "pinned": False, "sensitivity": context_sensitivity(text) if filename == "utils.md" else "internal"})
    pinned = [record for record in records if record["pinned"]]
    recent = [record for record in records if not record["pinned"]][-limit:]
    return pinned + recent


def format_context_entry(record: dict, max_chars: int = 1200) -> str:
    text = record["text"].strip()
    if len(text) <= max_chars:
        return text
    lines = text.splitlines()
    heading = lines[0] if lines else ""
    body = "\n".join(lines[1:]).strip()
    pointer = f"… (truncated; full content in {record.get('filename', 'source')}:{record['line']})"
    budget = max(0, max_chars - len(heading) - len(pointer) - 3)
    tail = body[-budget:] if budget else ""
    return f"{heading}\n{tail}\n{pointer}".strip()
