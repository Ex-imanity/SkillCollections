import json
import shutil
import subprocess
import unittest
import os
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
        self.assertTrue((mrs_dir / "utils.md").exists())

    def test_restore_includes_recent_context_and_utils(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script(
            "init_mrs.py",
            "--dir",
            mrs_dir,
            "--goal",
            "Recover context",
            "--complexity",
            "large",
        )
        (mrs_dir / "decisions.md").write_text(
            "# Decisions\n\n## 2026-01-01: Old\n- **Decision:** old\n\n"
            "## 2026-01-02: Current\n- **Decision:** keep the API boundary\n",
            encoding="utf-8",
        )
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: Discovery\n- **Finding:** parser drops trace IDs\n",
            encoding="utf-8",
        )
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Local tools\n- `pytest`: run tests\n- Path: `/Users/example/project`\n",
            encoding="utf-8",
        )

        result = self.run_script("restore_context.py", project_dir)
        self.assertIn("keep the API boundary", result.stdout)
        self.assertIn("parser drops trace IDs", result.stdout)
        self.assertIn("/Users/example/project", result.stdout)

    def test_precompact_and_snapshot_include_context_sections(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Digest context", "--complexity", "large")
        (mrs_dir / "decisions.md").write_text(
            "# Decisions\n\n## 2026-01-02: Decision\n- **Decision:** use fixture data\n",
            encoding="utf-8",
        )
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: Finding\n- **Finding:** production access is read-only\n",
            encoding="utf-8",
        )
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Runtime\n- `curl`: API probe\n",
            encoding="utf-8",
        )
        digest = self.run_script("precompact_digest.py", project_dir)
        self.assertIn("use fixture data", digest.stdout)
        self.assertIn("production access is read-only", digest.stdout)
        self.assertIn("curl", digest.stdout)

        self.run_script("generate_snapshot.py", mrs_dir)
        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        self.assertIn("## Stable Decisions", snapshot)
        self.assertIn("use fixture data", snapshot)
        self.assertIn("## Key Findings", snapshot)
        self.assertIn("production access is read-only", snapshot)
        self.assertIn("## Utilities", snapshot)
        self.assertIn("curl", snapshot)
        self.assertNotRegex(snapshot, r"^## (Latest|Runtime|2026-01-02)", msg=snapshot)

    def test_snapshot_omits_restricted_utilities(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Filter utilities", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Public\n- Sensitivity: public\n- Endpoint: https://example.test\n\n"
            "## Restricted\n- Sensitivity: restricted\n- Path: /secret/server\n",
            encoding="utf-8",
        )
        self.run_script("generate_snapshot.py", mrs_dir)
        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        self.assertIn("example.test", snapshot)
        self.assertNotIn("/secret/server", snapshot)

    def test_verify_warns_when_context_log_is_newer_than_snapshot(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Detect drift", "--complexity", "medium")
        future = (mrs_dir / "snapshot.md").stat().st_mtime + 5
        os.utime(mrs_dir / "findings.md", (future, future))
        result = self.run_script("verify_mrs.py", "--json", mrs_dir, check=False)
        payload = json.loads(result.stdout)
        self.assertTrue(any("snapshot.md is older" in warning for warning in payload["warnings"]))

    def test_verify_rejects_duplicate_authoritative_todo_sections(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Validate shape", "--complexity", "medium")
        task_state = mrs_dir / "task_state.md"
        content = task_state.read_text(encoding="utf-8")
        content += "\n## Completed Items\n- [x] Duplicate section\n"
        task_state.write_text(content, encoding="utf-8")
        result = self.run_script("verify_mrs.py", "--json", mrs_dir, check=False)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid")
        self.assertTrue(any("duplicate" in warning.lower() for warning in payload["warnings"]))

    def test_verify_rejects_suffixed_authoritative_todo_sections(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Validate variants", "--complexity", "medium")
        task_state = mrs_dir / "task_state.md"
        task_state.write_text(
            task_state.read_text(encoding="utf-8")
            + "\n## Completed Items（第一轮）\n- [x] Historical duplicate\n",
            encoding="utf-8",
        )
        result = self.run_script("verify_mrs.py", "--json", mrs_dir, check=False)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "valid")
        self.assertTrue(any("suffixed" in warning.lower() for warning in payload["warnings"]))

    def test_context_reader_uses_tail_and_preserves_pinned_entries(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        mrs_dir.mkdir(parents=True)
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-01: Old\nold detail\n\n"
            "## Invariants (pinned)\n- **Pinned:** yes\nNever remove this constraint\n\n"
            "## 2026-01-02: New\nnew detail\n" + ("tail-data " * 500),
            encoding="utf-8",
        )
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("state_probe", SKILL_ROOT / "scripts" / "_state_probe.py")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        entries = module.read_context_entries(mrs_dir, "findings.md", limit=1, max_chars=300)
        joined = "\n".join(entries)
        self.assertIn("Never remove this constraint", joined)
        self.assertIn("tail-data", joined)
        self.assertNotIn("old detail", joined)
        self.assertLessEqual(len(joined), 700)

    def test_utils_secrets_are_rejected(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Validate utilities", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Tooling\n- Endpoint: https://example.test\n- Authorization: Bearer super-secret\n",
            encoding="utf-8",
        )
        result = self.run_script("verify_mrs.py", "--json", mrs_dir, check=False)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid")
        self.assertTrue(any("secret" in warning.lower() for warning in payload["warnings"]))

    def test_mixed_restricted_utils_are_not_emitted(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Filter mixed utilities", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Tooling\n- Public tool; Sensitivity: public\n"
            "- Restricted endpoint; Sensitivity: restricted\n- Path: /private/endpoint\n",
            encoding="utf-8",
        )
        self.run_script("generate_snapshot.py", mrs_dir)
        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        self.assertNotIn("/private/endpoint", snapshot)
        restored = self.run_script("restore_context.py", project_dir)
        self.assertNotIn("/private/endpoint", restored.stdout)

    def test_bold_and_unknown_sensitivity_are_fail_closed(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Sensitivity forms", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Tooling\n- **Sensitivity:** restricted\n- Path: /private/bold\n",
            encoding="utf-8",
        )
        result = self.run_script("verify_mrs.py", "--json", mrs_dir, check=False)
        self.assertEqual(json.loads(result.stdout)["status"], "valid")
        self.run_script("generate_snapshot.py", mrs_dir)
        self.assertNotIn("/private/bold", (mrs_dir / "snapshot.md").read_text(encoding="utf-8"))

    def test_precompact_keeps_next_action_after_large_todos(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Keep action", "--complexity", "medium")
        task_state = mrs_dir / "task_state.md"
        content = task_state.read_text(encoding="utf-8").replace("Refine plan.md phases and add concrete todos", "x" * 6000)
        task_state.write_text(content, encoding="utf-8")
        digest = self.run_script("precompact_digest.py", project_dir).stdout
        self.assertIn("Next action", digest)

    def test_context_reader_preserves_original_lines_through_comments_and_fences(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        mrs_dir.mkdir(parents=True)
        (mrs_dir / "findings.md").write_text(
            "# Findings\n<!--\ncomment with ## Fake\n-->\n\n## Real\n"
            "```\n## Not a heading\n```\nreal finding\n",
            encoding="utf-8",
        )
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("state_probe_comments", SKILL_ROOT / "scripts" / "_state_probe.py")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        records = module.read_context_entry_records(mrs_dir, "findings.md")
        self.assertEqual(records[0]["line"], 6)
        self.assertIn("real finding", records[0]["text"])
        self.assertEqual(len(records), 1)

    def test_single_mrs_outputs_have_hard_budget(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Bound output", "--complexity", "large")
        (mrs_dir / "findings.md").write_text("# Findings\n\n## Huge\n" + ("x" * 20000), encoding="utf-8")
        digest = self.run_script("precompact_digest.py", project_dir)
        self.assertLessEqual(len(digest.stdout), 4000)
        self.run_script("generate_snapshot.py", mrs_dir)
        self.assertLessEqual(len((mrs_dir / "snapshot.md").read_text(encoding="utf-8")), 4000)

    def test_multiple_mrs_digest_has_global_budget_and_latest_context(self):
        project_dir = self.work_root / "multi"
        for index in range(5):
            mrs = project_dir / (".task-state" if index == 0 else f".task-state-{index}")
            self.run_script("init_mrs.py", "--dir", mrs, "--goal", f"Task {index}", "--complexity", "medium")
            (mrs / "findings.md").write_text(
                f"# Findings\n\n## Latest {index}\n" + ("detail-%d " % index * 800), encoding="utf-8"
            )
        digest = self.run_script("precompact_digest.py", project_dir)
        self.assertLessEqual(len(digest.stdout), 4500)
        self.assertIn("detail-4", digest.stdout)

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
