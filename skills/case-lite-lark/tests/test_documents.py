import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from documents import DocumentReader
from lark_cli import CLIError
from markdown_sections import parse_sections, select_sections


def text_block(bid, text, kind=2, children=None, parent_id="doc"):
    key = "text" if kind == 2 else f"heading{kind - 2}"
    return {"block_id": bid, "block_type": kind, "parent_id": parent_id, "children": children or [], key: {"elements": [{"text_run": {"content": text}}]}}


class FakeCLI:
    def __init__(self, blocks=None):
        self.blocks = blocks or [text_block("h1", "支付", 3), text_block("p1", "amount=100"), text_block("h2", "退款", 3), text_block("p2", "退款原文")]
        self.revision = 7
        self.markdown = "# 支付\r\n原文  \r\n```json\r\n# 不是标题\r\n```\r\n## 子节\r\nx\r\n# 退款\r\ny\r\n"
        self.calls = []
        self.fail_media = False

    def get(self, path, params=None):
        self.calls.append((path, params))
        if path.endswith("/blocks"):
            if not (params or {}).get("page_token"):
                return {"items": self.blocks[:2], "has_more": len(self.blocks) > 2, "page_token": "next"}
            return {"items": self.blocks[2:], "has_more": False}
        return {"document": {"document_id": "doc", "title": "测试文档", "revision_id": self.revision}}

    def call(self, *args):
        self.calls.append(args)
        if args[:2] == ("markdown", "+fetch"):
            return {"content": self.markdown}
        if args[:2] == ("wiki", "+node-get"):
            token = args[args.index("--node-token") + 1]
            return {"node_token": token, "obj_type": "docx", "obj_token": "doc", "space_id": "space", "title": "测试文档"}
        if args[:2] == ("wiki", "+node-list"):
            if "--page-token" not in args:
                return {"nodes": [{"node_token": "child1", "obj_token": "doc1", "obj_type": "docx", "title": "子文档", "has_child": False}], "has_more": True, "page_token": "page2"}
            return {"nodes": [{"node_token": "child2", "obj_token": "doc2", "obj_type": "docx", "title": "子文档2", "has_child": False}], "has_more": False}
        raise AssertionError(args)

    def media(self, media, output_root):
        if self.fail_media:
            raise CLIError("permission_denied", {"code": 403, "message": "denied"})
        path = output_root / media["expected_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-image")
        return str(path.resolve())


class MarkdownTest(unittest.TestCase):
    def test_fences_hierarchy_and_original_crlf_are_preserved(self):
        raw = FakeCLI().markdown
        sections = parse_sections(raw)
        self.assertEqual([s["id"] for s in sections], ["1", "1.1", "2"])
        selected = select_sections(sections, ["1.1", "1", "1"])
        self.assertEqual([s["id"] for s in selected], ["1"])
        self.assertEqual(selected[0]["content"], raw[:raw.index("# 退款")])

    def test_fence_closer_with_info_does_not_close_fence(self):
        sections = parse_sections("# A\n```py\n```not-a-closer\n# hidden\n```\n# B\n")
        self.assertEqual([s["title"] for s in sections], ["A", "B"])

    def test_unknown_or_empty_selection_is_rejected(self):
        for ids in [[], ["missing"]]:
            with self.assertRaises(CLIError):
                select_sections(parse_sections("# A\nx\n"), ids)


class DocumentTest(unittest.TestCase):
    def test_table_cells_beyond_section_boundary_are_included_once(self):
        table = {"block_id": "table", "block_type": 31, "table": {"cells": ["cell1", "cell2"], "property": {"row_size": 1, "column_size": 2}}}
        blocks = [text_block("h1", "支付", 3), table, text_block("h2", "退款", 3), text_block("p2", "退款原文"),
                  {"block_id": "cell1", "block_type": 32, "children": ["value1"]}, text_block("value1", "字段A", parent_id="cell1"),
                  {"block_id": "cell2", "block_type": 32, "children": ["value2"]}, text_block("value2", "字段B", parent_id="cell2")]
        reader = DocumentReader(FakeCLI(blocks))
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h1"], Path(temp), "doc")
            text = Path(result["corpus_path"]).read_text()
            self.assertIn("| 字段A | 字段B |", text)
            self.assertEqual(text.count("字段A"), 1)
            self.assertNotIn("退款原文", text)

    def test_code_blocks_keep_json_and_backticks(self):
        code = {"block_id": "code", "block_type": 14, "code": {"elements": [{"text_run": {"content": '{"amount": 100, "name": "x"}'}}]}}
        reader = DocumentReader(FakeCLI([text_block("h1", "支付", 3), code]))
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h1"], Path(temp), "doc")
            self.assertIn('```\n{"amount": 100, "name": "x"}\n```', Path(result["corpus_path"]).read_text())

    def test_unselected_table_descendants_do_not_leak_into_later_section(self):
        blocks = [text_block("h1", "支付", 3),
                  {"block_id": "table", "block_type": 31, "table": {"cells": ["cell"], "property": {"row_size": 1, "column_size": 1}}},
                  text_block("h2", "退款", 3), text_block("p2", "已选择的退款正文"),
                  {"block_id": "cell", "block_type": 32, "children": ["secret"]},
                  text_block("secret", "不应泄入退款章节", parent_id="cell")]
        reader = DocumentReader(FakeCLI(blocks))
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h2"], Path(temp), "doc")
            text = Path(result["corpus_path"]).read_text()
            self.assertIn("已选择的退款正文", text)
            self.assertNotIn("不应泄入退款章节", text)

    def test_iframe_and_attachment_are_reported_as_unread_resources(self):
        blocks = [text_block("h1", "支付", 3), {"block_id": "figma", "block_type": 26, "iframe": {"component": {"iframe_type": 1, "url": "https://example.com/design"}}},
                  {"block_id": "file", "block_type": 23, "file": {"token": "filetoken", "name": "design.pdf"}}]
        reader = DocumentReader(FakeCLI(blocks))
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h1"], Path(temp), "doc")
            self.assertEqual(result["status"], "partial")
            self.assertEqual({m["media_type"] for m in result["media"]}, {"iframe", "file"})

    def test_table_cell_keeps_more_than_300_blocks_and_legitimate_repetition(self):
        values = [text_block(f"v{i}", f"第{i}行", parent_id="cell") for i in range(301)]
        values += [text_block("repeat1", "再次点击", parent_id="cell"), text_block("repeat2", "再次点击", parent_id="cell")]
        blocks = [text_block("h1", "支付", 3), {"block_id": "table", "block_type": 31, "table": {"cells": ["cell"], "property": {"row_size": 1, "column_size": 1}}},
                  {"block_id": "cell", "block_type": 32, "children": [b["block_id"] for b in values]}, *values]
        reader = DocumentReader(FakeCLI(blocks))
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h1"], Path(temp), "doc")
            text = Path(result["corpus_path"]).read_text()
            self.assertIn("第300行", text)
            self.assertEqual(text.count("再次点击"), 2)

    def test_text_link_keeps_target_url(self):
        block = text_block("p", "协议接口")
        block["text"]["elements"][0]["text_run"]["text_element_style"] = {"link": {"url": "https://example.com/api/v2/pay"}}
        reader = DocumentReader(FakeCLI([text_block("h1", "支付", 3), block]))
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h1"], Path(temp), "doc")
            self.assertIn("[协议接口](https://example.com/api/v2/pay)", Path(result["corpus_path"]).read_text())

    def test_outline_only_contains_metadata_and_pins_revision(self):
        cli = FakeCLI()
        outline = DocumentReader(cli).outline("https://example.feishu.cn/docx/doc")
        self.assertEqual(outline["revision_id"], 7)
        self.assertEqual([s["id"] for s in outline["sections"]], ["h1", "h2"])
        self.assertNotIn("amount=100", json.dumps(outline))
        self.assertEqual([c[1]["page_token"] for c in cli.calls if c[0].endswith("/blocks") and "page_token" in c[1]], ["next"])

    def test_selected_corpus_preserves_text_excludes_other_sections_and_is_idempotent(self):
        reader = DocumentReader(FakeCLI())
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = reader.read(outline, ["h1"], root, "01-backend")
            content = Path(first["corpus_path"]).read_text()
            self.assertIn("amount=100", content)
            self.assertNotIn("退款原文", content)
            reader.read(outline, ["h1"], root, "01-backend")
            self.assertEqual(Path(first["corpus_path"]).read_text(), content)

    def test_document_change_rejects_stale_selection_before_writing(self):
        cli = FakeCLI()
        reader = DocumentReader(cli)
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        cli.revision += 1
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(CLIError, "变化"):
            reader.read(outline, ["h1"], Path(temp), "doc")

    def test_native_markdown_change_is_detected_and_no_media_is_downloaded(self):
        cli = FakeCLI()
        reader = DocumentReader(cli)
        outline = reader.outline("https://example.feishu.cn/file/mdtoken")
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["1"], Path(temp), "md")
            self.assertEqual(result["media"], [])
            self.assertIn("# 不是标题", Path(result["corpus_path"]).read_text())
            cli.markdown += "changed"
            with self.assertRaisesRegex(CLIError, "变化"):
                reader.read(outline, ["1"], Path(temp), "md")

    def test_children_are_metadata_only_and_include_all_pages(self):
        cli = FakeCLI()
        result = DocumentReader(cli).children("https://example.feishu.cn/wiki/parent", recursive=True)
        self.assertEqual([n["node_token"] for n in result["children"]], ["child1", "child2"])
        self.assertTrue(all(isinstance(c, tuple) and c[0] == "wiki" for c in cli.calls))

    def test_discovery_traverses_non_docx_parent_without_reading_its_body(self):
        class Nested(FakeCLI):
            def call(self, *args):
                if args[:2] == ("wiki", "+node-list"):
                    parent = args[args.index("--parent-node-token") + 1]
                    node = {"node_token": "folder", "obj_token": "sheet", "obj_type": "sheet", "title": "设计汇总", "has_child": True} if parent == "parent" else {"node_token": "child", "obj_token": "doc", "obj_type": "docx", "title": "功能需求", "has_child": False}
                    return {"nodes": [node], "has_more": False}
                return super().call(*args)
        children = DocumentReader(Nested()).children("https://example.feishu.cn/wiki/parent", recursive=True)["children"]
        self.assertEqual([c["node_token"] for c in children], ["child"])
        self.assertEqual(children[0]["path"], ["设计汇总", "功能需求"])

    def test_pagination_missing_or_repeated_cursor_is_not_partial_success(self):
        class Broken(FakeCLI):
            def get(self, path, params=None):
                if path.endswith("/blocks"):
                    return {"items": [text_block("same", "x")], "has_more": True, "page_token": "stuck"}
                return super().get(path, params)
        with self.assertRaises(CLIError):
            DocumentReader(Broken()).outline("https://example.feishu.cn/docx/doc")

    def test_all_content_requires_explicit_choice(self):
        reader = DocumentReader(FakeCLI())
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(CLIError):
            reader.read(outline, [], Path(temp), "doc")

    def test_invalid_doc_key_cannot_escape_task_directory(self):
        reader = DocumentReader(FakeCLI())
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(CLIError):
            reader.read(outline, ["h1"], Path(temp), "../escape")

    def test_media_failure_is_visible_and_text_is_retained(self):
        cli = FakeCLI([text_block("h1", "支付", 3), {"block_id": "image", "block_type": 27, "image": {"token": "imagetoken"}}, text_block("h2", "退款", 3)])
        reader = DocumentReader(cli)
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        cli.fail_media = True
        with tempfile.TemporaryDirectory() as temp:
            result = reader.read(outline, ["h1"], Path(temp), "doc")
            self.assertEqual(result["media"][0]["status"], "failed")
            self.assertEqual(result["status"], "partial")
            self.assertIn("图片下载失败", Path(result["corpus_path"]).read_text())

    def test_doc_key_collision_with_another_source_is_rejected(self):
        reader = DocumentReader(FakeCLI())
        outline = reader.outline("https://example.feishu.cn/docx/doc")
        other = dict(outline, source=dict(outline["source"], token="different"))
        with tempfile.TemporaryDirectory() as temp:
            reader.read(outline, ["h1"], Path(temp), "doc")
            with self.assertRaises(CLIError):
                reader.read(other, ["h1"], Path(temp), "doc")


if __name__ == "__main__":
    unittest.main()
