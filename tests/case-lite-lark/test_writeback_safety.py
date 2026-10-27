import importlib.util
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("lark_writeback_safety", Path(__file__).resolve().parents[2] / "skills" / "case-lite-lark" / "scripts/writeback.py")
writeback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(writeback)

VALID = """# 完整用例
## 场景1：登录
### 测试点1.1：成功
#### 执行步骤
1. 输入正确凭证
#### 预期结果
1. 登录成功
"""


def response(data, **extra):
    return {"result": {"content": [{"type": "text", "text": json.dumps({"code": 0, "data": data})}], **extra}}


def case(nodes):
    return response({"caseContent": json.dumps({"root": {"children": nodes}})})


class WriteSafetyTest(unittest.TestCase):
    def invoke(self, markdown, rpc, *flags):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "full.md"
            path.write_text(markdown)
            with patch.object(sys, "argv", ["writeback.py", str(path), "--case-id", "123", *flags]), patch.object(writeback, "mcp_call", side_effect=rpc) as call:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    result = writeback.main()
                logs = list((Path(temp) / "writeback").glob("writeback-log.json"))
                log = json.loads(logs[0].read_text()) if logs else {}
                return result, call.call_args_list, log

    def test_write_requires_explicit_confirm_flag(self):
        result, calls, _ = self.invoke(VALID, [])
        self.assertEqual(result, 2)
        self.assertEqual(calls, [])

    def test_warnings_block_network_even_with_confirmation(self):
        result, calls, _ = self.invoke(VALID.replace("测试点1.1", "测试点1.3"), [], "--confirm")
        self.assertEqual(result, 2)
        self.assertEqual(calls, [])

    def test_existing_case_is_not_silently_appended(self):
        result, calls, _ = self.invoke(VALID, [case([{"data": {"text": "existing"}, "children": []}])], "--confirm")
        self.assertEqual(result, 1)
        self.assertEqual([c.args[0] for c in calls], ["testCaseDetail"])

    def test_failed_precheck_stops_write(self):
        result, calls, _ = self.invoke(VALID, [{"error": {"message": "network"}}], "--confirm")
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)

    def test_iserror_in_tool_result_is_not_success(self):
        result, calls, log = self.invoke(VALID, [case([]), response({}, isError=True)], "--confirm")
        self.assertEqual(result, 1)
        self.assertFalse(log.get("success", False))

    def test_readback_must_match_inserted_tree(self):
        result, calls, log = self.invoke(VALID, [case([]), response({}), case([])], "--confirm")
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 3)
        self.assertFalse(log["success"])

    def test_readback_compares_content_not_only_count(self):
        nodes = writeback.strip_internal_keys(writeback.parse_full_md(VALID))
        nodes[0]["children"][0]["data"]["text"] = "wrong"
        result, _, log = self.invoke(VALID, [case([]), response({}), case(nodes)], "--confirm")
        self.assertEqual(result, 1)
        self.assertFalse(log["success"])

    def test_matching_readback_reports_success(self):
        nodes = writeback.strip_internal_keys(writeback.parse_full_md(VALID))
        result, _, log = self.invoke(VALID, [case([]), response({}), case(nodes)], "--confirm")
        self.assertEqual(result, 0)
        self.assertTrue(log["success"])

    def test_orphan_json_continuation_blocks_write_instead_of_losing_input(self):
        text = VALID.replace("1. 输入正确凭证", '1. 输入参数：\n   {"userId":"test","count":2}')
        result, calls, _ = self.invoke(text, [], "--confirm")
        self.assertEqual(result, 2)
        self.assertEqual(calls, [])

    def test_missing_expected_result_blocks_write(self):
        text = VALID[:VALID.index("#### 预期结果")]
        result, calls, _ = self.invoke(text, [], "--confirm")
        self.assertEqual(result, 2)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
