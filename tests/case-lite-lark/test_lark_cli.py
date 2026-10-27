import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "case-lite-lark" / "scripts"))
from lark_cli import CLIError, LarkCLI


class LarkCLITest(unittest.TestCase):
    def run_result(self, payload, code=0, stderr=""):
        return subprocess.CompletedProcess([], code, json.dumps(payload), stderr)

    @patch("lark_cli.subprocess.run")
    def test_raw_get_uses_user_identity_and_unwraps_one_envelope(self, run):
        run.return_value = self.run_result({"ok": True, "identity": "user", "data": {"items": []}})
        cli = LarkCLI(cwd=Path.cwd())
        self.assertEqual(cli.get("/open-apis/docx/v1/documents/doc/blocks", {"page_size": 500}), {"items": []})
        argv = run.call_args.args[0]
        self.assertEqual(argv[:4], ["lark-cli", "api", "GET", "/open-apis/docx/v1/documents/doc/blocks"])
        self.assertEqual(argv[argv.index("--as") + 1], "user")
        self.assertEqual(json.loads(argv[argv.index("--params") + 1]), {"page_size": 500})
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    @patch("lark_cli.subprocess.run")
    def test_stderr_scope_error_preserves_recovery_but_redacts_credentials(self, run):
        error = {"type": "authorization", "code": 999, "message": "Bearer private-token", "missing_scopes": ["wiki:node:retrieve"], "hint": "login", "access_token": "private-token"}
        run.return_value = subprocess.CompletedProcess([], 1, "", json.dumps({"ok": False, "error": error}))
        with self.assertRaises(CLIError) as raised:
            LarkCLI().call("wiki", "+node-get", "--node-token", "fake")
        self.assertEqual(raised.exception.details["missing_scopes"], ["wiki:node:retrieve"])
        self.assertNotIn("private-token", json.dumps(raised.exception.details))

    @patch("lark_cli.subprocess.run")
    def test_bot_fallback_is_rejected(self, run):
        run.return_value = self.run_result({"ok": True, "identity": "bot", "data": {}})
        with self.assertRaisesRegex(CLIError, "user"):
            LarkCLI().call("wiki", "+node-get", "--node-token", "fake")

    @patch("lark_cli.subprocess.run")
    def test_business_error_with_zero_exit_is_rejected(self, run):
        run.return_value = self.run_result({"ok": False, "error": {"code": 131006, "message": "denied"}})
        with self.assertRaises(CLIError):
            LarkCLI().call("wiki", "+node-get", "--node-token", "fake")

    @patch("lark_cli.subprocess.run")
    def test_parent_help_or_invalid_json_is_not_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "Usage: lark-cli wiki", "")
        with self.assertRaisesRegex(CLIError, "JSON"):
            LarkCLI().call("wiki", "+node-get", "--node-token", "fake")

    @patch("lark_cli.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_cli_has_actionable_error(self, run):
        with self.assertRaisesRegex(CLIError, "lark-cli"):
            LarkCLI().call("wiki", "+node-get", "--node-token", "fake")

    @patch("lark_cli.subprocess.run", side_effect=subprocess.TimeoutExpired("lark-cli", 120))
    def test_timeout_does_not_dump_partial_output(self, run):
        with self.assertRaisesRegex(CLIError, "超时"):
            LarkCLI().call("wiki", "+node-get", "--node-token", "fake")

    def test_transport_cannot_be_used_for_auth_or_mutations(self):
        for args in [("auth", "login"), ("docs", "+create"), ("api", "POST", "/open-apis/test")]:
            with self.subTest(args=args), self.assertRaises(CLIError):
                LarkCLI().call(*args)

    def test_whiteboard_uses_preview_image_path_and_returns_absolute_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            path = root / "feishu_images/board.png"
            path.parent.mkdir()
            path.write_bytes(b"fake")
            cli = LarkCLI(cwd=root)
            with patch.object(cli, "call", return_value={"preview_image_path": str(path)}) as call:
                saved = cli.media({"media_type": "board", "token": "boardtoken", "expected_path": "feishu_images/board.png"}, root)
            self.assertEqual(saved, str(path))
            self.assertEqual(call.call_args.args[:2], ("whiteboard", "+export"))
            self.assertEqual(call.call_args.args[call.call_args.args.index("--output") + 1], "feishu_images/board.png")

    def test_media_empty_file_and_unexpected_external_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cli = LarkCLI(cwd=root)
            with patch.object(cli, "call", return_value={"saved_path": str(root / "missing.png")}):
                with self.assertRaises(CLIError):
                    cli.media({"media_type": "image", "token": "image", "expected_path": "feishu_images/image.png"}, root)


if __name__ == "__main__":
    unittest.main()
