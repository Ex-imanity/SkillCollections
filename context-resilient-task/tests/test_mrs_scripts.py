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


if __name__ == "__main__":
    unittest.main()
