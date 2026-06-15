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


if __name__ == "__main__":
    unittest.main()
