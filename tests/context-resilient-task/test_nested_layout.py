"""Nested slots must preserve discovery, project scans and explicit task choice."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/context-resilient-task/scripts"
sys.path.insert(0, str(SCRIPTS))
from _mrs_discovery import find_mrs_dirs, mrs_project_root, work_root_for
from _state_probe import project_root_for
from generate_snapshot import infer_project_root


class NestedLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def mrs(self, relative):
        path = self.root / relative
        path.mkdir(parents=True, exist_ok=True)
        (path / "task_state.md").write_text("# Task State\n\n## Goal\nSample goal\n\n## Status\nactive\n\n## Active Todos\n- Check paths\n")
        return path

    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                              cwd=self.root, capture_output=True, text=True)

    def test_lists_leaf_slots_without_mistaking_container_or_archive_for_task(self):
        a = self.mrs(".task-state/main")
        b = self.mrs(".task-state/auth")
        self.mrs(".task-state/archive/old")
        (self.root / ".task-state/cross-agent-review").mkdir()
        self.assertEqual(set(find_mrs_dirs(self.root)), {a, b})

    def test_runtime_only_container_is_not_a_broken_mrs(self):
        (self.root / ".task-state/cross-agent-review").mkdir(parents=True)
        self.assertEqual(find_mrs_dirs(self.root), [])

    def test_mixed_legacy_and_nested_layouts_are_all_visible(self):
        paths = [self.mrs(p) for p in (".task-state", ".task-state-old", ".task-state/new")]
        self.assertEqual(set(find_mrs_dirs(self.root)), set(paths))

    def test_partial_mrs_is_not_hidden_or_reinitialized(self):
        path = self.root / ".task-state/repair"
        path.mkdir(parents=True)
        (path / "plan.md").write_text("Historical plan\n")
        self.assertEqual(find_mrs_dirs(self.root), [path])

    def test_all_root_helpers_use_owner_project_for_nested_slot(self):
        path = self.mrs(".task-state/main")
        for helper in (mrs_project_root, project_root_for, infer_project_root, work_root_for):
            with self.subTest(helper=helper.__name__):
                self.assertEqual(helper(path), self.root)

    def test_nested_slot_reached_from_its_evidence_directory_stays_selected(self):
        chosen = self.mrs(".task-state/auth")
        self.mrs(".task-state/main")
        evidence = chosen / "evidence"
        evidence.mkdir()
        self.assertEqual(find_mrs_dirs(evidence), [chosen])

    def test_discovery_from_source_subdirectory_keeps_nearest_project_scope(self):
        self.mrs(".task-state/main")
        child = self.root / "module"
        nested = child / ".task-state/feature"
        nested.mkdir(parents=True)
        (nested / "snapshot.md").write_text("Checkpoint\n")
        (child / "src").mkdir()
        self.assertEqual(find_mrs_dirs(child / "src"), [nested])

    def test_realpath_alias_is_not_listed_as_a_second_task(self):
        path = self.mrs(".task-state/auth")
        (self.root / ".task-state-auth").symlink_to(path, target_is_directory=True)
        self.assertEqual(find_mrs_dirs(self.root), [path])

    def test_default_initialization_creates_main_leaf(self):
        result = self.run_script("init_mrs.py", "--goal", "Default", "--complexity", "small")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / ".task-state/main/task_state.md").is_file())
        self.assertFalse((self.root / ".task-state/task_state.md").exists())

    def test_named_initialization_and_reserved_slot_validation(self):
        result = self.run_script("init_mrs.py", "--slot", "auth", "--goal", "Auth", "--complexity", "small")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / ".task-state/auth/task_state.md").is_file())
        for name in ("archive", "../escape", "nested/task"):
            result = self.run_script("init_mrs.py", "--slot", name, "--goal", "Bad", "--complexity", "small")
            self.assertNotEqual(result.returncode, 0)

    def test_default_init_does_not_create_a_second_main_below_legacy_default(self):
        self.mrs(".task-state")
        result = self.run_script("init_mrs.py", "--goal", "Different", "--complexity", "small")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".task-state/main").exists())

    def test_force_init_cannot_write_task_files_into_an_existing_slot_container(self):
        self.mrs(".task-state/main")
        result = self.run_script("init_mrs.py", "--dir", ".task-state", "--force",
                                 "--goal", "Accidental container overwrite", "--complexity", "small")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".task-state/task_state.md").exists())

    def test_list_and_restore_json_refer_to_actual_leaf(self):
        path = self.mrs(".task-state/auth")
        listed = self.run_script("list_mrs.py", "--json")
        payload = json.loads(listed.stdout)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["mrs"][0]["path"], str(path))
        restored = self.run_script("restore_context.py", "--mrs", path, "--json")
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(json.loads(restored.stdout)["state"]["goal"], "Sample goal")


    def test_linked_worktree_finds_nested_owner_but_keeps_its_work_root(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
        mrs = self.mrs(".task-state/main")
        with tempfile.TemporaryDirectory() as temp:
            worktree = Path(temp).resolve() / "worktree"
            subprocess.run(["git", "-C", str(self.root), "worktree", "add", "--detach", "-q", str(worktree)], check=True)
            self.assertEqual(find_mrs_dirs(worktree), [mrs])
            self.assertEqual(work_root_for(mrs, worktree), worktree)


if __name__ == "__main__":
    unittest.main()
