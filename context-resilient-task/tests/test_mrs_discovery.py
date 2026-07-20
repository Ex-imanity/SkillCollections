import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from _mrs_discovery import find_mrs_dirs


class FindMrsDirsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="crt-discovery-test-")).resolve()

    def tearDown(self):
        if self.root.exists():
            shutil.rmtree(self.root)

    def test_finds_default_mrs(self):
        (self.root / ".task-state").mkdir()
        result = find_mrs_dirs(self.root)
        self.assertEqual([p.name for p in result], [".task-state"])

    def test_finds_multiple_named_mrs(self):
        (self.root / ".task-state").mkdir()
        (self.root / ".task-state-auth").mkdir()
        (self.root / ".task-state-bugfix").mkdir()
        result = find_mrs_dirs(self.root)
        names = sorted(p.name for p in result)
        self.assertEqual(names, [".task-state", ".task-state-auth", ".task-state-bugfix"])

    def test_ignores_near_miss_task_state_names(self):
        (self.root / ".task-state").mkdir()
        (self.root / ".task-stateful").mkdir()
        (self.root / ".task-state.backup").mkdir()
        (self.root / ".task_state-auth").mkdir()
        result = find_mrs_dirs(self.root)
        self.assertEqual([p.name for p in result], [".task-state"])

    def test_walks_up_from_subdirectory(self):
        (self.root / ".task-state").mkdir()
        nested = self.root / "src" / "deep" / "nested"
        nested.mkdir(parents=True)
        result = find_mrs_dirs(nested)
        self.assertEqual([p.name for p in result], [".task-state"])

    def test_returns_empty_when_none_exist(self):
        result = find_mrs_dirs(self.root)
        self.assertEqual(result, [])

    def test_subdir_mrs_takes_precedence_over_parent(self):
        sub = self.root / "skill"
        sub.mkdir()
        (sub / ".task-state").mkdir()
        (self.root / ".task-state-other").mkdir()
        result = find_mrs_dirs(sub)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, ".task-state")
        self.assertEqual(result[0].parent, sub)


if __name__ == "__main__":
    unittest.main()
