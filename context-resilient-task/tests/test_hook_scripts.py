"""Tests for the auto-hook scripts (restore/precompact/gate/install)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
PY = sys.executable or "python3"

_EPOCH_PAST = 1_000_000  # far in the past; used to force snapshot < source


class HookScriptsTest(unittest.TestCase):
    def setUp(self):
        # Use a system temp dir (NOT under the repo): find_mrs_dirs walks up the
        # tree, so a work dir nested in this repo would discover the repo's own
        # stray .task-state-* dirs and break the "no MRS" isolation.
        self.work_root = Path(tempfile.mkdtemp(prefix="crt-hook-test-")).resolve()

    def tearDown(self):
        if self.work_root.exists():
            shutil.rmtree(self.work_root)

    # -- helpers -------------------------------------------------------------
    def run_script(self, name, *args, cwd=None, check=True):
        result = subprocess.run(
            [PY, str(SCRIPTS / name), *map(str, args)],
            text=True,
            capture_output=True,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"{name} rc={result.returncode}\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}")
        return result

    def init_mrs(self, mrs_dir, goal="Build sample", complexity="medium"):
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", goal, "--complexity", complexity)

    def make_git_project(self):
        project = self.work_root / "project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.email", "t@t.co"], check=True)
        subprocess.run(["git", "-C", str(project), "config", "user.name", "t"], check=True)
        return project

    def age_snapshot(self, mrs_dir):
        snap = mrs_dir / "snapshot.md"
        os.utime(snap, (_EPOCH_PAST, _EPOCH_PAST))

    # -- no-op contract ------------------------------------------------------
    def test_all_hooks_silent_without_mrs(self):
        empty = self.work_root / "empty"
        empty.mkdir()
        for name in ("restore_context.py", "precompact_digest.py", "gate_check.py"):
            result = self.run_script(name, "--hook", "test", cwd=empty)
            self.assertEqual(result.returncode, 0, name)
            self.assertEqual(result.stdout.strip(), "", f"{name} should be silent without an MRS")

    # -- restore_context -----------------------------------------------------
    def test_restore_single_mrs(self):
        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state", goal="Implement auth")
        result = self.run_script("restore_context.py", cwd=project)
        self.assertIn("Reconstructed Task State", result.stdout)
        self.assertIn("Implement auth", result.stdout)
        self.assertIn("Current Artifacts", result.stdout)

    def test_restore_single_mrs_json(self):
        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state", goal="JSON goal")
        result = self.run_script("restore_context.py", "--json", cwd=project)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["state"]["goal"], "JSON goal")

    def test_restore_multiple_mrs_asks_user(self):
        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state", goal="Default")
        self.init_mrs(project / ".task-state-bugfix", goal="Bug fix")
        result = self.run_script("restore_context.py", cwd=project)
        self.assertIn("DO NOT assume", result.stdout)
        self.assertIn(".task-state-bugfix", result.stdout)
        self.assertNotIn("Reconstructed Task State", result.stdout)  # must not pick one

    # -- precompact_digest ---------------------------------------------------
    def test_precompact_digest(self):
        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state", goal="Survive compaction")
        result = self.run_script("precompact_digest.py", cwd=project)
        self.assertIn("pre-compaction digest", result.stdout)
        self.assertIn("Survive compaction", result.stdout)

    # -- gate_check ----------------------------------------------------------
    def test_gate_reminds_on_uncommitted_source(self):
        project = self.make_git_project()
        self.init_mrs(project / ".task-state")
        self.age_snapshot(project / ".task-state")
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")
        result = self.run_script("gate_check.py", cwd=project)
        self.assertIn("before ending", result.stdout)
        self.assertIn("src/app.py", result.stdout)

    def test_gate_silent_on_clean_tree(self):
        project = self.make_git_project()
        self.init_mrs(project / ".task-state")
        subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "x"], check=True)
        result = self.run_script("gate_check.py", cwd=project)
        self.assertEqual(result.stdout.strip(), "")

    def test_gate_ignores_mrs_only_changes(self):
        project = self.make_git_project()
        self.init_mrs(project / ".task-state")
        subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "x"], check=True)
        # Only the MRS changes -> not real drift -> silent.
        (project / ".task-state" / "progress.md").write_text("- more\n", encoding="utf-8")
        result = self.run_script("gate_check.py", cwd=project)
        self.assertEqual(result.stdout.strip(), "")

    def test_gate_silent_when_completed(self):
        project = self.make_git_project()
        mrs = project / ".task-state"
        self.init_mrs(mrs)
        self.age_snapshot(mrs)
        content = (mrs / "task_state.md").read_text(encoding="utf-8")
        content = content.replace("## Status\nactive", "## Status\ncompleted")
        (mrs / "task_state.md").write_text(content, encoding="utf-8")
        (project / "app.py").write_text("x=1\n", encoding="utf-8")
        result = self.run_script("gate_check.py", cwd=project)
        self.assertEqual(result.stdout.strip(), "")

    # -- install_hooks -------------------------------------------------------
    def test_install_merges_and_is_idempotent(self):
        settings = self.work_root / "settings.json"
        settings.write_text(
            json.dumps({"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}),
            encoding="utf-8",
        )
        self.run_script("install_hooks.py", "--settings", settings)
        self.run_script("install_hooks.py", "--settings", settings)  # twice -> no dupes
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")
        self.assertEqual(sorted(data["hooks"]), ["PreCompact", "SessionStart", "Stop"])
        self.assertEqual(len(data["hooks"]["SessionStart"]), 1)
        self.assertEqual(len(data["hooks"]["Stop"]), 2)  # user's + ours

    def test_uninstall_removes_only_ours(self):
        settings = self.work_root / "settings.json"
        settings.write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}),
            encoding="utf-8",
        )
        self.run_script("install_hooks.py", "--settings", settings)
        self.run_script("install_hooks.py", "--settings", settings, "--uninstall")
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["hooks"], {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]})

    def test_install_refuses_invalid_json(self):
        settings = self.work_root / "settings.json"
        settings.write_text("not json{", encoding="utf-8")
        result = self.run_script("install_hooks.py", "--settings", settings, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(settings.read_text(encoding="utf-8"), "not json{")

    def test_uninstall_preserves_colocated_user_hook(self):
        # A user hook sharing the SAME group as ours must survive uninstall.
        settings = self.work_root / "settings.json"
        self.run_script("install_hooks.py", "--settings", settings)
        data = json.loads(settings.read_text(encoding="utf-8"))
        data["hooks"]["SessionStart"][0]["hooks"].insert(
            0, {"type": "command", "command": "echo user-colocated"}
        )
        settings.write_text(json.dumps(data), encoding="utf-8")
        self.run_script("install_hooks.py", "--settings", settings, "--uninstall")
        after = json.loads(settings.read_text(encoding="utf-8"))
        commands = [h["command"] for g in after["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertIn("echo user-colocated", commands)
        self.assertFalse(any("crt-auto-hook:" in c for c in commands))

    # -- git drift edge cases (Codex review) ---------------------------------
    def test_gate_reminds_on_rename(self):
        project = self.make_git_project()
        self.init_mrs(project / ".task-state")
        (project / "a.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "base"], check=True)
        self.age_snapshot(project / ".task-state")
        subprocess.run(["git", "-C", str(project), "mv", "a.py", "b.py"], check=True)
        result = self.run_script("gate_check.py", cwd=project)
        self.assertIn("b.py", result.stdout)

    def test_gate_reminds_on_deletion(self):
        project = self.make_git_project()
        self.init_mrs(project / ".task-state")
        (project / "gone.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "base"], check=True)
        self.age_snapshot(project / ".task-state")
        (project / "gone.py").unlink()  # deletion -> no mtime, must still count as drift
        result = self.run_script("gate_check.py", cwd=project)
        self.assertIn("before ending", result.stdout)

    def test_parse_porcelain_z_handles_rename_and_spaces(self):
        sys.path.insert(0, str(SCRIPTS))
        import _state_probe  # noqa: WPS433
        data = "R  new name.py\x00old name.py\x00 M other file.py\x00?? added.py\x00"
        self.assertEqual(
            _state_probe._parse_porcelain_z(data),
            ["new name.py", "other file.py", "added.py"],
        )

    # -- cross-platform command hardening (Windows support) ------------------
    def test_scripts_accept_tag_arg(self):
        # argparse must accept --tag; otherwise a hook command exits 2, which on
        # a Stop hook would BLOCK the session. Regression guard.
        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state", goal="tag arg")
        for name in ("restore_context.py", "precompact_digest.py", "gate_check.py"):
            result = self.run_script(name, "--hook", "test", "--tag", "crt-auto-hook:Test", cwd=project)
            self.assertEqual(result.returncode, 0, f"{name} rejected --tag: {result.stderr}")

    def test_build_command_is_portable(self):
        sys.path.insert(0, str(SCRIPTS))
        import install_hooks  # noqa: WPS433
        cmd = install_hooks.build_command("Stop", "gate_check.py")
        # No shell-specific operators (would break across sh/PowerShell/cmd).
        for bad in ("2>/dev/null", "2>NUL", "; exit 0", "#"):
            self.assertNotIn(bad, cmd, f"command should not contain {bad!r}: {cmd}")
        # Detection token travels as a --tag arg.
        self.assertIn("--tag crt-auto-hook:Stop", cmd)
        # Interpreter is a bare launcher, not a quoted first token (PowerShell trap).
        self.assertFalse(cmd.startswith('"'), cmd)
        self.assertTrue(cmd.split(" ", 1)[0] in ("python", "python3"), cmd)


if __name__ == "__main__":
    unittest.main()
