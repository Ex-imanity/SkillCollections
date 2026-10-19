"""Document discovery and selected corpus; all remote requests go through lark-cli."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from block_processor import BlockProcessor
from lark_cli import CLIError
from markdown_sections import parse_sections, select_sections


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise CLIError("文档或节点标识非法")
    return value


def metadata(section: dict) -> dict:
    return {k: v for k, v in section.items() if k != "content"}


class DocumentReader:
    def __init__(self, cli):
        self.cli = cli

    def resolve(self, url: str) -> dict:
        parsed = urlparse(url)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or len(parts) < 2:
            raise CLIError("请提供 HTTPS /docx/、/wiki/ 或 /file/ 文档链接")
        kind, token = parts[:2]
        identifier(token)
        if kind not in {"docx", "wiki", "file"}:
            raise CLIError("仅支持 Docx、Wiki 和原生 Markdown 文件")
        source = {"url": url, "type": kind, "token": token, "host": parsed.netloc}
        if kind == "wiki":
            node = self.cli.call("wiki", "+node-get", "--node-token", token)
            source.update(type=node.get("obj_type"), token=identifier(node.get("obj_token")),
                          node_token=node.get("node_token"), space_id=node.get("space_id"), title=node.get("title", ""))
        if source["type"] not in {"docx", "file"}:
            raise CLIError("该 Wiki 底层对象不是 Docx 或原生 Markdown 文件")
        return source

    def children(self, url: str, recursive: bool = False, max_nodes: int = 5000) -> dict:
        parsed = urlparse(url)
        if "/file/" in parsed.path:
            self.resolve(url)
            return {"children": [], "message": "原生 Markdown 不适用 Wiki 子文档发现"}
        source = self.resolve(url)
        try:
            node = self.cli.call("wiki", "+node-get", "--node-token", source.get("node_token", source["token"]))
        except CLIError as exc:
            if exc.details.get("code") == 131014:
                return {"children": [], "message": "该 Docx 不在知识库节点树中"}
            raise
        space = identifier(node.get("space_id"))
        pending = [(identifier(node.get("node_token")), [])]
        seen, result = {pending[0][0]}, []
        while pending:
            parent, parents = pending.pop(0)
            cursor, cursors = None, set()
            while True:
                args = ["wiki", "+node-list", "--space-id", space, "--parent-node-token", parent, "--page-size", "50"]
                if cursor:
                    args += ["--page-token", cursor]
                page = self.cli.call(*args)
                nodes = page.get("nodes")
                if not isinstance(nodes, list):
                    raise CLIError("Wiki 列表缺少 nodes；请检查 CLI 版本")
                for child in nodes:
                    token = identifier(child.get("node_token"))
                    if token in seen:
                        continue
                    seen.add(token)
                    if len(seen) > max_nodes:
                        raise CLIError("子文档发现超过节点上限；请缩小范围，不能将截断结果视为完整")
                    path = parents + [child.get("title", token)]
                    if recursive and child.get("has_child"):
                        pending.append((token, path))
                    if child.get("obj_type") != "docx":
                        continue
                    result.append({k: child.get(k) for k in ("node_token", "obj_token", "obj_type", "title", "has_child")}
                                  | {"url": f"https://{source['host']}/wiki/{token}", "parent_node_token": parent, "path": path})
                if not page.get("has_more"):
                    break
                cursor = page.get("page_token")
                if not cursor or cursor in cursors:
                    raise CLIError("Wiki 分页标记缺失或重复，未获取完整子文档")
                cursors.add(cursor)
        return {"children": result, "recursive": recursive}

    def _document(self, source: dict) -> dict:
        data = self.cli.get(f"/open-apis/docx/v1/documents/{identifier(source['token'])}")
        document = data.get("document", {})
        revision = document.get("revision_id")
        if not isinstance(revision, int) or revision < 0:
            raise CLIError("文档未返回有效 revision_id，无法保证选章一致性")
        return document

    def _blocks(self, source: dict, revision: int) -> list[dict]:
        result, seen, cursors, cursor = [], set(), set(), None
        for _ in range(200):
            params = {"document_revision_id": revision, "page_size": 500}
            if cursor:
                params["page_token"] = cursor
            page = self.cli.get(f"/open-apis/docx/v1/documents/{identifier(source['token'])}/blocks", params)
            items = page.get("items")
            if not isinstance(items, list):
                raise CLIError("文档分页缺少 items；不能将异常当作空文档")
            for block in items:
                bid = block.get("block_id")
                if not bid or bid in seen:
                    raise CLIError("文档分页出现缺失或重复 block_id，未获取完整文档")
                seen.add(bid)
                result.append(block)
            if not page.get("has_more"):
                return self._document_order(result)
            cursor = page.get("page_token")
            if not cursor or cursor in cursors:
                raise CLIError("文档分页标记缺失或重复，未获取完整文档")
            cursors.add(cursor)
        raise CLIError("文档超过分页上限；请缩小需求范围，不能使用截断语料")

    @staticmethod
    def _document_order(blocks: list[dict]) -> list[dict]:
        """API pages need not put table descendants beside their top-level parent."""
        block_map = {b["block_id"]: b for b in blocks}
        children, parents = {}, {}
        for block in blocks:
            bid = block["block_id"]
            ids = list(block.get("children", []))
            if block.get("block_type") == 31:
                ids += block.get("table", {}).get("cells", [])
            children[bid] = list(dict.fromkeys(ids))
            for child in children[bid]:
                if child not in block_map or child == bid:
                    raise CLIError("文档子块缺失或循环，无法保证完整正文")
                if child in parents and parents[child] != bid:
                    raise CLIError("文档子块属于多个父块，无法确定章节范围")
                parents[child] = bid
        for block in blocks:
            bid, parent = block["block_id"], block.get("parent_id")
            if parent in block_map and parent != bid and bid not in parents:
                parents[bid] = parent
                children[parent].append(bid)
        ordered, visited = [], set()
        stack = list(reversed([b["block_id"] for b in blocks if b["block_id"] not in parents]))
        while stack:
            bid = stack.pop()
            if bid in visited:
                raise CLIError("文档块出现循环，无法确定章节范围")
            visited.add(bid)
            ordered.append(block_map[bid])
            stack.extend(reversed(children[bid]))
        if len(ordered) != len(blocks):
            raise CLIError("文档块存在循环或不可达内容，无法确定章节范围")
        return ordered

    def _markdown(self, source: dict) -> str:
        data = self.cli.call("markdown", "+fetch", "--file-token", identifier(source["token"]))
        if not isinstance(data.get("content"), str):
            raise CLIError("Markdown 未返回原文 content")
        return data["content"]

    @staticmethod
    def _docx_sections(blocks: list[dict]) -> list[dict]:
        table_descendants = set()
        block_map = {b["block_id"]: b for b in blocks}
        queue = [cid for b in blocks if b.get("block_type") == 31 for cid in b.get("table", {}).get("cells", [])]
        while queue:
            bid = queue.pop()
            if bid not in table_descendants:
                table_descendants.add(bid)
                queue.extend(block_map.get(bid, {}).get("children", []))
        headings = [{"id": b["block_id"], "title": BlockProcessor.extract_text_from_block(b),
                     "level": b["block_type"] - 2, "position": pos}
                    for pos, b in enumerate(blocks) if 3 <= b.get("block_type", 0) <= 11 and b["block_id"] not in table_descendants]
        stack = []
        for index, heading in enumerate(headings):
            while stack and stack[-1]["level"] >= heading["level"]:
                stack.pop()
            heading["section_path"] = " > ".join([p["title"] for p in stack] + [heading["title"]])
            end = next((h["position"] - 1 for h in headings[index + 1:] if h["level"] <= heading["level"]), len(blocks) - 1)
            heading["range"] = {"start_position": heading["position"], "end_position": end}
            stack.append(heading)
        return headings

    def outline(self, url: str, max_level: int = 4) -> dict:
        if not 1 <= max_level <= 9:
            raise CLIError("标题层级须在 1 到 9 之间")
        source = self.resolve(url)
        if source["type"] == "file":
            raw = self._markdown(source)
            sections = parse_sections(raw)
            return {"source": source, "content_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "sections": [metadata(s) for s in sections if s["level"] <= max_level]}
        document = self._document(source)
        blocks = self._blocks(source, document["revision_id"])
        source["title"] = document.get("title", source.get("title", ""))
        return {"source": source, "revision_id": document["revision_id"], "total_blocks": len(blocks),
                "sections": [s for s in self._docx_sections(blocks) if s["level"] <= max_level]}

    def read(self, outline: dict, ids: list[str], output_dir: Path, doc_key: str, all_content: bool = False) -> dict:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", doc_key):
            raise CLIError("doc-key 必须为小写英文、数字或连字符，最长 80 字符")
        if all_content and ids:
            raise CLIError("--all 与 --section-id 不能同时使用")
        if not all_content and not ids:
            raise CLIError("请先选择章节；全文读取须显式使用 --all 并经用户确认")
        root = output_dir.resolve()
        source = outline["source"]
        identifier(source["token"])
        part_dir = root / "corpus" / "parts"
        manifest_path = part_dir / f"{doc_key}.json"
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (previous["source"]["type"], previous["source"]["token"]) != (source["type"], source["token"]):
                raise CLIError("doc-key 已用于另一篇文档，请使用不同名称")
        media, chunks = [], []
        if source["type"] == "file":
            raw = self._markdown(source)
            if hashlib.sha256(raw.encode()).hexdigest() != outline.get("content_sha256"):
                raise CLIError("Markdown 文档已发生变化，请重新获取目录并确认选章")
            sections = parse_sections(raw)
            chosen = [{"id": "all", "title": "全文", "content": raw}] if all_content else select_sections(sections, ids)
            for section in chosen:
                chunks.append(self._chunk(source, doc_key, section, section["content"]))
        elif source["type"] == "docx":
            if self._document(source)["revision_id"] != outline.get("revision_id"):
                raise CLIError("Docx 文档版本已发生变化，请重新获取目录并确认选章")
            blocks = self._blocks(source, outline["revision_id"])
            sections = self._docx_sections(blocks)
            if len(blocks) != outline.get("total_blocks"):
                raise CLIError("Docx 块数量发生变化，请重新获取目录")
            chosen = [{"id": "all", "title": "全文", "range": {"start_position": 0, "end_position": len(blocks) - 1}}] if all_content else select_sections(sections, ids)
            for section in chosen:
                bounds = section["range"]
                selected = self._with_descendants(blocks, bounds["start_position"], bounds["end_position"])
                text, section_media = BlockProcessor.extract_text_with_media_markers_and_tables(selected)
                for item in section_media:
                    item["section_id"] = section["id"]
                    if item["media_type"] not in {"image", "board"}:
                        item.update(status="unsupported", message="该媒体类型需要手动补充")
                    else:
                        try:
                            root.mkdir(parents=True, exist_ok=True)
                            path = self.cli.media(item, root)
                            text = text.replace(item["expected_path"], str(Path(path).relative_to(root)))
                            item.update(status="downloaded", path=path)
                        except CLIError as exc:
                            item.update(status="failed", error=exc.details)
                            text += f"\n[图片下载失败: block_id={item['block_id']}，需补充视觉信息]\n"
                    media.append(item)
                embedded = BlockProcessor.extract_charts_from_blocks(selected)
                for chart in embedded:
                    if chart.get("chart_type") != "board":
                        media.append({**chart, "media_type": chart["chart_type"], "block_id": chart.get("block_id"),
                                      "token": chart.get("token", ""), "section_id": section["id"],
                                      "status": "needs_context", "message": "内嵌资源需按文档工具指南读取或由用户补充"})
                chunks.append(self._chunk(source, doc_key, section, text))
        else:
            raise CLIError("不支持的 outline 文档类型")
        status = "partial" if any(m["status"] != "downloaded" for m in media) else "complete"
        result = {"source": source, "doc_key": doc_key, "selected_ids": [s["id"] for s in chosen],
                  "status": status, "media": media}
        part_dir.mkdir(parents=True, exist_ok=True)
        (part_dir / f"{doc_key}.md").write_text("\n".join(chunks), encoding="utf-8", newline="")
        manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        corpus = root / "corpus" / "selected-corpus.md"
        with corpus.open("w", encoding="utf-8", newline="") as stream:
            for part in sorted(part_dir.glob("*.md")):
                with part.open(encoding="utf-8", newline="") as content:
                    stream.write(content.read())
                stream.write("\n")
        return result | {"corpus_path": str(corpus), "manifest_path": str(manifest_path)}

    @staticmethod
    def _chunk(source: dict, key: str, section: dict, content: str) -> str:
        # JSON quoting keeps untrusted document titles out of SOURCE comment syntax.
        provenance = json.dumps({"doc_key": key, "url": source["url"], "section_id": section["id"],
                                 "range": section.get("range")}, ensure_ascii=False).replace("--", "\\u002d\\u002d")
        return f"<!-- SOURCE: {provenance} -->\n{content}\n<!-- END SOURCE -->\n"

    @staticmethod
    def _with_descendants(blocks: list[dict], start: int, end: int) -> list[dict]:
        block_map = {b["block_id"]: b for b in blocks}
        chosen = {b["block_id"] for b in blocks[start:end + 1]}
        queue = list(chosen)
        while queue:
            block = block_map[queue.pop()]
            children = list(block.get("children", []))
            if block.get("block_type") == 31:
                children += block.get("table", {}).get("cells", [])
            for cid in children:
                if cid not in block_map:
                    raise CLIError("选中章节的子块缺失，不能输出不完整表格或正文")
                if cid not in chosen:
                    chosen.add(cid)
                    queue.append(cid)
        return [b for b in blocks if b["block_id"] in chosen]
