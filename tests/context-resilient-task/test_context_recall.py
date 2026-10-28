"""Replay the observed long-session recall failures with bounded synthetic MRS."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "context-resilient-task" / "scripts"


class ContextRecallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".test-mrs-", dir=REPO_ROOT)
        self.project = Path(self.temp.name)
        self.mrs = self.project / ".task-state"
        self.run_script("init_mrs.py", "--dir", self.mrs, "--goal", "Recover test",
                        "--complexity", "large")

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, name, *args):
        env = {k: v for k, v in os.environ.items()
               if k not in ("GROK_WORKSPACE_ROOT", "CLAUDE_PROJECT_DIR")}
        return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                              cwd=self.project, env=env, capture_output=True, text=True)

    def write_problem(self, extra="", scope="repo=sample; env=local", status="resolved"):
        text = (
            "# Problems\n\n## P001: Python src imports\n"
            f"- Status: {status}\n"
            "- Signature: ModuleNotFoundError: No module named 'ai_search_probe'\n"
            f"- Scope: {scope}\n"
            "- Cause: confirmed: src is absent from the import path\n"
            "- Tried: rerunning unchanged failed\n"
            "- Resolution: PYTHONPATH=src python scripts/check.py\n"
            "- Verification: import succeeded, 2026-10-19\n"
            "- Source: progress.md:12\n"
            "- Last verified: 2026-10-19\n"
            "- Recheck when: interpreter or project layout changes\n"
        )
        (self.mrs / "problems.md").write_text(text + extra, encoding="utf-8")

    def test_init_creates_problem_template_and_legacy_absence_stays_valid(self):
        self.assertTrue((self.mrs / "problems.md").exists())
        (self.mrs / "problems.md").unlink()
        checked = json.loads(self.run_script("verify_mrs.py", "--json", self.mrs).stdout)
        self.assertEqual(checked["status"], "valid")
        self.assertFalse(any("problems.md" in w for w in checked["warnings"]))

    def test_new_snapshot_headings_do_not_trigger_legacy_structure_warnings(self):
        for regenerate in (False, True):
            if regenerate:
                self.run_script("generate_snapshot.py", self.mrs)
            data = json.loads(self.run_script("verify_mrs.py", "--json", self.mrs).stdout)
            self.assertFalse([w for w in data["warnings"] if "Snapshot contains" in w or "unexpected top-level" in w])

    def test_long_pinned_context_does_not_starve_other_sources(self):
        self.write_problem()
        (self.mrs / "decisions.md").write_text(
            "# Decisions\n\n## Invariants (pinned)\nPinned boundary\n" + "long decision " * 3000 +
            "".join(f"\n## Pinned section {i}\n- Pinned: yes\n" + "long decision " * 1000
                    for i in range(5)))
        (self.mrs / "findings.md").write_text("# Findings\n\n## Finding\nFINDING_SURVIVES\n")
        (self.mrs / "utils.md").write_text("# Utilities\n\n## Local tools\n- curl: RESOURCE_SURVIVES\n")
        for script in ("restore_context.py", "precompact_digest.py"):
            with self.subTest(script=script):
                result = self.run_script(script, self.project)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLessEqual(len(result.stdout), 4000)
                for value in ("Pinned boundary", "FINDING_SURVIVES", "RESOURCE_SURVIVES",
                              "problems.md", "recall_context.py", "Active", "Next",
                              "### Status\nactive", "Phase 1: Planning"):
                    self.assertIn(value, result.stdout)
        self.run_script("generate_snapshot.py", self.mrs)
        snapshot = (self.mrs / "snapshot.md").read_text()
        self.assertLessEqual(len(snapshot), 4000)
        for value in ("## Key Findings", "## Utilities", "problems.md", "recall_context.py"):
            self.assertIn(value, snapshot)

    def test_old_resolved_problem_is_retrieved_after_many_new_entries(self):
        self.write_problem("\n" + "\n".join(
            f"## Note {i}\nUnrelated newer history\n" for i in range(40)))
        result = self.run_script("recall_context.py", self.mrs, "--query",
                                 "ModuleNotFoundError ai_search_probe", "--scope", "repo=sample",
                                 "--scope", "env=local", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        match = data["matches"][0]
        self.assertEqual(match["id"], "P001")
        self.assertEqual(match["status"], "resolved")
        self.assertEqual(match["applicability"], "scope_matched")
        self.assertEqual(match["file"], "problems.md")
        self.assertIn("PYTHONPATH=src", match["excerpt"])
        self.assertGreater(match["line"], 0)

    def test_full_history_search_includes_old_findings_and_progress(self):
        for filename in ("findings.md", "progress.md"):
            (self.mrs / filename).write_text(
                "# History\n\n## Old workaround\nread-only variable: status; use task_exit\n" +
                "".join(f"\n## New {i}\nUnrelated\n" for i in range(30)))
        result = self.run_script("recall_context.py", self.mrs, "--query",
                                 "read-only variable status", "--json")
        matches = json.loads(result.stdout)["matches"]
        self.assertEqual({m["file"] for m in matches}, {"findings.md", "progress.md"})
        self.assertTrue(all("task_exit" in m["excerpt"] for m in matches))

    def test_scope_conflict_excludes_same_error_with_wrong_environment(self):
        self.write_problem(scope="repo=sample; env=prod")
        result = self.run_script("recall_context.py", self.mrs, "--query",
                                 "ModuleNotFoundError ai_search_probe", "--scope", "env=local", "--json")
        self.assertEqual(json.loads(result.stdout)["matches"], [])

    def test_unknown_scope_and_stale_fix_require_recheck(self):
        self.write_problem(status="stale")
        result = self.run_script("recall_context.py", self.mrs, "--query", "ai_search_probe", "--json")
        match = json.loads(result.stdout)["matches"][0]
        self.assertEqual(match["status"], "stale")
        self.assertEqual(match["applicability"], "recheck_required")

    def test_restricted_and_credential_records_never_replayed(self):
        self.write_problem("- Sensitivity: restricted\n")
        (self.mrs / "findings.md").write_text(
            "# Findings\n\n## unsafe\nai_search_probe Bearer abc123SECRET987\n"
            "\n## safe\nai_search_probe use a scoped runtime\n")
        for args in ((), ("--json",)):
            result = self.run_script("recall_context.py", self.mrs, "--query", "ai_search_probe", *args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("abc123SECRET987", result.stdout)
            self.assertNotIn("PYTHONPATH=src", result.stdout)
            self.assertIn("scoped runtime", result.stdout)

    def test_file_restriction_after_commented_example_heading_is_respected(self):
        (self.mrs / "findings.md").write_text(
            "# Findings\n<!--\n## Example\nCommented instructions\n-->\n"
            "- Sensitivity: restricted\n\n## Actual private finding\n"
            "ai_search_probe PRIVATE_MARKER\n")
        result = self.run_script("recall_context.py", self.mrs, "--query", "ai_search_probe", "--json")
        self.assertEqual(json.loads(result.stdout)["matches"], [])
        restored = self.run_script("restore_context.py", self.project)
        self.assertNotIn("PRIVATE_MARKER", restored.stdout)

    def test_multiple_mrs_uses_the_same_context_visibility_rules(self):
        self.run_script("init_mrs.py", "--dir", self.project / ".task-state-other",
                        "--goal", "Other task", "--complexity", "medium")
        path = self.mrs / "findings.md"
        path.write_text("# Findings\n\n## Private\n- Sensitivity: restricted\nPRIVATE_MARKER\n")
        future = path.stat().st_mtime + 5
        os.utime(path, (future, future))
        result = self.run_script("restore_context.py", self.project)
        self.assertIn("DO NOT assume", result.stdout)
        self.assertNotIn("PRIVATE_MARKER", result.stdout)

    def test_large_mrs_directory_keeps_selection_and_restore_entry_points(self):
        state = (self.mrs / "task_state.md").read_text()
        for i in range(50):
            other = self.project / f".task-state-long-project-task-{i}"
            other.mkdir()
            (other / "task_state.md").write_text(state.replace("Recover test", "Long recovery goal " * 5))
        result = self.run_script("restore_context.py", self.project)
        self.assertLessEqual(len(result.stdout), 4000)
        for entry in ("ASK the user", "After choosing", "--mrs <mrs_dir>", "list_mrs.py", "recall_context.py"):
            self.assertIn(entry, result.stdout)

    def test_problem_summary_prioritizes_open_items_without_losing_resolved_lookup(self):
        self.write_problem()
        path = self.mrs / "problems.md"
        first = path.read_text()
        path.write_text(first + "".join(first[first.index('## P001:'):].replace('P001', f'P00{i}')
                                      .replace('Status: resolved', 'Status: open' if i == 5 else 'Status: resolved')
                                      for i in range(2, 6)))
        restored = self.run_script("restore_context.py", self.project)
        self.assertIn("P005 [open]", restored.stdout)
        recalled = json.loads(self.run_script("recall_context.py", self.mrs, "--query", "P001", "--json").stdout)
        self.assertEqual(recalled["matches"][0]["id"], "P001")

    def test_validate_duplicate_ids_and_resolved_without_evidence(self):
        self.write_problem()
        path = self.mrs / "problems.md"
        path.write_text(path.read_text() + "\n## P001: duplicate\n- Status: resolved\n")
        result = self.run_script("verify_mrs.py", "--json", self.mrs)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "invalid")
        self.assertTrue(any("duplicate" in w.lower() and "P001" in w for w in data["warnings"]))
        self.assertTrue(any("Verification" in w for w in data["warnings"]))

    def test_cli_returns_valid_bounded_json_and_no_match_is_normal(self):
        for filename in ("findings.md", "decisions.md", "progress.md"):
            (self.mrs / filename).write_text("# History\n" + "".join(
                f"\n## Finding {i}\nai_search_probe " + "long data " * 1500 for i in range(8)))
        result = self.run_script("recall_context.py", self.mrs, "--query", "ai_search_probe",
                                 "--limit", "5", "--json")
        self.assertLessEqual(len(result.stdout), 4000)
        self.assertTrue(json.loads(result.stdout)["matches"])
        result = self.run_script("recall_context.py", self.mrs, "--query", "unseen_unique_issue", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["matches"], [])
        self.assertFalse(payload["truncated"])
        self.assertEqual(payload["omitted_matches"], 0)

    def test_fenced_examples_cannot_supply_or_override_live_problem_fields(self):
        self.write_problem(scope="repo=sample; env=prod", status="open")
        path = self.mrs / "problems.md"
        live = path.read_text().split("## P001:", 1)[1]
        live = "## P001:" + live
        example = live.replace("Status: open", "Status: resolved").replace("env=prod", "env=local")
        for fence, nested in (("```", ""), ("~~~", ""), ("````", "```"), ("```", "~~~")):
            content = f"{nested}\n{example}{nested}\n" if nested else example
            path.write_text("# Problems\n\n## P001: ai_search_probe\n" + fence + "\n" +
                            content + fence + "\n" + "\n".join(live.splitlines()[1:]))
            local = json.loads(self.run_script("recall_context.py", self.mrs, "--query", "ai_search_probe",
                                               "--scope", "env=local", "--json").stdout)
            self.assertEqual(local["matches"], [])
            prod = json.loads(self.run_script("recall_context.py", self.mrs, "--query", "ai_search_probe",
                                              "--scope", "env=prod", "--json").stdout)
            self.assertEqual(prod["matches"][0]["status"], "open")
            self.assertEqual(prod["matches"][0]["applicability"], "recheck_required")

    def test_fields_only_in_a_fence_are_reported_missing(self):
        self.write_problem()
        path = self.mrs / "problems.md"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:3]) + "\n```\n" + "\n".join(lines[3:]) + "\n```\n")
        data = json.loads(self.run_script("verify_mrs.py", "--json", self.mrs).stdout)
        self.assertEqual(data["status"], "invalid")
        self.assertTrue(any("missing Status" in warning for warning in data["warnings"]))

    def test_unstructured_problem_remains_searchable_with_format_warning(self):
        (self.mrs / "problems.md").write_text("# Problems\n\n## Import failure\n"
                                             "legacy_unique_import: use PYTHONPATH=src\n")
        recalled = json.loads(self.run_script("recall_context.py", self.mrs, "--query",
                                              "legacy_unique_import", "--json").stdout)
        self.assertEqual(recalled["matches"][0]["file"], "problems.md")
        self.assertEqual(recalled["matches"][0]["applicability"], "recheck_required")
        checked = json.loads(self.run_script("verify_mrs.py", "--json", self.mrs).stdout)
        self.assertEqual(checked["status"], "valid")
        self.assertTrue(any("problem ID" in w for w in checked["warnings"]))

    def test_large_metadata_keeps_a_match_and_explicit_truncation(self):
        for character in ("S", "\x01"):
            (self.mrs / "findings.md").write_text("# Findings\n\n## Old note\n- Status: " + character * 5000 +
                                                 "\n- Scope: tool=" + character * 5000 + "\nunique_metadata task_exit\n")
            for flags in ((), ("--json",)):
                result = self.run_script("recall_context.py", self.mrs, "--query", "unique_metadata", *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLessEqual(len(result.stdout), 4000)
                self.assertIn("findings.md", result.stdout)
                if flags:
                    payload = json.loads(result.stdout)
                    self.assertTrue(payload["matches"])
                    self.assertTrue(payload["truncated"])
                    self.assertEqual(payload["matches"][0]["applicability"], "recheck_required")

    def test_budget_omissions_are_distinct_from_no_matches(self):
        scope = "; ".join(f"key{i}=" + "V" * 120 for i in range(6))
        (self.mrs / "findings.md").write_text("# Findings\n" + "".join(
            f"\n## Old note {i}\n- Status: " + "S" * 80 + f"\n- Scope: {scope}\n"
            "budget_unique " + "long data " * 300 for i in range(5)))
        result = self.run_script("recall_context.py", self.mrs, "--query", "budget_unique",
                                 "--limit", "5", "--json")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["matches"])
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["omitted_matches"], 5 - len(payload["matches"]))
        self.assertLessEqual(len(result.stdout), 4000)

    def test_long_heading_cannot_consume_the_global_budget(self):
        sys.path.insert(0, str(SCRIPTS))
        from _context_recall import balanced_sections
        rendered = balanced_sections([("### " + "S" * 5000, "details", "findings.md:3"),
                                      ("### Context Recall", "python recall_context.py selected_mrs --query error", "")])
        self.assertLessEqual(len(rendered), 3999)
        self.assertIn("python recall_context.py", rendered)


if __name__ == "__main__":
    unittest.main()
