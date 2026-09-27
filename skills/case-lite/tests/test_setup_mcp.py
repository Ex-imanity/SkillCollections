import importlib.util
import io
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "setup_mcp.py"
SPEC = importlib.util.spec_from_file_location("case_lite_setup_mcp", SCRIPT_PATH)
setup_mcp = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["case_lite_setup_mcp"] = setup_mcp
SPEC.loader.exec_module(setup_mcp)

TEST_APP_ID = "app-id"
TEST_APP_SECRET = "test-secret-placeholder"


class MergeTest(unittest.TestCase):
    def test_merge_claude_code_config_preserves_existing_servers(self):
        existing = {
            "mcpServers": {
                "existing": {
                    "command": "node",
                    "args": ["server.js"],
                }
            },
            "otherSetting": True,
        }

        merged = setup_mcp.merge_claude_code_config(
            existing,
            feishu_app_id=TEST_APP_ID,
            feishu_app_secret=TEST_APP_SECRET,
        )

        self.assertEqual(merged["mcpServers"]["existing"]["command"], "node")
        self.assertTrue(merged["otherSetting"])
        self.assertEqual(
            merged["mcpServers"]["feishu-docx-blocks"],
            {
                "command": "uvx",
                "args": ["feishu-docx-blocks@latest"],
                "type": "stdio",
                "env": {
                    "FEISHU_APP_ID": TEST_APP_ID,
                    "FEISHU_APP_SECRET": TEST_APP_SECRET,
                },
            },
        )
        self.assertEqual(
            merged["mcpServers"]["Banshan"],
            {
                "type": "streamable-http",
                "url": setup_mcp.BANSHAN_MCP_URL,
            },
        )

    def test_merge_claude_code_config_keeps_existing_feishu_when_not_writing(self):
        existing = {
            "mcpServers": {
                "feishu-docx-blocks": {
                    "command": "python",
                    "args": ["-m", "feishu_from_source"],
                }
            }
        }

        merged = setup_mcp.merge_claude_code_config(
            existing,
            feishu_app_id=TEST_APP_ID,
            feishu_app_secret=TEST_APP_SECRET,
            write_feishu=False,
            write_banshan=True,
        )

        # F2: a custom/source feishu install must survive a banshan-only fix.
        self.assertEqual(
            merged["mcpServers"]["feishu-docx-blocks"]["command"], "python"
        )
        self.assertIn("Banshan", merged["mcpServers"])

    def test_merge_codex_config_preserves_existing_toml(self):
        existing = """
model = "gpt-5"

[mcp_servers.existing]
command = "node"
args = ["server.js"]
"""

        merged = setup_mcp.merge_codex_config(
            existing,
            feishu_app_id=TEST_APP_ID,
            feishu_app_secret=TEST_APP_SECRET,
        )

        self.assertIn('model = "gpt-5"', merged)
        self.assertIn("[mcp_servers.existing]", merged)
        self.assertIn('command = "node"', merged)
        self.assertIn("[mcp_servers.feishu-docx-blocks]", merged)
        self.assertIn('command = "uvx"', merged)
        self.assertIn('args = ["feishu-docx-blocks@latest"]', merged)
        self.assertIn("[mcp_servers.feishu-docx-blocks.env]", merged)
        self.assertIn(f'FEISHU_APP_ID = "{TEST_APP_ID}"', merged)
        self.assertIn(f'FEISHU_APP_SECRET = "{TEST_APP_SECRET}"', merged)
        self.assertIn("[mcp_servers.banshan]", merged)
        self.assertIn(f'url = "{setup_mcp.BANSHAN_MCP_URL}"', merged)

    def test_merge_codex_config_keeps_existing_feishu_when_not_writing(self):
        existing = """
[mcp_servers.feishu-docx-blocks]
command = "python"
args = ["-m", "feishu_from_source"]
"""

        merged = setup_mcp.merge_codex_config(
            existing,
            feishu_app_id=TEST_APP_ID,
            feishu_app_secret=TEST_APP_SECRET,
            write_feishu=False,
            write_banshan=True,
        )

        self.assertIn('command = "python"', merged)
        self.assertNotIn("feishu-docx-blocks@latest", merged)
        self.assertIn("[mcp_servers.banshan]", merged)

    def test_merge_codex_config_replaces_table_with_inline_comment(self):
        existing = """
[mcp_servers.feishu-docx-blocks] # user note
command = "python"
args = ["-m", "old_feishu"]

[mcp_servers.feishu-docx-blocks.env]
FEISHU_APP_ID = "old-id"
FEISHU_APP_SECRET = "old-secret"

[mcp_servers.existing]
command = "node"
"""

        merged = setup_mcp.merge_codex_config(
            existing,
            feishu_app_id=TEST_APP_ID,
            feishu_app_secret=TEST_APP_SECRET,
            write_feishu=True,
            write_banshan=False,
        )

        parsed = tomllib.loads(merged)
        self.assertEqual(parsed["mcp_servers"]["existing"]["command"], "node")
        self.assertEqual(
            parsed["mcp_servers"]["feishu-docx-blocks"]["args"],
            ["feishu-docx-blocks@latest"],
        )
        self.assertNotIn("old_feishu", merged)


class PathDetectionTest(unittest.TestCase):
    """F1: path detection must flag ambiguity instead of silently guessing."""

    def _home_with(self, files: list[str]) -> tempfile.TemporaryDirectory:
        tmp = tempfile.TemporaryDirectory()
        home = Path(tmp.name)
        for rel in files:
            path = home / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        return tmp

    def test_only_new_path_exists_is_unambiguous(self):
        with self._home_with([".claude/.claude.json"]) as tmp:
            choice = setup_mcp.detect_claude_code_config(Path(tmp))
            self.assertFalse(choice.ambiguous)
            self.assertEqual(choice.path, Path(tmp) / ".claude" / ".claude.json")

    def test_only_old_path_exists_is_unambiguous(self):
        with self._home_with([".claude.json"]) as tmp:
            choice = setup_mcp.detect_claude_code_config(Path(tmp))
            self.assertFalse(choice.ambiguous)
            self.assertEqual(choice.path, Path(tmp) / ".claude.json")

    def test_both_paths_exist_is_ambiguous(self):
        with self._home_with([".claude/.claude.json", ".claude.json"]) as tmp:
            choice = setup_mcp.detect_claude_code_config(Path(tmp))
            self.assertTrue(choice.ambiguous)
            self.assertEqual(len(choice.candidates), 2)
            self.assertIn("cc-switch", choice.note)

    def test_neither_path_exists_defaults_to_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            choice = setup_mcp.detect_claude_code_config(Path(tmp))
            self.assertFalse(choice.ambiguous)
            self.assertEqual(choice.path, Path(tmp) / ".claude" / ".claude.json")


class CredResolutionTest(unittest.TestCase):
    """F4: diagnostics should read existing creds, not only env vars."""

    def test_reads_creds_from_claude_code_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".claude.json"
            path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "feishu-docx-blocks": {
                                "env": {
                                    "FEISHU_APP_ID": TEST_APP_ID,
                                    "FEISHU_APP_SECRET": TEST_APP_SECRET,
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            app_id, secret = setup_mcp.read_claude_code_creds(path)
            self.assertEqual(app_id, TEST_APP_ID)
            self.assertEqual(secret, TEST_APP_SECRET)

    def test_reads_creds_from_codex_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                "[mcp_servers.feishu-docx-blocks.env]\n"
                f'FEISHU_APP_ID = "{TEST_APP_ID}"\n'
                f'FEISHU_APP_SECRET = "{TEST_APP_SECRET}"\n',
                encoding="utf-8",
            )
            app_id, secret = setup_mcp.read_codex_creds(path)
            self.assertEqual(app_id, TEST_APP_ID)
            self.assertEqual(secret, TEST_APP_SECRET)


class ReportTest(unittest.TestCase):
    def test_report_redacts_secret_and_flags_missing_uv(self):
        report = setup_mcp.build_diagnostic_report(
            agent="codex",
            config_path=Path("/tmp/config.toml"),
            uv_available=False,
            python_version="3.13.0",
            feishu_configured=True,
            feishu_uses_latest=False,
            banshan_configured=True,
            feishu_app_id=TEST_APP_ID,
            feishu_app_secret=TEST_APP_SECRET,
            cred_source="现有配置",
        )

        text = report.to_markdown()

        self.assertIn(TEST_APP_ID, text)
        self.assertIn("3.13.0", text)
        self.assertIn("***", text)
        self.assertNotIn(TEST_APP_SECRET, text)
        # meaningful: uv_available=False must surface the install section
        self.assertIn("需要先安装 uv", text)
        self.assertIn("现有配置", text)

    def test_report_shows_ambiguity_warning(self):
        report = setup_mcp.build_diagnostic_report(
            agent="claude-code",
            config_path=Path("/home/u/.claude/.claude.json"),
            feishu_configured=False,
            feishu_uses_latest=False,
            banshan_configured=False,
            feishu_app_id=None,
            feishu_app_secret=None,
            config_ambiguous=True,
            config_candidates=[
                Path("/home/u/.claude/.claude.json"),
                Path("/home/u/.claude.json"),
            ],
            config_note="同时检测到两个路径，cc-switch 可能覆盖。",
        )

        text = report.to_markdown()
        self.assertIn("配置路径不确定", text)
        self.assertIn("--config", text)


class ApplyTest(unittest.TestCase):
    def test_apply_claude_code_config_creates_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / ".claude.json"
            config_path.write_text(json.dumps({"mcpServers": {}}, ensure_ascii=False), encoding="utf-8")

            backup_path = setup_mcp.apply_claude_code_config(
                config_path,
                feishu_app_id=TEST_APP_ID,
                feishu_app_secret=TEST_APP_SECRET,
            )

            self.assertIsNotNone(backup_path)
            self.assertTrue(backup_path.exists())
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("feishu-docx-blocks", updated["mcpServers"])
            self.assertIn("Banshan", updated["mcpServers"])

    def test_apply_returns_none_backup_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"

            backup_path = setup_mcp.apply_codex_config(
                config_path,
                feishu_app_id=TEST_APP_ID,
                feishu_app_secret=TEST_APP_SECRET,
            )

            self.assertIsNone(backup_path)
            self.assertTrue(config_path.exists())
            self.assertIn("[mcp_servers.feishu-docx-blocks]", config_path.read_text(encoding="utf-8"))


class CliTest(unittest.TestCase):
    def test_replace_feishu_reuses_existing_creds_when_env_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"
            config_path.write_text(
                "[mcp_servers.feishu-docx-blocks]\n"
                'command = "uvx"\n'
                'args = ["feishu-docx-blocks==0.1"]\n'
                "\n"
                "[mcp_servers.feishu-docx-blocks.env]\n"
                f'FEISHU_APP_ID = "{TEST_APP_ID}"\n'
                f'FEISHU_APP_SECRET = "{TEST_APP_SECRET}"\n',
                encoding="utf-8",
            )

            with (
                mock.patch.dict(setup_mcp.os.environ, {}, clear=True),
                mock.patch("sys.stdout", new_callable=io.StringIO),
                mock.patch("sys.stderr", new_callable=io.StringIO),
            ):
                exit_code = setup_mcp.main(
                    [
                        "--agent",
                        "codex",
                        "--config",
                        str(config_path),
                        "--fix",
                        "--yes",
                        "--replace-feishu",
                    ]
                )

            self.assertEqual(exit_code, 0)
            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            feishu = parsed["mcp_servers"]["feishu-docx-blocks"]
            self.assertEqual(feishu["args"], ["feishu-docx-blocks@latest"])
            self.assertEqual(feishu["env"]["FEISHU_APP_ID"], TEST_APP_ID)
            self.assertEqual(feishu["env"]["FEISHU_APP_SECRET"], TEST_APP_SECRET)


if __name__ == "__main__":
    unittest.main()
