"""Bounded recovery sections and read-only retrieval from the complete MRS."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from datetime import date

from _state_probe import (
    context_sensitivity, has_sensitive_value, is_meaningful,
    read_context_entry_records, _visible_lines,
)

CONTEXT_FILES = ("problems.md", "decisions.md", "findings.md", "progress.md", "utils.md")
PROBLEM_HEADING = re.compile(r"^##\s+(P\d+)\s*:\s*(.+)", re.I)
PROBLEM_FIELDS = ("Status", "Signature", "Scope", "Cause", "Tried", "Resolution",
                  "Verification", "Source", "Last verified", "Recheck when")
PROBLEM_STATUSES = {"open", "resolved", "stale", "superseded"}


def clip(text: str, budget: int, pointer: str = "") -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    suffix = f"\n… (full content in {pointer})" if pointer else "\n… (truncated)"
    if budget <= len(suffix):
        return suffix.strip()[:budget]
    return text[:budget - len(suffix)].rstrip() + suffix


def balanced_sections(sections: list[tuple[str, str, str]], budget: int = 3999) -> str:
    """Reserve every section's heading/entry point before distributing spare space.

    Retrieval and restore commands have a protected slot. Other sections share
    the remainder; even an enormous pinned block cannot consume another slot.
    The default leaves one character for a CLI's final newline.
    """
    sections = [(heading, body.strip(), pointer) for heading, body, pointer in sections if body.strip()]
    if not sections or budget <= 0:
        return ""
    # Headings are untrusted source text too, not free framing overhead.
    # Leave at least half of the ordinary budget for bodies and entry points.
    heading_budget = max(0, min(160, (budget - 2 * (len(sections) - 1)) // (2 * len(sections)) - 1))
    sections = [(clip(h, heading_budget), b, p) for h, b, p in sections]
    def render(sizes):
        return "\n\n".join(
            (heading + "\n" if heading else "") + clip(body, size, pointer)
            for (heading, body, pointer), size in zip(sections, sizes))
    sizes = [len(body) for _, body, _ in sections]
    if len(render(sizes)) <= budget:
        return render(sizes)
    overhead = sum(len(h) + (1 if h else 0) for h, _, _ in sections) + 2 * (len(sections) - 1)
    available = max(0, budget - overhead)
    weights = [5 if "Todo" in h or "todo" in h or "Next" in h else 2 for h, _, _ in sections]
    sizes = [min(len(b), len(b) if h.lstrip("# ") in ("Context Recall", "Restore Command") else 90)
             for h, b, _ in sections]
    # Extremely long paths/metadata still have to obey the global output limit.
    if sum(sizes) > available:
        sizes = [min(n, max(0, available // len(sections))) for n in sizes]
    remaining = available - sum(sizes)
    while remaining > 0:
        active = [i for i, (_, body, _) in enumerate(sections) if sizes[i] < len(body)]
        if not active:
            break
        total_weight = sum(weights[i] for i in active)
        pool = remaining
        for i in active:
            growth = min(remaining, len(sections[i][1]) - sizes[i],
                         max(1, pool * weights[i] // total_weight))
            sizes[i] += growth
            remaining -= growth
    return render(sizes)[:budget]


def safe_records(mrs: Path, filename: str, limit: int = 1_000_000) -> list[dict]:
    """No recency window for retrieval; reuse comment/fence and utils redaction."""
    path = mrs / filename
    if not path.is_file():
        return []
    # An explicit file-level restriction applies to its entries too.
    visible, _ = _visible_lines(path.read_text(encoding="utf-8").splitlines())
    prefix_lines = []
    for line, _, fenced in visible:
        if not fenced and re.match(r"^##\s+", line):
            break
        if not fenced:
            prefix_lines.append(line)
    prefix = "\n".join(prefix_lines)
    if context_sensitivity(prefix) == "restricted":
        return []
    return [r for r in read_context_entry_records(mrs, filename, limit=limit)
            if context_sensitivity(r["text"]) != "restricted" and not has_sensitive_value(r["text"])]


def fields_for(text: str) -> dict[str, str]:
    fields = {}
    for line, _, fenced in _visible_lines(text.splitlines())[0]:
        if fenced:
            continue
        match = re.match(r"^\s*[-*]\s+([A-Za-z ]+):\s*(.*)", line.replace("**", ""))
        if match:
            fields.setdefault(match[1].strip().lower(), match[2].strip())
    return fields


def problem_records(mrs: Path, safe: bool = True) -> list[dict]:
    records = (safe_records(mrs, "problems.md") if safe else
               read_context_entry_records(mrs, "problems.md", limit=1_000_000))
    result = []
    for record in records:
        match = PROBLEM_HEADING.match(record["text"])
        if match:
            result.append({**record, "id": match[1].upper(), "fields": fields_for(record["text"])})
    return result


def problem_format_warnings(mrs: Path) -> list[str]:
    return [f"problems.md:{r['line']}: missing standard problem ID (use ## P001: symptom); "
            "searchable as historical evidence, recheck before reuse"
            for r in read_context_entry_records(mrs, "problems.md", limit=1_000_000)
            if not PROBLEM_HEADING.match(r["text"])]


def validate_problems(mrs: Path) -> list[str]:
    errors, seen = [], set()
    for record in problem_records(mrs, safe=False):
        label, fields = f"problems.md:{record['line']} {record['id']}", record["fields"]
        if record["id"] in seen:
            errors.append(f"{label}: duplicate problem ID")
        seen.add(record["id"])
        for field in PROBLEM_FIELDS:
            if not fields.get(field.lower()):
                errors.append(f"{label}: missing {field}")
        if fields.get("status") not in PROBLEM_STATUSES:
            errors.append(f"{label}: Status must be open, resolved, stale or superseded")
        if fields.get("status") == "resolved":
            for field in ("Resolution", "Verification", "Source", "Last verified"):
                if not is_meaningful(fields.get(field.lower(), "")) or fields.get(field.lower(), "").lower() in {"unknown", "pending", "unverified"}:
                    errors.append(f"{label}: resolved requires verified {field}")
            try:
                date.fromisoformat(fields.get("last verified", ""))
            except ValueError:
                errors.append(f"{label}: Last verified must be an ISO date for resolved problems")
        if has_sensitive_value(record["text"]):
            errors.append(f"{label}: remove credential-shaped values")
    return errors


def context_sections(mrs: Path) -> list[tuple[str, str, str]]:
    sections = []
    for title, filename in (("Stable Decisions", "decisions.md"), ("Key Findings", "findings.md"), ("Utilities", "utils.md")):
        records = safe_records(mrs, filename, limit=3)
        if records:
            # A short head of EACH selected record, with a pointer. Preserve the
            # first pinned constraint as well as recent entries, not just tails.
            parts = []
            for r in records:
                text = re.sub(r"^#{1,2} ", "### ", r["text"], flags=re.M)
                parts.append(clip(text, max(130, 1000 // len(records)), f"{filename}:{r['line']}"))
            sections.append((f"### {title} ({filename})", "\n".join(parts), filename))
    if (mrs / "problems.md").exists():
        records = [r for r in problem_records(mrs) if r["fields"].get("status") != "superseded"]
        records.sort(key=lambda r: ({"open": 0, "stale": 1, "resolved": 2}.get(r["fields"].get("status"), 0),
                                    -r["line"]))
        summaries = [f"- {r['id']} [{r['fields'].get('status', 'unverified')}] "
                     f"{r['text'].splitlines()[0].split(':', 1)[-1].strip()} (problems.md:{r['line']})"
                     for r in records[:3]]
        body = "\n".join(summaries) if summaries else "No reusable problems recorded yet."
        unstructured = sum(not PROBLEM_HEADING.match(r["text"]) for r in safe_records(mrs, "problems.md"))
        if unstructured:
            body += f"\n{unstructured} unstructured problem record(s): search full history and check sources."
        body += "\nSearch problems.md before retrying an error/blocker; resolved records remain searchable."
        sections.append(("### Known Problems (problems.md)", body, "problems.md"))
    command = (f"python {shlex.quote(str(Path(__file__).with_name('recall_context.py')))} "
               f"{shlex.quote(str(mrs))} --query '<error, symptom or component>'")
    sections.append(("### Context Recall", "Before retrying an error/blocker, search FULL history:\n" +
                     command + "\nChecks problems/findings/decisions/progress/utils beyond the recent window. "
                     "Read source and verify scope before reusing a fix.", ""))
    return sections


def scope_fields(value: str) -> dict[str, str]:
    return {k.casefold(): v.strip().casefold() for k, v in
            re.findall(r"([\w-]+)\s*=\s*([^;]+)", value)}


def tokens(value: str) -> set[str]:
    words = set(re.findall(r"[a-z_][a-z_0-9-]*|\d+", value.casefold()))
    for run in re.findall(r"[\u3400-\u9fff]+", value):
        words.update(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return words - {"no", "not", "the", "a", "an", "is", "of", "in", "named", "module", "error"}


def search_context(mrs: Path, query: str, scope: dict[str, str], limit: int = 3) -> list[dict]:
    wanted, matches = tokens(query), []
    invalid_ids = {pid for error in validate_problems(mrs)
                   for pid in re.findall(r"\bP\d+\b", error)}
    if not wanted:
        return []
    for filename in CONTEXT_FILES:
        for record in safe_records(mrs, filename):
            fields = fields_for(record["text"])
            problem = PROBLEM_HEADING.match(record["text"]) if filename == "problems.md" else None
            actual_scope = scope_fields(fields.get("scope", ""))
            if any(k in actual_scope and actual_scope[k] != v for k, v in scope.items()):
                continue
            status = fields.get("status", "historical")
            if status == "superseded":
                continue
            overlap = wanted & tokens(record["text"])
            if not overlap:
                continue
            signature_hits = wanted & tokens(fields.get("signature", ""))
            score = len(overlap) + 4 * len(signature_hits) + (2 if problem else 0)
            applicability = ("scope_matched" if actual_scope and actual_scope.items() <= scope.items()
                             else "check_scope")
            if status in {"stale", "open"}:
                applicability = "recheck_required"
            if filename == "problems.md" and not problem:
                status, applicability = "historical", "recheck_required"
            if problem and (problem[1].upper() in invalid_ids or status not in PROBLEM_STATUSES or
                            any(not fields.get(f.lower()) for f in PROBLEM_FIELDS)):
                applicability = "recheck_required"
            text = record["text"]
            # Problem entries keep their schema; long legacy logs get a window
            # around the first match, plus the exact source heading line.
            if not problem and len(text) > 850:
                position = min((m.start() for term in overlap
                                for m in re.finditer(re.escape(term), text.casefold())), default=0)
                start = max(0, position - 200)
                text = ("… " if start else "") + text[start:start + 850]
            excerpt = clip(text, 900, f"{filename}:{record['line']}")
            matches.append({"id": problem[1].upper() if problem else None, "file": filename,
                            "line": record["line"], "status": status,
                            "scope": actual_scope, "applicability": applicability,
                            "excerpt": excerpt, "truncated": excerpt != record["text"], "score": score})
    return sorted(matches, key=lambda m: (-m["score"], CONTEXT_FILES.index(m["file"]), m["line"]))[:limit]
