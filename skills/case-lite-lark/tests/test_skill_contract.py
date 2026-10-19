import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SkillContractTest(unittest.TestCase):
    def test_packaged_markdown_links_do_not_depend_on_other_skills(self):
        for path in ROOT.rglob("*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if target.startswith(("https://", "http://", "#")):
                    continue
                resolved = (path.parent / target.split("#")[0]).resolve()
                with self.subTest(file=path.name, target=target):
                    self.assertTrue(resolved.is_relative_to(ROOT.resolve()))
                    self.assertTrue(resolved.exists())

    def test_script_imports_do_not_require_mcp_or_external_python_packages(self):
        import ast
        allowed = set(getattr(__import__("sys"), "stdlib_module_names")) | {p.stem for p in (ROOT / "scripts").glob("*.py")}
        for path in (ROOT / "scripts").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for name in names:
                    with self.subTest(file=path.name, module=name):
                        self.assertIn(name.split(".")[0], allowed)

    def test_evals_cover_discovery_selection_and_partial_media(self):
        data = json.loads((ROOT / "evals/evals.json").read_text())
        self.assertEqual(data["skill_name"], ROOT.name)
        self.assertGreaterEqual(len(data["evals"]), 3)
        self.assertEqual(len({e["id"] for e in data["evals"]}), len(data["evals"]))
        self.assertTrue(all(e["assertions"] for e in data["evals"]))

    def test_style_and_workflow_agree_on_preconditions_and_priority(self):
        style = (ROOT / "assets/case-learning.md").read_text()
        self.assertIn("前置条件融入执行步骤第一步", style)
        self.assertIn("full.md 不自动生成 P0/P1/P2", style)


if __name__ == "__main__":
    unittest.main()
