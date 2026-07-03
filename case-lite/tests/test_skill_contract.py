import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class CaseLiteSkillContractTest(unittest.TestCase):
    def test_skill_requires_recursive_child_document_discovery(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("get_child_documents", skill)
        self.assertIn("递归", skill)
        self.assertIn("fetch_all=true", skill)
        self.assertIn("include_non_docx=false", skill)
        self.assertIn("has_child", skill)
        self.assertIn("同类文档", skill)
        self.assertIn("用户确认纳入", skill)

    def test_feishu_guide_documents_child_document_tool(self):
        guide = (SKILL_ROOT / "references" / "feishu-tools-guide.md").read_text(encoding="utf-8")

        self.assertIn("get_child_documents", guide)
        self.assertIn("递归", guide)
        self.assertIn("fetch_all=true", guide)
        self.assertIn("include_non_docx=false", guide)

    def test_skill_uses_progressive_mcp_setup_flow(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("setup_mcp.py", skill)
        self.assertIn("用户同意", skill)
        self.assertIn("渐进式披露", skill)
        self.assertIn("FEISHU_APP_ID", skill)
        self.assertIn("FEISHU_APP_SECRET", skill)
        self.assertIn("不要在 skill 中写入默认凭证", skill)

    def test_install_reference_exists_without_plaintext_secret(self):
        reference = (SKILL_ROOT / "references" / "install-mcp.md").read_text(encoding="utf-8")

        self.assertIn("Claude Code", reference)
        self.assertIn("Codex", reference)
        self.assertIn("setup_mcp.py", reference)
        self.assertIn("FEISHU_APP_SECRET", reference)
        self.assertNotIn("drRCI", reference)

    def test_skill_documents_safe_write_contract(self):
        """F1/F2/F3 must stay documented so the write flow can't silently regress."""
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

        # F1: ambiguous Claude Code path is not silently guessed
        self.assertIn("--config", skill)
        self.assertIn(".claude/.claude.json", skill)
        # F2: existing feishu-docx-blocks not clobbered by default
        self.assertIn("--replace-feishu", skill)
        # F3: close Claude Code before writing
        self.assertIn("退出 Claude Code", skill)

    def test_install_reference_documents_path_ambiguity_and_no_clobber(self):
        reference = (SKILL_ROOT / "references" / "install-mcp.md").read_text(encoding="utf-8")

        self.assertIn("--replace-feishu", reference)
        self.assertIn("cc-switch", reference)
        self.assertIn("不确定", reference)
        self.assertIn("连通", reference)


if __name__ == "__main__":
    unittest.main()
