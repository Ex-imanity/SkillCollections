#!/usr/bin/env python3
"""Draft a utils.md Resource Registry from the pointers already in an MRS.

Legacy MRS trees (created before the registry existed) carry their resource
pointers inside `findings.md`, `progress.md`, `decisions.md` and custom
documents — append-only logs that recovery either truncates or never replays.
This script finds those pointers, classifies them, and prints a draft registry
for review. It never rewrites existing rows and never invents access
credentials: `Name / Purpose`, `Access` and `Sensitivity` still need a human.

Read-only by default. With --write it inserts the draft rows into utils.md
(creating the file from the template when absent), skipping pointers already
registered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"
sys.path.insert(0, str(SCRIPT_DIR))

from _mrs_discovery import find_mrs_dirs  # noqa: E402
from _state_probe import configure_utf8_stdout  # noqa: E402

URL_RE = re.compile(r"(?:https?|mysql|redis|mongodb|postgres(?:ql)?)://[^\s)\"'|`>\]]+")
PATH_RE = re.compile(r"(?<![\w/])(?:/Users/[A-Za-z0-9._-]+|~)/[A-Za-z0-9._/-]{4,}")
HOST_PORT_RE = re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d{2,5})?\b")
HEADING_RE = re.compile(r"^#{1,4}\s+(.*\S)\s*$")
TRAILING_PUNCT = "。，、；：）)】」』.,;:!?，>*_`"

# Ordered: the first matching rule wins.
CLASSIFIERS: list[tuple[str, re.Pattern[str]]] = [
    ("feishu-doc", re.compile(r"(?:feishu\.cn|larksuite\.com|feishu\.net)", re.I)),
    ("database", re.compile(r"^(?:mysql|redis|mongodb|postgres(?:ql)?)://", re.I)),
    ("local-process", re.compile(r"^(?:https?://)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?", re.I)),
    ("repo", re.compile(r"(?:github\.com|gitlab|/\.git\b|\.git$)", re.I)),
    ("log-platform", re.compile(r"(?:grafana|kibana|gapm|sls|jaeger|zipkin|arms|log[s]?\.)", re.I)),
    ("dashboard", re.compile(r"(?:dashboard|metabase|superset|report|data-science)", re.I)),
    ("static-site", re.compile(r"\.html?(?:[#?].*)?$", re.I)),
    ("ticket", re.compile(r"(?:jira|banshan|/issues?/|/case/|tapd|teambition)", re.I)),
    ("local-path", re.compile(r"^(?:/Users/|~/)")),
    ("service-api", re.compile(r"^https?://[^/]*(?:api|service|gateway|internal|test-)", re.I)),
    ("web-page", re.compile(r"^https?://", re.I)),
]

# Single source/doc files cited as evidence are findings, not resources: they
# belong in the finding that cites them, and registering them would crowd the
# registry out of its working budget. --include-files keeps them anyway.
EVIDENCE_SUFFIXES = {
    ".java", ".kt", ".swift", ".ts", ".tsx", ".js", ".jsx", ".vue", ".py", ".go",
    ".rb", ".rs", ".php", ".c", ".h", ".cpp", ".m", ".mm", ".scala", ".sql",
    ".md", ".txt", ".yml", ".yaml", ".xml", ".gradle", ".properties",
}

# Rows are ranked by how likely the pointer is something an agent must reach
# again, so a tight --limit keeps the reachable things and drops the noise.
TYPE_PRIORITY = {
    "feishu-doc": 0, "ticket": 1, "dashboard": 2, "log-platform": 3, "database": 4,
    "service-api": 5, "local-process": 6, "static-site": 7, "repo": 8,
    "web-page": 9, "local-path": 10, "other:unclassified": 11,
}

ENV_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("local", re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0|^/Users/|^~/)", re.I)),
    ("staging", re.compile(r"(?:\btest-|\bstaging|\bdev-|\buat\b|\bpre-)", re.I)),
    ("prod", re.compile(r"^(?:https?|mysql|redis|mongodb|postgres(?:ql)?)://", re.I)),
]


def classify(pointer: str) -> str:
    if pointer.startswith(("/Users/", "~/")):
        expanded = Path(pointer).expanduser()
        if expanded.is_dir():
            return "repo" if (expanded / ".git").exists() else "local-path"
    for name, pattern in CLASSIFIERS:
        if pattern.search(pointer):
            return name
    return "other:unclassified"


# A bare container directory is never itself the resource.
GENERIC_DIRS = {"projects", "ideaprojects", "pycharmprojects", "documents",
                "downloads", "desktop", "library", "src", "code", "workspace"}


def is_generic_container(pointer: str) -> bool:
    parts = [part for part in Path(pointer).expanduser().parts if part not in ("/", "")]
    tail = parts[2:] if parts[:1] == ["Users"] else parts
    return len(tail) <= 1 and (not tail or tail[0].lower() in GENERIC_DIRS)


def is_evidence_path(pointer: str) -> bool:
    """True for a single source/doc file cited as evidence rather than a resource."""
    if not pointer.startswith(("/Users/", "~/")):
        return False
    return Path(pointer).suffix.lower() in EVIDENCE_SUFFIXES


def guess_env(pointer: str) -> str:
    for name, pattern in ENV_RULES:
        if pattern.search(pointer):
            return name
    return "—"


def normalize(pointer: str) -> str:
    return pointer.rstrip(TRAILING_PUNCT).rstrip("/")


def scan_file(path: Path) -> list[dict]:
    """Collect pointers from one markdown file, tagged with their nearest heading."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    hits: list[dict] = []
    heading = ""
    for number, line in enumerate(lines, start=1):
        matched = HEADING_RE.match(line)
        if matched:
            heading = matched.group(1)
            continue
        found = URL_RE.findall(line) + PATH_RE.findall(line)
        if not found:
            # A bare host:port (no scheme) still names a reachable process.
            found = [m.group(0) for m in HOST_PORT_RE.finditer(line) if ":" in m.group(0)]
        for raw in found:
            pointer = normalize(raw)
            if len(pointer) < 8:
                continue
            hits.append({
                "pointer": pointer,
                "context": heading,
                "source": f"{path.name}:{number}",
            })
    return hits


def existing_pointers(utils: Path) -> set[str]:
    if not utils.exists():
        return set()
    try:
        content = utils.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {normalize(p) for p in URL_RE.findall(content) + PATH_RE.findall(content)}


def collect(mrs_dir: Path, limit: int, include_files: bool = False) -> list[dict]:
    registered = existing_pointers(mrs_dir / "utils.md")
    seen: dict[str, dict] = {}
    sources = sorted(
        (p for p in mrs_dir.glob("*.md") if p.name != "utils.md" and not p.name.startswith("snapshot_")),
        key=lambda p: p.name,
    )
    for path in sources:
        for hit in scan_file(path):
            pointer = hit["pointer"]
            if pointer in registered:
                continue
            if not include_files and is_evidence_path(pointer):
                continue
            if pointer.startswith(("/Users/", "~/")) and is_generic_container(pointer):
                continue
            record = seen.setdefault(pointer, {
                "pointer": pointer,
                "type": classify(pointer),
                "env": guess_env(pointer),
                "context": hit["context"],
                "sources": [],
                "count": 0,
            })
            record["count"] += 1
            if hit["source"] not in record["sources"]:
                record["sources"].append(hit["source"])
            if not record["context"] and hit["context"]:
                record["context"] = hit["context"]
    ranked = sorted(
        seen.values(),
        key=lambda r: (TYPE_PRIORITY.get(r["type"], 99), -r["count"], r["pointer"]),
    )
    return ranked[:limit]


def render_rows(records: list[dict], start_index: int) -> tuple[list[str], list[str]]:
    rows: list[str] = []
    notes: list[str] = []
    for offset, record in enumerate(records):
        rid = f"R{start_index + offset}"
        purpose = (record["context"] or "(待填写用途)").replace("|", "/")[:40]
        verified = "— (draft)"
        if record["pointer"].startswith(("/Users/", "~/")) and not Path(record["pointer"]).expanduser().exists():
            verified = "— (draft, 路径不存在)"
        rows.append(
            f"| {rid} | {record['type']} | {purpose} | {record['pointer']} | {record['env']} "
            f"| (待填写) | internal | {verified} |"
        )
        notes.append(f"- {rid} 草稿来源: {', '.join(record['sources'][:3])}（出现 {record['count']} 次）")
    return rows, notes


def next_index(utils: Path) -> int:
    if not utils.exists():
        return 1
    try:
        ids = re.findall(r"^\|\s*R(\d+)\s*\|", utils.read_text(encoding="utf-8"), re.M)
    except OSError:
        return 1
    return max((int(i) for i in ids), default=0) + 1


def write_rows(utils: Path, rows: list[str], notes: list[str]) -> str:
    if not utils.exists():
        template = (ASSETS_DIR / "utils.template.md").read_text(encoding="utf-8")
        utils.write_text(template, encoding="utf-8")
    content = utils.read_text(encoding="utf-8")
    lines = content.splitlines()

    if not re.search(r"^##\s*Resource Registry\b", content, re.M):
        lines += ["", "## Resource Registry", "",
                  "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |",
                  "|----|------|----------------|---------|-----|--------|-------------|----------|"]

    # Insert after the last table row of the registry section, dropping the
    # "(none recorded)" placeholder row if it is still there.
    start = next(i for i, line in enumerate(lines) if re.match(r"^##\s*Resource Registry\b", line))
    end = start + 1
    last_row = None
    while end < len(lines) and not re.match(r"^##\s+", lines[end]):
        if lines[end].lstrip().startswith("|"):
            last_row = end
        end += 1
    if last_row is None:
        return "no registry table found in utils.md; add the header row and retry"
    if "(none recorded)" in lines[last_row]:
        lines.pop(last_row)
        last_row -= 1
    lines[last_row + 1:last_row + 1] = rows

    if notes:
        if re.search(r"^##\s*Notes\b", "\n".join(lines), re.M):
            note_at = next(i for i, line in enumerate(lines) if re.match(r"^##\s*Notes\b", line))
            insert_at = note_at + 1
            while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].lstrip().startswith("<!--")):
                insert_at += 1
            if insert_at < len(lines) and "(none recorded)" in lines[insert_at]:
                lines.pop(insert_at)
            lines[insert_at:insert_at] = notes
        else:
            lines += ["", "## Notes", ""] + notes
    utils.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"wrote {len(rows)} draft rows into {utils}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft a utils.md Resource Registry from existing MRS pointers")
    parser.add_argument("directory", nargs="?", default=".", help="MRS directory or a project containing one")
    parser.add_argument("--write", action="store_true", help="Insert the draft rows into utils.md")
    parser.add_argument("--limit", type=int, default=40, help="Maximum draft rows (default: 40)")
    parser.add_argument("--include-files", action="store_true",
                        help="Also draft rows for single source/doc files cited as evidence")
    parser.add_argument("--json", action="store_true", help="Emit JSON for agent consumption")
    args = parser.parse_args()
    configure_utf8_stdout()

    target = Path(args.directory).resolve()
    if not target.is_dir():
        print(f"not a directory: {target}", file=sys.stderr)
        return 1
    if not (target / "task_state.md").exists():
        found = find_mrs_dirs(target)
        if len(found) != 1:
            names = ", ".join(p.name for p in found) or "none"
            print(f"expected exactly one MRS under {target}; found: {names}. "
                  "Pass the MRS directory explicitly.", file=sys.stderr)
            return 1
        target = found[0]

    records = collect(target, args.limit, include_files=args.include_files)
    if args.json:
        print(json.dumps({"mrs": str(target), "candidates": records}, indent=2, ensure_ascii=False))
        return 0
    if not records:
        print(f"No unregistered resource pointers found in {target}.")
        return 0

    rows, notes = render_rows(records, next_index(target / "utils.md"))
    print(f"# Draft Resource Registry for {target}")
    print(f"# {len(records)} unregistered pointers found. Review Name/Purpose, Access and Sensitivity before trusting them.")
    print()
    print("| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |")
    print("|----|------|----------------|---------|-----|--------|-------------|----------|")
    for row in rows:
        print(row)
    print()
    for note in notes:
        print(note)
    if args.write:
        print()
        print(write_rows(target / "utils.md", rows, notes))
    else:
        print()
        print("Re-run with --write to insert these rows into utils.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
