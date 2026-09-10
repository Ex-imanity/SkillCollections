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


    REGISTRY = (
        "# Utilities & Resource Registry\n\n## Resource Registry\n\n"
        "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
        "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
        "| R1 | feishu-doc | PRD | https://xx.feishu.cn/docx/abc | prod | login | internal | 2026-09-10 |\n"
        "| R2 | web-page | spec | https://spec.example | - | open | public | 2026-09-10 |\n"
        "| R3 | local-process | dev server | http://localhost:3000 | local | - | internal | 2026-09-10 |\n"
        "| R4 | database | prod db | mysql://prod-host/app | prod | ro_user | restricted | 2026-09-10 |\n"
        "| R5 | web-page | unlabeled | https://unlabeled.example | - | open | | |\n"
    )

    def test_registry_is_redacted_per_row_not_per_section(self):
        """One restricted resource must not hide its table siblings."""
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Row redaction", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(self.REGISTRY, encoding="utf-8")

        restored = self.run_script("restore_context.py", project_dir).stdout
        for kept in ("xx.feishu.cn/docx/abc", "spec.example", "localhost:3000"):
            self.assertIn(kept, restored)
        # restricted row, and the unlabeled sibling that inherits it, stay out
        self.assertNotIn("mysql://prod-host/app", restored)
        self.assertNotIn("unlabeled.example", restored)

        self.run_script("generate_snapshot.py", mrs_dir)
        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        self.assertIn("xx.feishu.cn/docx/abc", snapshot)
        self.assertNotIn("mysql://prod-host/app", snapshot)

    def test_utils_sections_survive_the_recency_window(self):
        """utils.md is an index, not a log: no section may be recency-trimmed."""
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Pinned registry", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities & Resource Registry\n\n"
            "## Resource Registry\n- R1 pointer https://first.example; Sensitivity: internal\n\n"
            "## Tooling\n- pytest; Sensitivity: public\n\n"
            "## Environments\n- staging base https://staging.example; Sensitivity: internal\n\n"
            "## Notes\n- R1 needs VPN\n",
            encoding="utf-8",
        )
        digest = self.run_script("precompact_digest.py", project_dir).stdout
        for kept in ("first.example", "pytest", "staging.example", "needs VPN"):
            self.assertIn(kept, digest, digest)

    def test_registry_truncation_keeps_header_and_earliest_rows(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        mrs_dir.mkdir(parents=True)
        rows = "".join(
            f"| R{n} | web-page | resource {n} | https://res-{n}.example/{'p' * 40} | - | open | internal | 2026-09-10 |\n"
            for n in range(1, 40)
        )
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n" + rows,
            encoding="utf-8",
        )
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("state_probe", SKILL_ROOT / "scripts" / "_state_probe.py")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        records = module.utils_records(mrs_dir, max_chars=600)
        self.assertEqual(len(records), 1)
        rendered = module.format_context_entry(records[0], 600)
        self.assertIn("| ID | Type |", rendered)      # header kept
        self.assertIn("res-1.example", rendered)      # earliest rows kept
        self.assertNotIn("res-39.example", rendered)  # tail dropped
        self.assertIn("utils.md:", rendered)          # pointer to full file
        self.assertLessEqual(len(rendered), 700)

    def test_verify_flags_registry_rows_and_legacy_layout(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Registry checks", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            self.REGISTRY + "| R6 | madeup | bad type | https://x.example | - | open | internal | 2026-09-10 |\n",
            encoding="utf-8",
        )
        warnings = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)["warnings"]
        self.assertTrue(any("unknown Type" in w and "R6" in w for w in warnings), warnings)
        self.assertTrue(any("without an explicit Sensitivity" in w and "R5" in w for w in warnings), warnings)

        (mrs_dir / "utils.md").write_text("# Utilities\n\n## Tooling\n- pytest\n", encoding="utf-8")
        legacy = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)
        self.assertEqual(legacy["status"], "valid")  # legacy layout warns, never invalidates
        self.assertTrue(any("no '## Resource Registry' table" in w for w in legacy["warnings"]), legacy["warnings"])

    def test_registry_accepts_other_prefixed_types(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Open enum", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
            "| R1 | other:banshan-case | 搬山用例集 | https://banshan.example/case/1 | prod | SSO | internal | 2026-09-10 |\n",
            encoding="utf-8",
        )
        warnings = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)["warnings"]
        self.assertFalse([w for w in warnings if "unknown Type" in w], warnings)


    def test_scan_resources_drafts_registry_and_ranks_reachable_first(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Scan legacy", "--complexity", "medium")
        (mrs_dir / "utils.md").unlink()  # legacy MRS: no registry at all
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: 外部资料坐标\n"
            "- PRD https://gaotuedu.feishu.cn/wiki/ABC123456789\n"
            "- 本地服务 http://127.0.0.1:28688 已启动\n"
            "- 证据 /Users/nobody/repo/src/main/java/com/example/AppUtils.java\n"
            "- 容器目录 /Users/nobody/Projects\n",
            encoding="utf-8",
        )
        out = self.run_script("scan_resources.py", mrs_dir).stdout
        self.assertIn("feishu.cn/wiki/ABC123456789", out)
        self.assertIn("local-process", out)
        # evidence source files and bare container dirs are not resources
        self.assertNotIn("AppUtils.java", out)
        self.assertNotIn("| /Users/nobody/Projects |", out)
        # the reachable doc outranks everything else
        self.assertLess(out.index("feishu.cn"), out.index("127.0.0.1"))
        self.assertIn("findings.md:", out)  # provenance
        self.assertFalse((mrs_dir / "utils.md").exists())  # read-only without --write

        self.run_script("scan_resources.py", mrs_dir, "--write")
        utils = (mrs_dir / "utils.md").read_text(encoding="utf-8")
        self.assertIn("## Resource Registry", utils)
        self.assertIn("feishu-doc", utils)
        self.assertNotIn("(none recorded)", utils.split("## Notes")[0])

        # a second pass must not duplicate rows already registered
        again = self.run_script("scan_resources.py", mrs_dir).stdout
        self.assertIn("No unregistered resource pointers", again)

    def test_scan_resources_reports_json_and_handles_empty_mrs(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Nothing to scan", "--complexity", "small")
        payload = json.loads(self.run_script("scan_resources.py", mrs_dir, "--json").stdout)
        self.assertEqual(payload["candidates"], [])

    def test_malformed_tier0_snapshot_is_repairable_not_absent(self):
        """A hand-written snapshot must never route an agent to re-initialization."""
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Legacy snapshot", "--complexity", "medium")
        (mrs_dir / "snapshot.md").write_text(
            "# Latest Snapshot\n\n**Timestamp:** 2026-01-02 15:05:00 CST\n**Status:** active\n\n"
            "## 本轮完成\n- 手写快照，章节是中文\n",
            encoding="utf-8",
        )
        payload = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)
        self.assertIn("snapshot.md", payload["tier0"]["present"])
        self.assertEqual(payload["tier0"]["invalid"], [])
        self.assertTrue(any("legacy header" in w for w in payload["warnings"]), payload["warnings"])
        self.assertTrue(any("do NOT re-initialize" in w for w in payload["warnings"]), payload["warnings"])

    def test_recovery_lists_tier2_and_custom_mrs_documents(self):
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "List everything", "--complexity", "medium")
        (mrs_dir / "evidence-index.md").write_text("# Evidence Index\n- E1\n", encoding="utf-8")
        (mrs_dir / "blockers.md").write_text("# Blockers\n- none\n", encoding="utf-8")
        (mrs_dir / "snapshot_20260101_1200.md").write_text("# Snapshot: 2026-01-01 12:00\n", encoding="utf-8")
        restored = self.run_script("restore_context.py", project_dir).stdout
        self.assertIn("evidence-index.md", restored)
        self.assertIn("blockers.md", restored)
        self.assertNotIn("snapshot_20260101_1200.md", restored)  # archives are history


    def test_verify_nudges_long_logs_without_pinned_invariants(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Pin nudge", "--complexity", "large")
        (mrs_dir / "decisions.md").write_text(
            "# Decisions\n\n## Entries\n\n" + "".join(
                f"## 2026-01-{n:02d}: Decision {n}\n- **Decision:** d{n}\n\n" for n in range(1, 15)
            ) + "## Invariants (pinned)\n- (none recorded)\n",
            encoding="utf-8",
        )
        warnings = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)["warnings"]
        self.assertTrue(any("no pinned invariants" in w and "14 entries" in w for w in warnings), warnings)

        content = (mrs_dir / "decisions.md").read_text(encoding="utf-8").replace(
            "## Invariants (pinned)\n- (none recorded)",
            "## Invariants (pinned)\n- **Pinned:** yes\n- Never call the prod sync API from tests",
        )
        (mrs_dir / "decisions.md").write_text(content, encoding="utf-8")
        warnings = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)["warnings"]
        self.assertFalse([w for w in warnings if "no pinned invariants" in w], warnings)


    # --- Grok review 2026-09-10 (gate crt-1.6.0-grok-20260910): P1 regressions ---

    def test_credential_shaped_pointer_is_never_emitted_even_unlabeled(self):
        """P1: a registry with no Sensitivity column must not leak a credential."""
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Unlabeled leak", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access |\n"
            "|----|------|----------------|---------|-----|--------|\n"
            "| R1 | database | 线上库 | mysql://svc:SuperSecretPass@db.internal:3306/app | prod | svc |\n"
            "| R2 | service-api | 回调 | https://x.test/cb?token=abc123def456 | prod | open |\n"
            "| R3 | feishu-doc | PRD | https://xx.feishu.cn/docx/keepme | prod | login |\n",
            encoding="utf-8",
        )
        restored = self.run_script("restore_context.py", project_dir).stdout
        digest = self.run_script("precompact_digest.py", project_dir).stdout
        self.run_script("generate_snapshot.py", mrs_dir)
        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        for emitted in (restored, digest, snapshot):
            self.assertNotIn("SuperSecretPass", emitted)
            self.assertNotIn("abc123def456", emitted)
            # R3 is unlabeled and sits beside credential-shaped rows, so
            # fail-closed inheritance drops it too.
            self.assertNotIn("docx/keepme", emitted)

        payload = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)
        self.assertEqual(payload["status"], "invalid")
        self.assertTrue(any("likely secret value" in w for w in payload["warnings"]), payload["warnings"])

        # With explicit levels, per-row redaction keeps the clean siblings.
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
            "| R1 | database | 线上库 | mysql://svc:SuperSecretPass@db.internal:3306/app | prod | svc | internal | 2026-09-10 |\n"
            "| R3 | feishu-doc | PRD | https://xx.feishu.cn/docx/keepme | prod | login | internal | 2026-09-10 |\n",
            encoding="utf-8",
        )
        restored = self.run_script("restore_context.py", project_dir).stdout
        self.assertNotIn("SuperSecretPass", restored)  # label cannot override the secret guard
        self.assertIn("docx/keepme", restored)

    def test_verify_warns_about_secrets_in_replayed_documents(self):
        """P1: findings/progress are replayed or committed, so flag credentials there too."""
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Doc secrets", "--complexity", "medium")
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: env\n- db mysql://svc:Passw0rdXYZ@db.internal:3306/app\n",
            encoding="utf-8",
        )
        warnings = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)["warnings"]
        self.assertTrue(any("findings.md" in w and "likely secret" in w for w in warnings), warnings)

    def test_redaction_placeholders_are_not_reported_as_secrets(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Placeholders", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
            "| R1 | database | 线上库 | mysql://svc:***@db.internal:3306/app | prod | svc_user | internal | 2026-09-10 |\n",
            encoding="utf-8",
        )
        payload = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)
        self.assertFalse([w for w in payload["warnings"] if "likely secret value" in w], payload["warnings"])
        self.assertIn("db.internal", self.run_script("restore_context.py", mrs_dir.parent).stdout)

    def test_secret_detector_ignores_prose_and_keeps_real_values(self):
        """A false positive silently drops a legitimate registry row, so the
        detector must not fire on prose like "Bearer credentials"."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("state_probe", SKILL_ROOT / "scripts" / "_state_probe.py")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        for text, expected in (
            # Grok postfix gate crt-1.6.0-postfix-grok-20260910:
            # empty-userinfo URLs, vendor keys, JWTs, and probe/verify parity.
            ("redis://:sOmEpAsSwOrD99@redis:6379/0", True),
            ("mysql://u:P@ss1@h/db", True),
            ("password: Passw0rd", True),
            ("password: P@ssw0rd", True),
            ("xoxb-1234567890-abcdef", True),
            ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcd", True),
            ("Authorization: Bearer super-secret", True),
            ("parent_node_token=node_token", False),
            ("?token=<docx_token>", False),
            ("Access: 飞书登录", False),
            ("bearer token 说明见文档", False),
            ("https://user@host/x", False),
            # postfix sweep over the 16 real MRS: these were false positives
            ("task-breakdown 见 docs", False),          # `sk-` inside "task-"
            (".task-state-ai-qa-tech-selection", False),
            ("token 轮换/清理继续按用户要求独立", False),   # CJK prose
            ("token rotation: 见方案", False),
            ("sk-proj-abcdefghijklmnop123456", True),
            # postfix2 gate: compound keys, Basic auth, PEM
            ("client_secret=abc123def456", True),
            ("aws_secret_access_key=AbCd1234EfGh5678", True),
            ("refresh_token=8f3c6d12b5f0", True),
            ("mytoken=abc123def456", True),
            ("Authorization: Basic dXNlcjpwYXNzd29yZA==", True),
            ("-----BEGIN RSA PRIVATE KEY-----", True),
            # postfix2 gate: prose shapes found in the real MRS corpus
            ("token-gated sync/delete 已确认", False),
            ("token-based Framelink/figma fetch", False),
            ("token: ~/.claude/settings.json", False),
            ("token authenticates the request", False),
            ("tenant-token record-list request", False),
            # value capture must stop at the first backtick, not run into CJK
            ("token `8f3c6d12b5e74a9ca1d8f0b36e2c7a4d`、`allowedSystem`", True),
            ("token=8f3c6d12b5f0", True),
            ("Authorization: Bearer sk-abc12345678", True),
            # Deliberate known limit: an all-letter value cannot be told apart
            # from prose ("token authenticates the request"), and a false
            # positive silently drops a legitimate registry row. Documented in
            # references/artifact-standards.md.
            ("password: SuperSecretPass", False),
            ("api_key = a1b2c3d4e5", True),
            ("mysql://u:P@ss1@h/db", True),
            ("Bearer credentials", False),
            ("token: token", False),
            ("bearer credential handling", False),
            ("token=***", False),
            ("mysql://u:***@h/db", False),
            ("mysql://prod-host:3306/app", False),
        ):
            self.assertEqual(module.has_sensitive_value(text), expected, text)

        # a row whose Access column is prose must still be emitted
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Prose access", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
            "| R1 | service-api | 订单查询 | https://api.test/orders | prod | bearer credentials | internal | 2026-09-10 |\n",
            encoding="utf-8",
        )
        self.assertIn("api.test/orders", self.run_script("restore_context.py", project_dir).stdout)

    def test_probe_and_verifier_agree_on_every_secret_shape(self):
        """Drift between the emission guard and the validator either hides a
        leak or silently drops a row the validator calls healthy."""
        from importlib.util import spec_from_file_location, module_from_spec
        probe_spec = spec_from_file_location("state_probe", SKILL_ROOT / "scripts" / "_state_probe.py")
        probe = module_from_spec(probe_spec); probe_spec.loader.exec_module(probe)
        verify_spec = spec_from_file_location("verify_mrs", SKILL_ROOT / "scripts" / "verify_mrs.py")
        verify = module_from_spec(verify_spec); verify_spec.loader.exec_module(verify)
        # no second copy of the detector may exist in the validator
        self.assertFalse(hasattr(verify, "SECRET_PATTERNS"), "verify_mrs.py reintroduced its own patterns")
        self.assertEqual(verify.has_sensitive_value.__module__, "_state_probe")
        for text in ("redis://:sOmEpAsSwOrD99@redis:6379/0", "mytoken=abc123def456",
                     "parent_node_token=node_token", "Bearer credentials",
                     "password: Passw0rd", "?token=<docx_token>",
                     "Authorization: Bearer super-secret", "mysql://prod-host:3306/app",
                     "xoxb-1234567890-abcdef", "token=***"):
            self.assertEqual(probe.has_sensitive_value(text), verify.has_sensitive_value(text), text)

    def test_empty_userinfo_credentials_are_redacted_withheld_and_rejected(self):
        """P1 (postfix gate): `scheme://:password@host` must be handled like `user:pass@`."""
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Empty userinfo", "--complexity", "medium")

        # 1. emission: withheld even when the row claims `internal`
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
            "| R1 | database | redis | redis://:sOmEpAsSwOrD99@redis:6379/0 | prod | redis | internal | 2026-09-10 |\n"
            "| R2 | feishu-doc | PRD | https://xx.feishu.cn/docx/keepme | prod | login | internal | 2026-09-10 |\n",
            encoding="utf-8",
        )
        restored = self.run_script("restore_context.py", project_dir).stdout
        digest = self.run_script("precompact_digest.py", project_dir).stdout
        self.run_script("generate_snapshot.py", mrs_dir)
        snapshot = (mrs_dir / "snapshot.md").read_text(encoding="utf-8")
        for emitted in (restored, digest, snapshot):
            self.assertNotIn("sOmEpAsSwOrD99", emitted)
            self.assertIn("docx/keepme", emitted)

        # 2. verification: the file is rejected, not merely filtered
        payload = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)
        self.assertEqual(payload["status"], "invalid")
        self.assertTrue(any("likely secret value" in w for w in payload["warnings"]), payload["warnings"])

        # 3. scanner: never writes the raw password to disk
        (mrs_dir / "utils.md").unlink()
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: env\n- cache redis://:sOmEpAsSwOrD99@redis:6379/0\n",
            encoding="utf-8",
        )
        self.run_script("scan_resources.py", mrs_dir, "--write")
        utils = (mrs_dir / "utils.md").read_text(encoding="utf-8")
        self.assertNotIn("sOmEpAsSwOrD99", utils)
        self.assertIn("redis://:***@redis:6379/0", utils)

    def test_scan_drafts_are_restricted_and_credentials_redacted(self):
        """P1: machine drafts must not publish unclassified resources or write secrets."""
        project_dir = self.work_root / "project"
        mrs_dir = project_dir / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Draft policy", "--complexity", "medium")
        (mrs_dir / "utils.md").unlink()
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: env\n"
            "- db mysql://svc:Passw0rdXYZ@db.internal:3306/app\n"
            "- PRD https://xx.feishu.cn/wiki/ABC123456\n",
            encoding="utf-8",
        )
        self.run_script("scan_resources.py", mrs_dir, "--write")
        utils = (mrs_dir / "utils.md").read_text(encoding="utf-8")
        self.assertNotIn("Passw0rdXYZ", utils)          # secret never written
        self.assertIn("mysql://svc:***@db.internal", utils)  # resource still registered
        rows = [line for line in utils.splitlines() if line.startswith("| R")]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("| restricted |" in row for row in rows), rows)  # nothing unreviewed published
        # drafts stay out of every digest until a human classifies them
        # (the raw pointer still shows up via findings.md replay — that is the
        # source file the scanner tells the user to clean, covered separately)
        restored = self.run_script("restore_context.py", project_dir).stdout
        self.assertNotIn("mysql://svc:***@", restored)
        self.assertNotIn("| R1 |", restored)
        self.assertNotIn("| R2 |", restored)

    def test_ipv6_pointers_survive_the_scanner(self):
        """P2 (postfix2 gate): a bracketed IPv6 host must not be truncated."""
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "IPv6", "--complexity", "medium")
        (mrs_dir / "utils.md").unlink()
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: env\n- db postgres://alice:s3cretPw9@[::1]:5432/db\n",
            encoding="utf-8",
        )
        self.run_script("scan_resources.py", mrs_dir, "--write")
        utils = (mrs_dir / "utils.md").read_text(encoding="utf-8")
        self.assertIn("postgres://alice:***@[::1]:5432/db", utils)
        self.assertNotIn("s3cretPw9", utils)

    def test_scan_write_places_notes_after_the_template_comment(self):
        """P1: provenance must not be swallowed by the template's HTML comment."""
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "Notes placement", "--complexity", "medium")
        (mrs_dir / "findings.md").write_text(
            "# Findings\n\n## 2026-01-02: env\n- PRD https://xx.feishu.cn/wiki/ABC123456\n", encoding="utf-8",
        )
        self.run_script("scan_resources.py", mrs_dir, "--write")
        notes = (mrs_dir / "utils.md").read_text(encoding="utf-8").split("## Notes", 1)[1]
        comment_end = notes.index("-->")
        provenance = notes.index("草稿来源")
        self.assertLess(comment_end, provenance)          # outside the comment
        self.assertNotIn("(none recorded)", notes)        # placeholder replaced

    def test_chinese_sensitivity_label_is_not_reported_unlabeled(self):
        mrs_dir = self.work_root / "project" / ".task-state"
        self.run_script("init_mrs.py", "--dir", mrs_dir, "--goal", "CN label", "--complexity", "medium")
        (mrs_dir / "utils.md").write_text(
            "# Utilities\n\n## Resource Registry\n"
            "| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |\n"
            "|----|------|----------------|---------|-----|--------|-------------|----------|\n"
            "| R1 | database | 线上库 | mysql://prod-host:3306/app | prod | ro_user | 受限 | 2026-09-10 |\n",
            encoding="utf-8",
        )
        warnings = json.loads(self.run_script("verify_mrs.py", "--json", mrs_dir, check=False).stdout)["warnings"]
        self.assertFalse([w for w in warnings if "without an explicit Sensitivity" in w], warnings)
        self.assertNotIn("prod-host", self.run_script("restore_context.py", mrs_dir.parent).stdout)


if __name__ == "__main__":
    unittest.main()
