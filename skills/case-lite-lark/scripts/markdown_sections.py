"""ATX section selection, adapted from feishu-docx-blocks 3.4.0; keep original bytes-as-text."""
from __future__ import annotations

import re

from lark_cli import CLIError

HEADING = re.compile(r"^ {0,3}(#{1,6})(?!#)[ \t]+(.*?)[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def parse_sections(markdown: str) -> list[dict]:
    lines = markdown.splitlines(keepends=True)
    headings = []
    fence = None
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        match = FENCE.match(line)
        if match:
            marker, tail = match.groups()
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not tail.strip():
                fence = None
            continue
        if fence is not None:
            continue
        match = HEADING.match(line)
        if match:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", match[2]).strip()
            if title:
                headings.append({"title": title, "level": len(match[1]), "start": index})
    stack, counts = [], {}
    for index, heading in enumerate(headings):
        while stack and stack[-1]["level"] >= heading["level"]:
            stack.pop()
        parent = stack[-1]["id"] if stack else ""
        counts[parent] = counts.get(parent, 0) + 1
        heading["id"] = f"{parent}.{counts[parent]}" if parent else str(counts[parent])
        heading["section_path"] = " > ".join([p["title"] for p in stack] + [heading["title"]])
        end = next((h["start"] for h in headings[index + 1:] if h["level"] <= heading["level"]), len(lines))
        heading["range"] = {"start_line": heading["start"] + 1, "end_line": end}
        heading["content"] = "".join(lines[heading.pop("start"):end])
        stack.append(heading)
    return headings


def select_sections(sections: list[dict], ids: list[str]) -> list[dict]:
    if not ids:
        raise CLIError("请先选择章节；全文导入须显式使用 --all 并经用户确认")
    by_id = {s["id"]: s for s in sections}
    missing = sorted(set(ids) - by_id.keys())
    if missing:
        raise CLIError("章节不存在，请重新浏览目录", {"message": "章节不存在", "section_ids": missing})
    def bounds(section):
        values = section["range"]
        return (values.get("start_line", values.get("start_position")), values.get("end_line", values.get("end_position")))
    ordered = sorted((by_id[i] for i in set(ids)), key=bounds)
    selected = []
    for section in ordered:
        start, end = bounds(section)
        if not any(bounds(p)[0] <= start and bounds(p)[1] >= end for p in selected):
            selected.append(section)
    return selected
