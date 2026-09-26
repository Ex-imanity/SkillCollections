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

    # -- superpowers 6.x execution ledgers -----------------------------------
    def write_ledger(self, project, slug, plan_id, task_lines, mtime=None, header=True):
        workspace = project / ".superpowers" / "sdd" / slug
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace.parent / ".gitignore").write_text("*\n", encoding="utf-8")
        (workspace / "plan-path").write_text(plan_id + "\n", encoding="utf-8")
        ledger = workspace / "progress.md"
        ledger.write_text((f"# SDD ledger — plan: {plan_id}\n" if header else "# SDD ledger\n") + "".join(f"{l}\n" for l in task_lines), encoding="utf-8")
        if mtime is not None:
            os.utime(ledger, (mtime, mtime))
        return ledger

    def register_plans(self, mrs_dir, rows):
        plan = mrs_dir / "plan.md"
        table = "".join(f"| {path} | writing-plans | 2026-09-27 | {status} |\n" for path, status in rows)
        plan.write_text(
            plan.read_text(encoding="utf-8").replace("|------|--------------|------|--------|\n",
                                                     "|------|--------------|------|--------|\n" + table, 1),
            encoding="utf-8",
        )

    def test_restore_and_precompact_follow_ledger_marker_not_slug(self):
        project = self.work_root / "project"
        project.mkdir()
        mrs = project / ".task-state"
        self.init_mrs(mrs)
        self.register_plans(mrs, [("docs/alpha/plan.md", "completed"), ("docs/beta/plan.md", "in_progress")])
        # Colliding basenames: upstream disambiguates the second slug; only the marker is authoritative.
        self.write_ledger(project, "plan", "docs/alpha/plan.md", ["Task 1: complete (alpha)"], mtime=_EPOCH_PAST, header=False)
        self.write_ledger(project, "plan-beta", "docs/beta/plan.md", ["Task 1: complete", "Task 2: complete (abc123)"], header=False)

        restored = self.run_script("restore_context.py", cwd=project).stdout
        self.assertIn("superpowers Execution Ledger", restored)
        self.assertIn("docs/beta/plan.md [in_progress]", restored)
        self.assertIn("plan-beta/progress.md", restored)
        self.assertIn("Task 2: complete (abc123)", restored)
        self.assertLess(restored.index("docs/beta/plan.md"), restored.index("docs/alpha/plan.md"))

        digest = self.run_script("precompact_digest.py", cwd=project).stdout
        self.assertIn("docs/beta/plan.md [in_progress]", digest)
        self.assertIn("Task 2: complete (abc123)", digest)

    def test_gate_reminds_when_ledger_advances_on_clean_tree(self):
        project = self.make_git_project()
        mrs = project / ".task-state"
        self.init_mrs(mrs)
        subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "x"], check=True)
        self.age_snapshot(mrs)
        self.write_ledger(project, "sync", "docs/superpowers/plans/sync.md", ["Task 2: complete"])
        status = subprocess.run(["git", "-C", str(project), "status", "--porcelain"], capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), "", "ledger workspace must stay out of git status")

        result = self.run_script("gate_check.py", cwd=project)
        self.assertIn("superpowers ledger", result.stdout)
        self.assertIn("docs/superpowers/plans/sync.md", result.stdout)

        # Once the snapshot is newer than the ledger, the reminder goes away.
        os.utime(mrs / "snapshot.md", None)
        ledger = project / ".superpowers" / "sdd" / "sync" / "progress.md"
        os.utime(ledger, (_EPOCH_PAST, _EPOCH_PAST))
        self.assertEqual(self.run_script("gate_check.py", cwd=project).stdout.strip(), "")

    # -- git worktrees share the MRS; drift and ledgers are per worktree -----
    def make_repo_with_worktree(self, worktree_path):
        project = self.make_git_project()
        (project / "README.md").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(project), "commit", "-qm", "init"], check=True)
        # Untracked MRS in the main checkout: linked worktrees do not get a copy.
        self.init_mrs(project / ".task-state", goal="Shared task")
        (project / ".git" / "info" / "exclude").write_text(".task-state/\n.worktrees/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "worktree", "add", "-q", "-b", "feat", str(worktree_path)], check=True)
        self.age_snapshot(project / ".task-state")
        return project

    def test_nested_worktree_shares_mrs_but_checks_its_own_tree_and_ledger(self):
        project_dir = self.work_root / "project"
        worktree = project_dir / ".worktrees" / "feat"
        project = self.make_repo_with_worktree(worktree)
        (project / "main_only.py").write_text("x\n", encoding="utf-8")
        self.write_ledger(project, "main-plan", "docs/superpowers/plans/main.md", ["Task 9: main"])
        self.write_ledger(worktree, "feat-plan", "docs/superpowers/plans/feat.md", ["Task 1: complete (feat)"])

        restored = self.run_script("restore_context.py", cwd=worktree).stdout
        self.assertIn("Shared task", restored)
        self.assertIn(f"current worktree: {worktree.resolve()}", restored)
        self.assertIn("Task 1: complete (feat)", restored)
        self.assertNotIn("Task 9: main", restored)
        self.assertNotIn("main_only.py", restored)

        (worktree / "feature.py").write_text("x\n", encoding="utf-8")
        gate = self.run_script("gate_check.py", cwd=worktree).stdout
        self.assertIn("feature.py", gate)
        self.assertNotIn("main_only.py", gate)

        # From the main checkout, the main tree's own drift and ledger apply.
        main_gate = self.run_script("gate_check.py", cwd=project).stdout
        self.assertIn("main_only.py", main_gate)
        self.assertNotIn("feature.py", main_gate)
        self.assertIn("Task 9: main", self.run_script("restore_context.py", cwd=project).stdout)

    def test_external_worktree_falls_back_to_main_checkout_mrs(self):
        worktree = self.work_root / "elsewhere" / "feat"
        self.make_repo_with_worktree(worktree)
        restored = self.run_script("restore_context.py", cwd=worktree).stdout
        self.assertIn("Shared task", restored)
        self.assertIn("current worktree", restored)
        (worktree / "feature.py").write_text("x\n", encoding="utf-8")
        self.assertIn("feature.py", self.run_script("gate_check.py", cwd=worktree).stdout)
        self.assertIn(".task-state", self.run_script("precompact_digest.py", cwd=worktree).stdout)

    def git(self, *args, cwd=None):
        subprocess.run(["git", *args], check=True, cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True)

    def commit_all(self, repo):
        self.git("-C", str(repo), "add", "-A")
        self.git("-C", str(repo), "-c", "user.email=t@t.co", "-c", "user.name=t", "commit", "-qm", "c")

    def test_subdirectory_project_finds_shared_mrs_and_toplevel_ledger(self):
        main = self.make_git_project()
        (main / "project").mkdir()
        (main / "project" / "app.py").write_text("x\n", encoding="utf-8")
        self.commit_all(main)
        mrs = main / "project" / ".task-state"
        self.init_mrs(mrs, goal="Monorepo task")
        (main / ".git" / "info" / "exclude").write_text(".task-state/\n", encoding="utf-8")
        self.register_plans(mrs, [("docs/superpowers/plans/p.md", "in_progress")])
        # Upstream keeps the workspace at the git toplevel, marker relative to it.
        self.write_ledger(main, "p", "project/docs/superpowers/plans/p.md", ["Task 3: complete (main)"])

        restored = self.run_script("restore_context.py", cwd=main / "project").stdout
        self.assertIn("Task 3: complete (main)", restored)
        self.assertIn("[in_progress]", restored)  # project-relative registry row still matches

        worktree = self.work_root / "wt"
        self.git("-C", str(main), "worktree", "add", "-q", "-b", "feat", str(worktree))
        self.age_snapshot(mrs)
        (worktree / "project" / "feature.py").write_text("x\n", encoding="utf-8")
        from_wt = self.run_script("restore_context.py", cwd=worktree / "project").stdout
        self.assertIn("Monorepo task", from_wt)
        self.assertIn(f"current worktree: {(worktree / 'project').resolve()}", from_wt)
        self.assertIn("feature.py", self.run_script("gate_check.py", cwd=worktree / "project").stdout)

    def test_fallback_uses_worktree_list_for_separate_git_dir_and_bare(self):
        # separate-git-dir: the common dir is not named .git
        main = self.work_root / "main"
        self.git("init", "-q", "--separate-git-dir", str(self.work_root / "meta"), str(main))
        (main / "a.txt").write_text("x\n", encoding="utf-8")
        self.commit_all(main)
        self.init_mrs(main / ".task-state", goal="Separate dir task")
        self.git("-C", str(main), "worktree", "add", "-q", "-b", "f1", str(self.work_root / "wt1"))
        # Git records no path for this checkout, so discovery stays silent (the
        # hook contract) and the explicit --mrs entry point restores it.
        self.assertEqual(self.run_script("restore_context.py", cwd=self.work_root / "wt1").stdout.strip(), "")
        explicit = self.run_script("restore_context.py", self.work_root / "wt1", "--mrs", main / ".task-state").stdout
        self.assertIn("Separate dir task", explicit)

        # submodule: git reports the module's git dir; core.worktree names the checkout
        mod = self.work_root / "mod"
        self.git("init", "-q", str(mod))
        (mod / "a.txt").write_text("x\n", encoding="utf-8")
        self.commit_all(mod)
        sup = self.work_root / "super"
        self.git("init", "-q", str(sup))
        self.git("-C", str(sup), "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(mod), "module")
        self.commit_all(sup)
        self.init_mrs(sup / "module" / ".task-state", goal="Submodule task")
        self.git("-C", str(sup / "module"), "worktree", "add", "-q", "-b", "f3", str(self.work_root / "subwt"))
        self.assertIn("Submodule task", self.run_script("restore_context.py", cwd=self.work_root / "subwt").stdout)

        # bare repository: no main checkout; the MRS lives in one linked worktree
        seed = self.work_root / "seed"
        self.git("init", "-q", str(seed))
        (seed / "a.txt").write_text("x\n", encoding="utf-8")
        self.commit_all(seed)
        bare = self.work_root / "bare.git"
        self.git("clone", "-q", "--bare", str(seed), str(bare))
        self.git("-C", str(bare), "worktree", "add", "-q", str(self.work_root / "b1"))
        self.git("-C", str(bare), "worktree", "add", "-q", "-b", "f2", str(self.work_root / "b2"))
        self.init_mrs(self.work_root / "b1" / ".task-state", goal="Bare task")
        self.assertIn("Bare task", self.run_script("restore_context.py", cwd=self.work_root / "b2").stdout)

    def test_multiple_mrs_index_ledgers_and_mrs_flag_restores_one(self):
        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state", goal="Task A")
        self.init_mrs(project / ".task-state-other", goal="Task B")
        self.write_ledger(project, "a", "docs/superpowers/plans/a.md", ["Task 5: complete (a)"])

        listing = self.run_script("restore_context.py", cwd=project).stdout
        self.assertIn("DO NOT assume which is current", listing)
        self.assertIn("In-flight superpowers ledgers", listing)
        self.assertIn("docs/superpowers/plans/a.md", listing)
        self.assertIn("--mrs <mrs_dir>", listing)

        chosen = self.run_script("restore_context.py", project, "--mrs", project / ".task-state-other").stdout
        self.assertIn("Task B", chosen)
        self.assertNotIn("DO NOT assume", chosen)
        self.assertIn("Task 5: complete (a)", chosen)

    def test_active_plan_ledger_wins_over_newer_siblings(self):
        project = self.work_root / "project"
        project.mkdir()
        mrs = project / ".task-state"
        self.init_mrs(mrs)
        self.register_plans(mrs, [("docs/superpowers/plans/active.md", "in_progress"),
                                  ("docs/superpowers/plans/o1.md", "pending"),
                                  ("docs/superpowers/plans/o2.md", "pending")])
        self.write_ledger(project, "active", "docs/superpowers/plans/active.md", ["Task 1: active"], mtime=_EPOCH_PAST)
        self.write_ledger(project, "o1", "docs/superpowers/plans/o1.md", ["Task 1: o1"])
        self.write_ledger(project, "o2", "docs/superpowers/plans/o2.md", ["Task 1: o2"])
        restored = self.run_script("restore_context.py", cwd=project).stdout
        self.assertIn("Task 1: active", restored)
        self.assertIn("1 more in-flight ledger", restored)
        digest = self.run_script("precompact_digest.py", cwd=project).stdout
        self.assertIn("Task 1: active", digest)
        self.assertIn("2 more in-flight ledger(s)", digest)

    def test_gate_reports_new_ledger_despite_old_dirty_file(self):
        project = self.make_git_project()
        mrs = project / ".task-state"
        self.init_mrs(mrs)
        self.commit_all(project)
        old = project / "old.py"
        old.write_text("x\n", encoding="utf-8")
        os.utime(old, (_EPOCH_PAST, _EPOCH_PAST))  # dirty but older than the snapshot
        self.write_ledger(project, "s", "docs/superpowers/plans/s.md", ["Task 2: complete"])
        os.utime(mrs / "snapshot.md", (_EPOCH_PAST + 10, _EPOCH_PAST + 10))
        gate = self.run_script("gate_check.py", cwd=project).stdout
        self.assertIn("superpowers ledger", gate)
        self.assertNotIn("old.py", gate)

    def test_precompact_restore_hint_keeps_current_worktree(self):
        worktree = self.work_root / "elsewhere" / "feat"
        project = self.make_repo_with_worktree(worktree)
        digest = self.run_script("precompact_digest.py", cwd=worktree).stdout
        self.assertIn(f"restore_context.py {worktree.resolve()} --mrs {(project / '.task-state').resolve()}", digest)

    def test_vanishing_workspace_is_skipped(self):
        sys.path.insert(0, str(SCRIPTS))
        import _state_probe  # noqa: E402

        project = self.work_root / "project"
        project.mkdir()
        self.init_mrs(project / ".task-state")
        gone = self.write_ledger(project, "gone", "docs/superpowers/plans/gone.md", ["x"])
        self.write_ledger(project, "kept", "docs/superpowers/plans/kept.md", ["y"])
        real_stat = Path.stat

        def flaky_stat(path, *args, **kwargs):
            if path == gone and not kwargs and not args and flaky_stat.armed:
                raise FileNotFoundError(path)
            return real_stat(path, *args, **kwargs)

        flaky_stat.armed = False
        original_is_file = Path.is_file
        Path.is_file = lambda path: True if path == gone else original_is_file(path)
        Path.stat = flaky_stat
        flaky_stat.armed = True
        try:
            ledgers = _state_probe.sdd_ledgers(project / ".task-state", project)
        finally:
            Path.stat, Path.is_file = real_stat, original_is_file
        self.assertEqual([item["plan"] for item in ledgers], ["docs/superpowers/plans/kept.md"])

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

    def test_install_codex_project_merges_and_is_idempotent(self):
        project = self.work_root / "codex-project"
        hooks_file = project / ".codex" / "hooks.json"
        hooks_file.parent.mkdir(parents=True)
        hooks_file.write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo user"}]}]}}),
            encoding="utf-8",
        )

        self.run_script("install_hooks.py", "--codex", cwd=project)
        self.run_script("install_hooks.py", "--codex", cwd=project)

        data = json.loads(hooks_file.read_text(encoding="utf-8"))
        self.assertEqual(sorted(data["hooks"]), ["PreCompact", "SessionStart", "Stop"])
        self.assertEqual(len(data["hooks"]["SessionStart"]), 1)
        self.assertEqual(len(data["hooks"]["Stop"]), 2)
        commands = [hook["command"] for group in data["hooks"]["SessionStart"] for hook in group["hooks"]]
        self.assertEqual(len([command for command in commands if "crt-auto-hook:SessionStart" in command]), 1)
        self.assertIn("restore_context.py", commands[0])

    def test_uninstall_codex_preserves_user_hooks(self):
        project = self.work_root / "codex-project"
        project.mkdir()
        self.run_script("install_hooks.py", "--codex", cwd=project)
        hooks_file = project / ".codex" / "hooks.json"
        data = json.loads(hooks_file.read_text(encoding="utf-8"))
        data["hooks"]["Stop"].insert(0, {"hooks": [{"type": "command", "command": "echo user"}]})
        hooks_file.write_text(json.dumps(data), encoding="utf-8")
        self.run_script("install_hooks.py", "--codex", "--uninstall", cwd=project)

        data = json.loads(hooks_file.read_text(encoding="utf-8"))
        self.assertEqual(data["hooks"], {"Stop": [{"hooks": [{"type": "command", "command": "echo user"}]}]})

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
