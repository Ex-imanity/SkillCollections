"""Verify that each skill directory is a self-contained runtime distribution."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"


def bundles():
    return sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir())


class SkillDistributionTest(unittest.TestCase):
    def test_skill_directories_contain_no_development_payload(self):
        development = {"tests", "evals", "fixtures", "__pycache__", ".pytest_cache"}
        for bundle in bundles():
            with self.subTest(skill=bundle.name):
                self.assertTrue((bundle / "SKILL.md").is_file())
                unwanted = [
                    str(path.relative_to(bundle))
                    for path in bundle.rglob("*")
                    if (path.is_dir() and path.name in development)
                    or (path.is_file() and (path.suffix == ".pyc" or path.name.startswith("test_")))
                ]
                self.assertEqual([], unwanted)

    def test_relative_markdown_links_stay_inside_runtime_bundle(self):
        for bundle in bundles():
            for path in bundle.rglob("*.md"):
                text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
                for target in re.findall(r"\]\(([^)\s]+)\)", text):
                    parsed = urlsplit(target)
                    if parsed.scheme or not parsed.path:
                        continue
                    resolved = (path.parent / unquote(parsed.path)).resolve()
                    with self.subTest(skill=bundle.name, file=str(path.relative_to(bundle)), target=target):
                        self.assertTrue(resolved.is_relative_to(bundle.resolve()))
                        self.assertTrue(resolved.exists())

    def test_evaluation_inputs_are_relative_to_development_manifest(self):
        manifests = sorted((REPO_ROOT / "evals").glob("*/evals.json"))
        self.assertTrue(manifests, "Repository-level evaluation manifests are missing")
        for manifest in manifests:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest.parent.name, data["skill_name"])
            ids = [item["id"] for item in data["evals"]]
            self.assertEqual(len(ids), len(set(ids)))
            for case in data["evals"]:
                for entry in case.get("files", []):
                    resolved = (manifest.parent / entry).resolve()
                    with self.subTest(manifest=str(manifest), case=case["id"], path=entry):
                        self.assertTrue(resolved.is_relative_to(manifest.parent.resolve()))
                        self.assertTrue(resolved.is_file())

    def test_literal_runtime_asset_paths_exist_inside_bundle(self):
        for bundle in bundles():
            for path in bundle.rglob("*.md"):
                for target in re.findall(r"`((?:references|assets|scripts|examples)/[^`\n]+)`", path.read_text()):
                    if any(char in target for char in "*?<> {}") or target.endswith("/"):
                        continue
                    resolved = (bundle / target.split("#", 1)[0]).resolve()
                    with self.subTest(skill=bundle.name, file=str(path.relative_to(bundle)), target=target):
                        self.assertTrue(resolved.is_relative_to(bundle.resolve()))
                        self.assertTrue(resolved.exists())

    def test_copied_skill_scripts_import_without_repository_or_dev_assets(self):
        program = """
import importlib, sys
from pathlib import Path
bundle = Path(sys.argv[1])
sys.path[:0] = [str(bundle), str(bundle / 'scripts')]
for path in sorted((bundle / 'scripts').glob('*.py')):
    if path.name != '__init__.py':
        importlib.import_module('scripts.' + path.stem)
"""
        for bundle in bundles():
            if not (bundle / "scripts").is_dir():
                continue
            with self.subTest(skill=bundle.name), tempfile.TemporaryDirectory() as directory:
                copied = Path(directory) / bundle.name
                shutil.copytree(bundle, copied, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", program, str(copied)],
                    cwd=directory, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_copied_mrs_skill_initializes_from_packaged_templates(self):
        with tempfile.TemporaryDirectory(prefix=".test-mrs-", dir=REPO_ROOT) as directory:
            copied = Path(directory) / "context-resilient-task"
            shutil.copytree(SKILLS_ROOT / copied.name, copied)
            state = Path(directory) / "project" / ".task-state"
            initialized = subprocess.run(
                [sys.executable, "-B", str(copied / "scripts/init_mrs.py"),
                 "--dir", str(state), "--goal", "Standalone bundle check", "--complexity", "small"],
                cwd=directory, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
            self.assertTrue((state / "task_state.md").is_file())
            verified = subprocess.run(
                [sys.executable, "-B", str(copied / "scripts/verify_mrs.py"), "--json", str(state)],
                cwd=directory, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(0, verified.returncode, verified.stdout + verified.stderr)
            self.assertEqual("valid", json.loads(verified.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
