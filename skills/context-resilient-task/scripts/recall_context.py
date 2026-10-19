#!/usr/bin/env python3
"""Search complete MRS history before retrying an error or blocker (read-only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _context_recall import balanced_sections, clip, search_context
from _state_probe import configure_utf8_stdout, has_sensitive_value


def bounded_value(value: str, budget: int) -> str:
    """Bound serialized metadata too: escaped characters consume output space."""
    result = clip(value, budget)
    while len(json.dumps(result, ensure_ascii=False)) > budget:
        result = clip(result, len(result) // 2)
    return result


def bounded_match(match: dict) -> dict:
    result = dict(match)
    result["id"] = bounded_value(match["id"], 64) if match["id"] else None
    result["status"] = bounded_value(match["status"], 80)
    result["scope"] = {bounded_value(k, 40): bounded_value(v, 120)
                       for k, v in list(match["scope"].items())[:6]}
    if any(result[key] != match[key] for key in ("id", "status", "scope")):
        result["truncated"] = True
        result["applicability"] = "recheck_required"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mrs", type=Path, help="Explicit MRS directory; never chooses another task")
    parser.add_argument("--query", required=True, help="Error/symptom/component, without credentials")
    parser.add_argument("--scope", action="append", default=[], metavar="KEY=VALUE",
                        help="Repeat for known repo/env/tool/version constraints; conflicts excluded")
    parser.add_argument("--limit", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    configure_utf8_stdout()
    if not args.mrs.is_dir():
        parser.error("MRS directory does not exist")
    if has_sensitive_value(args.query) or any(has_sensitive_value(s) for s in args.scope):
        parser.error("Remove credentials from the query and scope")
    scope = {}
    for value in args.scope:
        key, sep, item = value.partition("=")
        if not sep or not key.strip() or not item.strip():
            parser.error("Scope must use KEY=VALUE")
        scope[key.strip().casefold()] = item.strip().casefold()
    matches = [bounded_match(m) for m in search_context(args.mrs, args.query, scope, args.limit)]
    note = "Candidates only: read sources, verify current scope and evidence before reuse."
    if args.json:
        payload = {"matches": matches, "note": note,
                   "truncated": any(m["truncated"] for m in matches), "omitted_matches": 0}
        rendered = json.dumps(payload, ensure_ascii=False)
        while len(rendered) > 3999:
            payload["truncated"] = True
            if any(len(m["excerpt"]) > 100 for m in matches):
                for match in matches:
                    if len(match["excerpt"]) > 100:
                        match["excerpt"] = clip(match["excerpt"], max(100, len(match["excerpt"]) // 2))
                        match["truncated"] = True
            else:
                # Metadata is bounded above, so a single candidate always fits.
                # Keep its source pointer instead of turning a hit into no match.
                matches.pop()
                payload["omitted_matches"] += 1
            rendered = json.dumps(payload, ensure_ascii=False)
        print(rendered)
    else:
        sections = [("### Context Recall", note, "")]
        for match in matches:
            source = f"{match['file']}:{match['line']}"
            sections.append((f"### {source} [{match['status']}; {match['applicability']}]",
                             match["excerpt"], source))
        if not matches:
            sections.append(("### No matches", "Continue normal diagnosis; record reusable problems after triage.", ""))
        print(balanced_sections(sections))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
