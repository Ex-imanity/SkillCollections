import json
import shutil
import subprocess
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parent


class MrsScriptsTest(unittest.TestCase):
    def setUp(self):
        self.work_root = REPO_ROOT / ".test-mrs-scripts"
        if self.work_root.exists():
            shutil.rmtree(self.work_root)
        self.work_root.mkdir()

    def tearDown(self):
        if self.work_root.exists():
            shutil.rmtree(self.work_root)

    def run_script(self, script_name, *args, check=True):
        result = subprocess.run(
            ["python", str(SKILL_ROOT / "scripts" / script_name), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(
                f"{script_name} failed with {result.returncode}\n"
                f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def test_initialized_mrs_verifies_as_valid(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script(
            "init_mrs.py",
            "--dir",
            mrs_dir,
            "--goal",
            "Review CRT changes",
            "--complexity",
            "medium",
            "--requirements",
            "Compare main;Check scripts",
        )

        verify = self.run_script("verify_mrs.py", "--json", mrs_dir, check=False)
        payload = json.loads(verify.stdout)

        self.assertEqual(payload["status"], "valid", verify.stdout)
        self.assertTrue((mrs_dir / "findings.md").exists())
        self.assertTrue((mrs_dir / "progress.md").exists())

    def test_snapshot_uses_project_root_and_normalizes_empty_blockers(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        src_file = project_dir / "src" / "app.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("print('hello')\n", encoding="utf-8")

        self.run_script(
            "init_mrs.py",
            "--dir",
            mrs_dir,
            "--goal",
            "Build sample app",
            "--complexity",
            "medium",
            "--requirements",
            "Implement app",
        )
        self.run_script("generate_snapshot.py", mrs_dir)

        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        self.assertIn("- src/app.py", snapshot)
        self.assertIn("## Blockers\n- (None)", snapshot)
        self.assertNotIn("_(none)_", snapshot)

    def test_snapshot_infers_project_root_from_named_mrs(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state-feature-x"
        src_file = project_dir / "src" / "module.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("x = 1\n", encoding="utf-8")

        self.run_script(
            "init_mrs.py",
            "--dir",
            mrs_dir,
            "--goal",
            "Build feature X",
            "--complexity",
            "medium",
            "--requirements",
            "Implement module",
        )
        self.run_script("generate_snapshot.py", mrs_dir)

        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        self.assertIn("- src/module.py", snapshot)

    def test_list_mrs_finds_multiple_with_metadata(self):
        project_dir = self.work_root / "project"
        project_dir.mkdir()
        self.run_script(
            "init_mrs.py",
            "--dir",
            project_dir / ".task-state",
            "--goal",
            "Default task",
            "--complexity",
            "medium",
        )
        self.run_script(
            "init_mrs.py",
            "--dir",
            project_dir / ".task-state-bugfix",
            "--goal",
            "Urgent bug fix",
            "--complexity",
            "small",
        )

        result = self.run_script("list_mrs.py", "--json", project_dir)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["count"], 2)
        by_name = {m["name"]: m for m in payload["mrs"]}
        self.assertEqual(sorted(by_name), [".task-state", ".task-state-bugfix"])
        self.assertEqual(by_name[".task-state"]["goal"], "Default task")
        self.assertEqual(by_name[".task-state"]["status"], "active")
        self.assertEqual(by_name[".task-state-bugfix"]["goal"], "Urgent bug fix")
        self.assertEqual(by_name[".task-state-bugfix"]["status"], "active")
        for mrs in payload["mrs"]:
            self.assertIn("updated", mrs)
            self.assertIn("updated_human", mrs)
            self.assertIn("path", mrs)

    def test_list_mrs_reads_legacy_single_line_metadata(self):
        project_dir = self.work_root / "legacy-project"
        mrs_dir = project_dir / ".task-state"
        mrs_dir.mkdir(parents=True)
        (mrs_dir / "task_state.md").write_text(
            "# Task State\n\n**Goal:** Legacy task\n**Status:** active\n",
            encoding="utf-8",
        )

        result = self.run_script("list_mrs.py", "--json", project_dir)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["mrs"][0]["goal"], "Legacy task")
        self.assertEqual(payload["mrs"][0]["status"], "active")

    def test_init_mrs_suggests_sibling_on_conflict(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"

        self.run_script(
            "init_mrs.py",
            "--dir",
            mrs_dir,
            "--goal",
            "Original task",
            "--complexity",
            "small",
        )

        result = self.run_script(
            "init_mrs.py",
            "--dir",
            mrs_dir,
            "--goal",
            "New task",
            "--complexity",
            "small",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".task-state-", result.stderr)
        self.assertIn("--dir", result.stderr)


if __name__ == "__main__":
    unittest.main()
