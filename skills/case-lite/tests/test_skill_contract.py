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

    def test_skill_routes_native_drive_markdown_through_mcp(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        guide = (SKILL_ROOT / "references" / "feishu-tools-guide.md").read_text(encoding="utf-8")
        readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")

        for document in (skill, guide):
            self.assertIn("get_markdown_file_sections", document)
            self.assertIn("/file/TOKEN", document)
            self.assertIn("section_ids", document)
            self.assertIn("原始 Markdown", document)

        self.assertIn("原生 Markdown", skill)
        self.assertIn("Docx", skill)
        self.assertIn("不下载图片", skill)
        self.assertIn("/file/TOKEN", readme)


    def test_skill_documents_nested_scene_contract(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("编号即路径", skill)
        self.assertIn("场景分层规则", skill)
        self.assertIn("何时拆子场景", skill)
        # 混搭是硬约束，必须在 SKILL.md 里写明
        self.assertIn("不允许混搭", skill)
        # 标题级别不参与解析，必须写明以免生成时纠结层级
        self.assertIn("标题级别只影响阅读观感", skill)

    def test_layering_review_is_a_mandatory_step_with_visible_output(self):
        """分层复核必须是流程里的独立步骤，且结论对用户可见。

        1.1.0 的教训：判据写在 full.md 格式规范里、Step 3 只给一句交叉引用时，
        agent 稳定跳过分层评估直接产出扁平结构，而且跳过与「评估后不拆」
        在输出上无法区分。修复的关键不是把判据写得更好，而是
        (a) 判据和决策点放在同一处，(b) 强制产出可见的复核结论。
        """
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        # (a) 决策点是独立步骤，且标明必做
        self.assertIn("3d. 场景分层复核 [必做]", skill)
        # (b) 判据与决策点同处：何时拆子场景必须在 3d 之后、Step 4 之前
        idx_3d = skill.index("3d. 场景分层复核")
        idx_step4 = skill.index("### Step 4：生成完整用例")
        idx_criteria = skill.index("何时拆子场景（完整判据）")
        self.assertLess(idx_3d, idx_criteria, "判据必须和决策点在一起，不能留在格式规范章节")
        self.assertLess(idx_criteria, idx_step4)
        # (c) 复核结论必须可见，且覆盖全部场景——否则跳过不可检测
        self.assertIn("分层复核：", skill)
        self.assertIn("复核表必须覆盖所有顶层场景", skill)
        # (d) Step 4 必须给出合法回头路，否则确认后的结构就被焊死了
        step4 = skill[idx_step4:]
        self.assertIn("structure.md 是结构的唯一真相", step4)

    def test_layering_review_table_is_not_persisted_into_structure_md(self):
        """复核表只出现在给用户的确认消息里。

        写进 structure.md 会污染下游：Step 4 按 structure.md 展开，
        表格里的场景名会被当成内容。
        """
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`structure.md` 里**不写**这张表", skill)


if __name__ == "__main__":
    unittest.main()
