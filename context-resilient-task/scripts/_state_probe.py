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
    "utils_records",
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
_LEVEL_MENTION_RE = re.compile(r"(?:\bsensitivity\b|敏感度|敏感级别)", re.I)
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|\-—–]+\|\s*$")
_BULLET_RE = re.compile(r"^ {0,1}[-*+]\s+")
    # --- Secret detection -------------------------------------------------------
# Deliberately "capture the value, then judge it" rather than encoding the
# secret shape positionally in one regex: the positional form both missed real
# credentials (empty-userinfo URLs, `Passw0rd`) and drifted between this probe
# and verify_mrs.py. verify_mrs.py imports has_sensitive_value from here so the
# emission guard and the validator can never disagree — a false positive here
# silently drops a legitimate registry row, which is worse than a warning.

# `Bearer <value>` is a strong grammar position: whatever follows is the token,
# unless it is a plain word ("Bearer credentials" is prose about auth).
_BEARER_RE = re.compile(r"(?<![\w-])(?:bearer|basic)(?![\w-])(?:\s*[:=]\s*|\s+)([^\s|]+)", re.I)
# `password: value` / `token=value` — ambiguous with prose, so the value has to
# look opaque before it counts.
# Compound keys are common (`client_secret`, `aws_secret_access_key`,
# `refresh_token`): allow one affix on either side. This widens the *keyword*
# only — the value still has to look opaque, so `parent_node_token=node_token`
# stays prose.
_SECRET_KEY_RE = re.compile(
    r"(?<![\w-])(?:[A-Za-z0-9]{1,24}[_-]?)?"
    r"(?:password|passwd|secret|token|api[_-]?key|apikey)"
    r"(?:[_-][A-Za-z0-9]{1,24})*(?![\w-])"
    r"(?:\s*[:=]\s*|\s+)([^\s|]+)",
    re.I,
)
# scheme://user:password@host — the username may be empty (redis://:pass@host).
# The value is greedy so a password containing '@' is captured whole.
_URI_CRED_RE = re.compile(r"(?<![\w-])[a-z][a-z0-9+.-]*://[^\s/:@|]*:([^\s/|]+)@", re.I)
# ?token=… / &api_key=…
_QUERY_CRED_RE = re.compile(
    r"[?&](?:token|access[_-]?token|api[_-]?key|apikey|secret|password|passwd|sig|signature)=([^\s&#|]+)",
    re.I,
)
# Vendor-prefixed keys and JWTs are self-identifying, so no value heuristic.
_STATIC_SECRET_RE = re.compile(
    # The left boundary matters: without it `sk-` matches inside "task-state".
    r"(?<![A-Za-z0-9_])"
    r"(?:(?:AKIA|ghp_|gho_|github_pat_|xoxb-|xoxp-|xapp-|sk_live_|pk_live_|glpat-)[A-Za-z0-9_-]{8,}"
    r"|sk-[A-Za-z0-9_-]{16,}"  # OpenAI-style keys (incl. sk-proj-...)
    r"|eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}"
    r"|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----)"
)
# Placeholders and redaction markers are never credentials.
_PLACEHOLDER_VALUE_RE = re.compile(r"^(?:[<{\[(].*|[*x.…\-_]+|\(.*\)|待填写.*|tbd|n/?a|none|null)$", re.I)
# One opaque token: credential punctuation is allowed, path/sentence punctuation
# (`/`, `:`, `,`, whitespace) is not.
_TOKEN_SHAPE_RE = re.compile(r"[A-Za-z0-9._~+=%@!$^&*#?-]{6,}")
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/=]{20,}")


def _looks_like_secret_value(value: str, mode: str = "keyword") -> bool:
    """Judge one captured value. Conservative on prose, strict on opaque data.

    `mode` reflects how much the surrounding grammar already proves:
      "uri"     — the password slot of a URL's userinfo: any real value counts,
                  including a short one.
      "bearer"  — after `Bearer`: anything but a plain word counts.
      "keyword" — after `password:` / `token=`: ambiguous with prose, so the
                  value must look opaque (digit or structural symbol, or a long
                  single alphabetic run).
    """
    value = value.strip().strip("`'\"“”‘’,;.，。；、:：)）]】>》")
    # `token=\`abc\`、\`def\`` captures past the first value, so keep the leading
    # run: otherwise trailing CJK punctuation makes a real token look like prose.
    value = re.split(r"[`\s、，。；;,]", value)[0].strip("'\"“”‘’:：)）]】>》")
    if not value or _PLACEHOLDER_VALUE_RE.match(value) or "***" in value:
        return False
    # Credentials are ASCII. A value carrying CJK (or any non-ASCII) is prose
    # such as "token 轮换/清理继续按用户要求独立".
    if not value.isascii():
        return False
    if mode == "uri":
        return True
    is_plain_word = bool(re.fullmatch(r"[A-Za-z]{1,12}", value))
    if mode == "bearer":
        return not is_plain_word
    if len(value) < 6:
        return False
    if _BASE64_BLOB_RE.fullmatch(value):
        return True
    # A credential is one opaque token. A value carrying path or sentence
    # punctuation is prose: "token-gated sync/delete", "token: ~/.claude/x.json".
    if not _TOKEN_SHAPE_RE.fullmatch(value):
        return False
    # Within that shape a digit or credential punctuation marks it opaque. An
    # all-letter value is not accepted at any length: English words reach 13+
    # characters ("token authenticates …"), and a false positive here silently
    # drops a legitimate registry row — the failure this release exists to fix.
    # Only punctuation that does not occur in ordinary compound words counts:
    # `-`, `_` and `.` are common in prose ("tenant-token record-list"), so a
    # value needs a digit or one of these to read as opaque.
    return any(char.isdigit() or char in "@!$^&*#?%+=~" for char in value)


def has_sensitive_value(text: str) -> bool:
    """True when the text carries a likely credential *value* (not a name)."""
    if _STATIC_SECRET_RE.search(text):
        return True
    for pattern, mode in ((_BEARER_RE, "bearer"), (_URI_CRED_RE, "uri"),
                          (_SECRET_KEY_RE, "keyword"), (_QUERY_CRED_RE, "keyword")):
        for match in pattern.finditer(text):
            if _looks_like_secret_value(match.group(1), mode=mode):
                return True
    return False


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


def list_artifacts(mrs_dir: Path, max_extra: int = 12) -> list[tuple[str, str]]:
    """Present every MRS document with human-readable mtimes.

    Tier 0 + Tier 1 come first in canonical order, then Tier 2 and any
    domain-specific document the task created (`evidence-index.md`,
    `test-observability.md`, meeting notes, ...). Real MRS trees accumulate
    these, and a recovery output that lists only the canonical set makes an
    agent behave as if they do not exist.

    Archived snapshots (`snapshot_*.md`) are excluded — they are history, not
    current state.
    """
    artifacts: list[tuple[str, str]] = []
    for name in TIER0 + TIER1:
        path = mrs_dir / name
        if path.exists():
            artifacts.append((name, human_time(path.stat().st_mtime)))
    known = set(TIER0 + TIER1)
    try:
        extra = sorted(
            (p for p in mrs_dir.glob("*.md")
             if p.name not in known and not p.name.startswith("snapshot_")),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
    except OSError:
        extra = []
    for path in extra[:max_extra]:
        artifacts.append((path.name, human_time(path.stat().st_mtime)))
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


def _split_utils_entries(lines: list[str]) -> list[dict]:
    """Group a utils.md section body into individually filterable entries.

    ``utils.md`` is a registry, not a prose log: one table row or one top-level
    bullet is one resource. Splitting at that granularity lets a single
    ``restricted`` resource be dropped without taking every sibling resource in
    the same table with it.

    Table header/separator rows are marked ``structural`` — they carry no
    pointer, and are emitted only when at least one data row survives.
    """
    entries: list[dict] = []
    for index, line in enumerate(lines):
        if _TABLE_ROW_RE.match(line):
            following = next((lines[j] for j in range(index + 1, len(lines)) if lines[j].strip()), "")
            structural = bool(_TABLE_SEP_RE.match(line)) or bool(_TABLE_SEP_RE.match(following))
            entries.append({"lines": [line], "structural": structural, "closed": True})
            continue
        if _BULLET_RE.match(line):
            entries.append({"lines": [line], "structural": False, "closed": False})
            continue
        if not line.strip():
            for entry in entries:
                entry["closed"] = True
            entries.append({"lines": [line], "structural": True, "closed": True})
            continue
        if entries and not entries[-1]["closed"]:
            entries[-1]["lines"].append(line)
            continue
        entries.append({"lines": [line], "structural": False, "closed": True})
    return entries


def filter_utils_section(chunk: str) -> tuple[str, str]:
    """Redact restricted resources from one utils.md section, row by row.

    Returns ``(text, sensitivity)``. ``sensitivity`` is ``restricted`` when
    nothing survived, so callers can drop the section entirely.

    Fail-closed: an entry that states no level inherits ``restricted`` whenever
    any sibling entry in the same section is restricted.
    """
    lines = chunk.splitlines()
    heading, body = (lines[0], lines[1:]) if lines else ("", [])
    entries = _split_utils_entries(body)
    for entry in entries:
        text = "\n".join(entry["lines"])
        if entry["structural"] or not text.strip():
            entry["level"] = None
            continue
        if has_sensitive_value(text):
            # A credential-shaped value must never reach a digest, whatever the
            # row claims its sensitivity is. verify_mrs.py rejects the file too;
            # this is the emission-side half of that guard.
            entry["level"] = "restricted"
            continue
        mentions = bool(
            _SENSITIVITY_RE.search(text) or _TABLE_SENSITIVITY_RE.search(text) or _LEVEL_MENTION_RE.search(text)
        )
        entry["level"] = context_sensitivity(text) if mentions else None
    has_restricted = any(entry["level"] == "restricted" for entry in entries)
    kept = [
        entry for entry in entries
        if entry["structural"] or entry["level"] in {"public", "internal"} or (entry["level"] is None and not has_restricted)
    ]
    survivors = [entry for entry in kept if not entry["structural"] and entry["lines"] and "".join(entry["lines"]).strip()]
    if not survivors:
        return "", "restricted"
    kept_lines = [line for entry in kept for line in entry["lines"]]
    text = "\n".join([heading] + kept_lines).rstrip()
    levels = {entry["level"] for entry in survivors}
    return text, "public" if levels == {"public"} else "internal"


def utils_records(mrs_dir: Path, limit: int = 3, max_chars: int = 1800) -> list[dict]:
    """Emittable utils.md sections: pinned, restricted rows already redacted."""
    return [
        record for record in read_context_entry_records(mrs_dir, "utils.md", limit=limit, max_chars=max_chars)
        if record["sensitivity"] in {"public", "internal"}
    ]


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
            if filename == "utils.md":
                # The resource registry is a profile, not a chronological log:
                # every section is pinned so a growing registry is never
                # recency-trimmed, and restricted rows are redacted per row.
                text, sensitivity = filter_utils_section(chunk)
                if sensitivity == "restricted":
                    continue
                records.append({
                    "text": text,
                    "line": visible[start][1] + 1,
                    "filename": filename,
                    "pinned": True,
                    "sensitivity": sensitivity,
                })
                continue
            records.append({
                "text": chunk,
                "line": visible[start][1] + 1,
                "filename": filename,
                "pinned": bool(re.match(r"^##\s+invariants\s*\(pinned\)", lines[start], re.I)) or bool(re.search(r"^\s*(?:[-*]\s*)?(?:\*\*)?pinned(?:\*\*)?\s*:?\s*(?:\*\*)?\s*yes\b|^\s*(?:[-*]\s*)?pinned\s*:\s*yes\b", body, re.I | re.M)),
                "sensitivity": "internal",
            })
    else:
        text = "\n".join(lines).strip()
        body = "\n".join(text.splitlines()[1:]).strip() if text.startswith("# ") else text
        if body and body.lower() not in _NONE_CONTENT:
            if filename == "utils.md":
                title = text.splitlines()[0] if text.startswith("# ") else ""
                filtered, sensitivity = filter_utils_section("# (synthetic heading)\n" + body)
                if sensitivity != "restricted":
                    kept_body = "\n".join(filtered.splitlines()[1:]).strip()
                    records.append({"text": f"{title}\n{kept_body}".strip() if title else kept_body,
                                    "line": 1, "filename": filename, "pinned": True, "sensitivity": sensitivity})
            else:
                records.append({"text": text, "line": 1, "filename": filename, "pinned": False, "sensitivity": "internal"})
    pinned = [record for record in records if record["pinned"]]
    recent = [record for record in records if not record["pinned"]][-limit:]
    return pinned + recent


def format_context_entry(record: dict, max_chars: int = 1200) -> str:
    text = record["text"].strip()
    if len(text) <= max_chars:
        return text
    lines = text.splitlines()
    heading = lines[0] if lines else ""
    # A truncated table is unreadable without its header row, so keep the
    # header/separator pair as part of the heading and tail-trim only the rows.
    header: list[str] = []
    rest = lines[1:]
    for index, line in enumerate(rest):
        if _TABLE_SEP_RE.match(line) and index >= 1 and _TABLE_ROW_RE.match(rest[index - 1]):
            header = rest[index - 1:index + 1]
            rest = rest[index + 1:]
            break
        if line.strip() and not _TABLE_ROW_RE.match(line):
            break
    prefix = "\n".join([heading] + header)
    body = "\n".join(rest).strip()
    pointer = f"… (truncated; full content in {record.get('filename', 'source')}:{record['line']})"
    budget = max(0, max_chars - len(prefix) - len(pointer) - 3)
    if not budget:
        kept = ""
    elif record.get("filename") == "utils.md":
        # The registry has no recency order and IDs are cited from other files,
        # so keep the earliest-registered rows instead of the tail.
        kept = body[:budget].rsplit("\n", 1)[0] if len(body) > budget else body
    else:
        kept = body[-budget:]
    return f"{prefix}\n{kept}\n{pointer}".strip()
