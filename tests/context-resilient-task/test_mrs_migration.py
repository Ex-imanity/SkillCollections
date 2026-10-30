"""Migration must preserve data, historical pointers and reversible ownership."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/context-resilient-task/scripts"


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def mrs(self, name):
        path = self.root / name
        path.mkdir(parents=True)
        (path / "task_state.md").write_text("# Task State\n\n## Goal\nMigration fixture\n\n## Status\npaused\n\n## Active Todos\n- Verify path\n")
        (path / "plan.md").write_text("# Task Plan\n\n## Plan Registry\n")
        (path / "snapshot.md").write_text("# Snapshot\n\n## Current State\nPaused\n")
        (path / "evidence.txt").write_text("Evidence bytes\n")
        (path / "utils.md").write_text(f"# Resources\n`{name}/evidence.txt`\n")
        (path / "progress.md").write_text(f"# Progress\nHistorical `{path}/evidence.txt:3`\n")
        return path

    def run_migration(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "migrate_mrs.py"), str(self.root),
                               *map(str, args), "--json"], cwd=self.root, capture_output=True, text=True)

    def apply(self, *args):
        r = self.run_migration("--apply", *args)
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
        return json.loads(r.stdout)

    def test_preview_never_creates_container_or_changes_source(self):
        source = self.mrs(".task-state-auth")
        before = {p.relative_to(source): p.read_bytes() for p in source.iterdir()}
        r = self.run_migration()
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout)
        self.assertEqual(plan["moves"][0]["destination"], ".task-state/auth")
        self.assertFalse((self.root / ".task-state").exists())
        self.assertEqual(before, {p.relative_to(source): p.read_bytes() for p in source.iterdir()})

    def test_apply_preserves_history_but_updates_current_registry_and_entrypoint(self):
        source = self.mrs(".task-state-auth")
        history = (source / "progress.md").read_bytes()
        (self.root / "AGENTS.md").write_text("Recover .task-state-auth/task_state.md\n")
        result = self.apply()
        target = self.root / ".task-state/auth"
        self.assertFalse(source.exists())
        self.assertEqual((target / "progress.md").read_bytes(), history)
        self.assertEqual((target / "evidence.txt").read_text(), "Evidence bytes\n")
        self.assertIn(".task-state/auth/evidence.txt", (target / "utils.md").read_text())
        self.assertIn(".task-state/auth/task_state.md", (self.root / "AGENTS.md").read_text())
        self.assertEqual(result["state"], "completed")

    def test_legacy_default_moves_contents_to_main_but_keeps_archive_and_new_slots(self):
        source = self.mrs(".task-state")
        self.mrs(".task-state/feature")
        archive = source / "archive/old"
        archive.mkdir(parents=True)
        (archive / "progress.md").write_text("Archived\n")
        self.apply()
        self.assertTrue((source / "main/task_state.md").exists())
        self.assertFalse((source / "task_state.md").exists())
        self.assertTrue((source / "feature/task_state.md").exists())
        self.assertEqual((archive / "progress.md").read_text(), "Archived\n")

    def test_runtime_only_container_does_not_manufacture_main(self):
        runtime = self.root / ".task-state/cross-agent-review"
        runtime.mkdir(parents=True)
        (runtime / "cost.jsonl").write_text("{}\n")
        result = self.apply()
        self.assertEqual(result["state"], "no_op")
        self.assertFalse((self.root / ".task-state/main").exists())

    def test_conflicting_destination_refuses_before_moving_any_task(self):
        self.mrs(".task-state-a")
        self.mrs(".task-state-b")
        self.mrs(".task-state/b")
        r = self.run_migration("--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((self.root / ".task-state-a").exists())
        self.assertTrue((self.root / ".task-state-b").exists())
        self.assertFalse((self.root / ".task-state/a").exists())

    def test_legacy_default_and_flat_main_are_a_planned_collision_not_a_merge(self):
        default = self.mrs(".task-state")
        named = self.mrs(".task-state-main")
        (default / "evidence.txt").write_text("default data\n")
        (named / "evidence.txt").write_text("named data\n")
        r = self.run_migration("--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((default / "task_state.md").exists())
        self.assertTrue((named / "task_state.md").exists())
        self.assertEqual((default / "evidence.txt").read_text(), "default data\n")
        self.assertEqual((named / "evidence.txt").read_text(), "named data\n")
        self.assertFalse((default / "main").exists())

    def test_second_apply_is_a_no_op(self):
        self.mrs(".task-state-auth")
        self.apply()
        self.assertEqual(self.apply()["state"], "no_op")

    def test_interrupted_migration_must_be_recovered_before_starting_another(self):
        source = self.mrs(".task-state-auth")
        manifest = self.root / ".task-state/.migrations/old/manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"version":1,"state":"in_progress","moves":[]}\n')
        r = self.run_migration("--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(source.exists())
        self.assertFalse((self.root / ".task-state/auth").exists())

    def test_old_absolute_relative_and_line_locators_resolve_without_physical_aliases(self):
        source = self.mrs(".task-state-auth")
        self.apply()
        for old in (str(source / "evidence.txt"), ".task-state-auth/evidence.txt:3"):
            r = self.run_migration("--resolve", old)
            self.assertEqual(r.returncode, 0, r.stderr)
            answer = json.loads(r.stdout)
            self.assertTrue(answer["exists"])
            self.assertIn(".task-state/auth/evidence.txt", answer["resolved"])
        self.assertFalse(source.exists())

    def test_old_explicit_crt_commands_resolve_the_migrated_directory(self):
        source = self.mrs(".task-state-auth")
        self.apply()
        r = subprocess.run([sys.executable, str(SCRIPTS / "restore_context.py"), str(self.root),
                            "--mrs", str(source), "--json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["state"]["goal"], "Migration fixture")

    def test_default_alias_does_not_swallow_other_new_slots_or_archive(self):
        self.mrs(".task-state")
        other = self.mrs(".task-state/other")
        self.apply()
        for value in (".task-state", ".task-state/task_state.md", ".task-state/other/task_state.md"):
            r = self.run_migration("--resolve", value)
            self.assertEqual(r.returncode, 0, r.stderr)
            answer = json.loads(r.stdout)
            self.assertTrue(answer["exists"])
            if value.endswith("other/task_state.md"):
                self.assertEqual(answer["resolved"], str(other / "task_state.md"))
            else:
                self.assertIn(".task-state/main", answer["resolved"])

    def test_bare_default_path_in_a_historical_document_is_repo_relative(self):
        self.mrs(".task-state")
        self.apply()
        r = self.run_migration("--resolve", ".task-state", "--from-file", ".task-state/main/progress.md")
        answer = json.loads(r.stdout)
        self.assertTrue(answer["exists"])
        self.assertEqual(answer["resolved"], str(self.root / ".task-state/main"))

    def test_dot_prefixed_state_reference_keeps_project_relative_meaning(self):
        self.mrs(".task-state-auth")
        self.apply()
        r = self.run_migration("--resolve", "./.task-state-auth/evidence.txt", "--from-file", ".task-state/auth/progress.md")
        answer = json.loads(r.stdout)
        self.assertTrue(answer["exists"])
        self.assertEqual(answer["resolved"], str(self.root / ".task-state/auth/evidence.txt"))

    def test_relative_markdown_current_links_are_rebased_and_history_has_an_explicit_resolver(self):
        source = self.mrs(".task-state-auth")
        (self.root / "docs").mkdir()
        (self.root / "docs/design.md").write_text("Design\n")
        (source / "utils.md").write_text("[Design](../docs/design.md)\n")
        history = "[Old design](../docs/design.md)\n"
        (source / "progress.md").write_text(history)
        self.apply()
        target = self.root / ".task-state/auth"
        self.assertIn("../../docs/design.md", (target / "utils.md").read_text())
        self.assertEqual((target / "progress.md").read_text(), history)
        r = self.run_migration("--resolve", "../docs/design.md", "--from-file", target / "progress.md")
        self.assertTrue(json.loads(r.stdout)["exists"])
        self.assertEqual(json.loads(r.stdout)["resolved"], str(self.root / "docs/design.md"))

    def test_rollback_restores_original_files_and_entrypoints(self):
        source = self.mrs(".task-state-auth")
        (self.root / "AGENTS.md").write_text("Recover .task-state-auth\n")
        before = {p.name: p.read_bytes() for p in source.iterdir()}
        tx = self.apply()
        r = self.run_migration("--rollback", tx["id"])
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
        self.assertEqual(json.loads(r.stdout)["state"], "rolled_back")
        self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Recover .task-state-auth\n")

    def test_rollback_refuses_to_overwrite_post_migration_work(self):
        self.mrs(".task-state-auth")
        tx = self.apply()
        target = self.root / ".task-state/auth"
        (target / "progress.md").write_text("New task progress\n")
        r = self.run_migration("--rollback", tx["id"])
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((target / "progress.md").read_text(), "New task progress\n")

    def test_unfinished_review_gate_blocks_relocation_without_resetting_it(self):
        source = self.mrs(".task-state-auth")
        sessions = source / "review/rounds.json.sessions"
        sessions.mkdir(parents=True)
        record = sessions / "gate.json"
        record.write_text('{"state":"timed_out"}\n')
        r = self.run_migration("--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(record.read_text(), '{"state":"timed_out"}\n')

    def test_unknown_default_child_is_not_assumed_to_belong_to_main(self):
        source = self.mrs(".task-state")
        (source / "shared-runtime").mkdir()
        r = self.run_migration("--apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((source / "task_state.md").exists())
        self.apply("--include-default-dir", "shared-runtime")
        self.assertTrue((source / "main/shared-runtime").is_dir())


    def test_sensitive_reference_is_not_echoed_in_preview_or_audit(self):
        source = self.mrs(".task-state-auth")
        (source / "progress.md").write_text("`.task-state-auth/evidence.txt?token=fixturePrivate123456!`\n")
        r = self.run_migration()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("fixturePrivate123456!", r.stdout)
        self.assertIn("withheld_sensitive", r.stdout)

    def test_relative_history_resolution_uses_given_project_not_process_cwd(self):
        source = self.mrs(".task-state-auth")
        (self.root / "docs").mkdir()
        (self.root / "docs/design.md").write_text("Design\n")
        (source / "progress.md").write_text("[Design](../docs/design.md)\n")
        self.apply()
        r = subprocess.run([sys.executable, str(SCRIPTS / "migrate_mrs.py"), str(self.root),
                            "--resolve", "../docs/design.md", "--from-file", ".task-state/auth/progress.md", "--json"],
                           cwd=SCRIPTS, capture_output=True, text=True)
        self.assertTrue(json.loads(r.stdout)["exists"])

    def test_reference_rewrite_does_not_touch_another_repo_or_remote_url(self):
        source = self.mrs(".task-state-auth")
        value = "/other/project/.task-state-auth/evidence.txt\nhttps://example.invalid/repo/.task-state-auth/evidence.txt\n"
        (source / "utils.md").write_text(value)
        self.apply()
        self.assertEqual((self.root / ".task-state/auth/utils.md").read_text(), value)

    def test_failed_reference_write_rolls_back_prior_moves_and_edits(self):
        sys.path.insert(0, str(SCRIPTS))
        import migrate_mrs
        source = self.mrs(".task-state-auth")
        old = {p.name: p.read_bytes() for p in source.iterdir()}
        (self.root / "AGENTS.md").write_text("Recover .task-state-auth\n")
        original_atomic = migrate_mrs.atomic
        failed = False
        def fail_entry_once(path, data, *args, **kwargs):
            nonlocal failed
            if path.name == "AGENTS.md" and not failed:
                failed = True
                raise OSError("fixture disk failure")
            return original_atomic(path, data, *args, **kwargs)
        with mock.patch.object(migrate_mrs, "atomic", side_effect=fail_entry_once):
            with self.assertRaises(OSError):
                migrate_mrs.apply(self.root, [], [])
        self.assertEqual(old, {p.name: p.read_bytes() for p in source.iterdir()})
        self.assertFalse((self.root / ".task-state/auth").exists())
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Recover .task-state-auth\n")

    def test_symlink_project_spelling_is_rewritten_and_resolved(self):
        source = self.mrs(".task-state-auth")
        with tempfile.TemporaryDirectory() as alias_dir:
            alias = Path(alias_dir) / "project"
            try:
                alias.symlink_to(self.root, target_is_directory=True)
            except OSError as exc:
                self.skipTest(str(exc))
            old = str(alias / source.name / "evidence.txt")
            (self.root / "AGENTS.md").write_text(f"Recover `{old}`\n")
            before = json.loads(self.run_migration("--resolve", old).stdout)
            self.assertTrue(before["exists"])
            self.assertFalse(before["via_migration"])
            self.apply()
            after = json.loads(self.run_migration("--resolve", old).stdout)
            self.assertTrue(after["exists"])
            self.assertTrue(after["via_migration"])
            self.assertEqual(after["path"], str(self.root / ".task-state/auth/evidence.txt"))
            self.assertIn(after["path"], (self.root / "AGENTS.md").read_text())

    def test_rollback_rename_failure_can_retry_after_rewriting_slot_pointers(self):
        sys.path.insert(0, str(SCRIPTS))
        import migrate_mrs
        source = self.mrs(".task-state-auth")
        original = {p.name: p.read_bytes() for p in source.iterdir()}
        tx = self.apply()
        manifest = self.root / ".task-state/.migrations" / tx["id"] / "manifest.json"
        target = self.root / ".task-state/auth"
        rename = Path.rename
        def fail_target(path, destination):
            if path == target:
                raise OSError("fixture rollback rename failure")
            return rename(path, destination)
        with mock.patch.object(Path, "rename", fail_target):
            with self.assertRaises(OSError):
                migrate_mrs.rollback(self.root, manifest)
        self.assertEqual(json.loads(manifest.read_text())["state"], "rolling_back")
        self.assertEqual((target / "utils.md").read_bytes(), original["utils.md"])
        self.assertEqual(migrate_mrs.rollback(self.root, manifest)["state"], "rolled_back")
        self.assertEqual(original, {p.name: p.read_bytes() for p in source.iterdir()})

    def test_partly_moved_rollback_retries_but_preserves_new_work(self):
        sys.path.insert(0, str(SCRIPTS))
        import migrate_mrs
        for modified in (False, True):
            with self.subTest(modified=modified), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                for slot in ("a", "b"):
                    task = root / (".task-state-" + slot)
                    task.mkdir()
                    (task / "task_state.md").write_text("fixture\n")
                tx = migrate_mrs.apply(root, [], [])
                manifest = root / ".task-state/.migrations" / tx["id"] / "manifest.json"
                rename = Path.rename
                def fail_a(path, destination):
                    if path == root / ".task-state/a":
                        raise OSError("fixture partial rollback")
                    return rename(path, destination)
                with mock.patch.object(Path, "rename", fail_a):
                    with self.assertRaises(OSError):
                        migrate_mrs.rollback(root, manifest)
                self.assertTrue((root / ".task-state-b").exists())
                if modified:
                    file = root / ".task-state-b/task_state.md"
                    file.write_text("new user work\n")
                    with self.assertRaises(ValueError):
                        migrate_mrs.rollback(root, manifest)
                    self.assertEqual(file.read_text(), "new user work\n")
                else:
                    self.assertEqual(migrate_mrs.rollback(root, manifest)["state"], "rolled_back")
                    self.assertTrue((root / ".task-state-a/task_state.md").exists())

    def test_rollback_final_journal_failure_can_retry_after_paths_restored(self):
        sys.path.insert(0, str(SCRIPTS))
        import migrate_mrs
        source = self.mrs(".task-state-auth")
        tx = self.apply()
        manifest = self.root / ".task-state/.migrations" / tx["id"] / "manifest.json"
        save = migrate_mrs.save
        def fail_final(path, value):
            if value["state"] == "rolled_back":
                raise OSError("fixture final journal failure")
            return save(path, value)
        with mock.patch.object(migrate_mrs, "save", fail_final):
            with self.assertRaises(OSError):
                migrate_mrs.rollback(self.root, manifest)
        self.assertTrue(source.exists())
        self.assertEqual(json.loads(manifest.read_text())["state"], "rolling_back")
        self.assertEqual(migrate_mrs.rollback(self.root, manifest)["state"], "rolled_back")

    def test_sensitive_query_path_is_rewritten_without_leaking_query_in_audit(self):
        source = self.mrs(".task-state-auth")
        secret = "fixturePrivate123456!"
        suffix = ":3?token=" + secret + "#section"
        (source / "utils.md").write_text("`.task-state-auth/evidence.txt" + suffix + "`\n")
        tx = self.apply()
        self.assertNotIn(secret, json.dumps(tx))
        self.assertIn("withheld_sensitive", json.dumps(tx))
        self.assertIn(".task-state/auth/evidence.txt" + suffix,
                      (self.root / ".task-state/auth/utils.md").read_text())
        resolved = json.loads(self.run_migration("--resolve", ".task-state-auth/evidence.txt" + suffix).stdout)
        self.assertTrue(resolved["exists"])
        self.assertTrue(resolved["resolved"].endswith(suffix))

    def test_non_utf8_current_pointer_blocks_before_any_move(self):
        source = self.mrs(".task-state-auth")
        raw = b"`.task-state-auth/evidence.txt`\n\xff"
        (source / "utils.md").write_bytes(raw)
        preview = json.loads(self.run_migration().stdout)
        self.assertTrue(preview["blocked"])
        applied = self.run_migration("--apply")
        self.assertNotEqual(applied.returncode, 0)
        self.assertEqual((source / "utils.md").read_bytes(), raw)
        self.assertFalse((self.root / ".task-state/auth").exists())

    def test_non_utf8_history_is_preserved_and_text_mode_reports_skip(self):
        source = self.mrs(".task-state-auth")
        raw = b"historical bytes\xff"
        (source / "progress.md").write_bytes(raw)
        result = subprocess.run([sys.executable, str(SCRIPTS / "migrate_mrs.py"),
                                 str(self.root), "--apply"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SKIPPED", result.stdout)
        self.assertIn("progress.md", result.stdout)
        self.assertEqual((self.root / ".task-state/auth/progress.md").read_bytes(), raw)

    def test_complete_spaced_state_paths_in_code_and_markdown_are_rewritten(self):
        source = self.mrs(".task-state-auth")
        (source / "my file.txt").write_text("spaced evidence\n")
        (source / "utils.md").write_text(
            "`.task-state-auth/my file.txt`\n[Evidence](<.task-state-auth/my file.txt>)\n")
        tx = self.apply()
        text = (self.root / ".task-state/auth/utils.md").read_text()
        self.assertIn("`.task-state/auth/my file.txt`", text)
        self.assertIn("[Evidence](<.task-state/auth/my file.txt>)", text)
        self.assertFalse(any(r["status"] == "preexisting_missing" for r in tx["references"]))

    def test_refused_apply_removes_only_its_new_empty_container(self):
        source = self.mrs(".task-state-auth")
        sessions = source / "review/rounds.json.sessions"
        sessions.mkdir(parents=True)
        (sessions / "gate.json").write_text('{"state":"running"}\n')
        self.assertNotEqual(self.run_migration("--apply").returncode, 0)
        self.assertFalse((self.root / ".task-state").exists())
        (self.root / ".task-state").mkdir()
        self.assertNotEqual(self.run_migration("--apply").returncode, 0)
        self.assertTrue((self.root / ".task-state").exists())

    def test_reference_to_unselected_symlink_task_keeps_its_local_spelling(self):
        source = self.mrs(".task-state-auth")
        with tempfile.TemporaryDirectory() as elsewhere:
            external = Path(elsewhere)
            (external / "task_state.md").write_text("external task\n")
            alias = self.root / ".task-state-other"
            try:
                alias.symlink_to(external, target_is_directory=True)
            except OSError as exc:
                self.skipTest(str(exc))
            value = "`.task-state-other/task_state.md`\n"
            (source / "utils.md").write_text(value)
            self.apply("--slot", "auth")
            self.assertEqual((self.root / ".task-state/auth/utils.md").read_text(), value)
            self.assertEqual((external / "task_state.md").read_text(), "external task\n")

    def test_rollback_metadata_failure_is_repaired_on_retry(self):
        sys.path.insert(0, str(SCRIPTS))
        import migrate_mrs
        source = self.mrs(".task-state-auth")
        stamp = 1_600_000_000_123456789
        (source / "utils.md").chmod(0o640)
        utime = migrate_mrs.os.utime
        utime(source / "utils.md", ns=(stamp, stamp))
        tx = self.apply()
        manifest = self.root / ".task-state/.migrations" / tx["id"] / "manifest.json"
        target = self.root / ".task-state/auth/utils.md"
        def fail_metadata(path, *args, **kwargs):
            if Path(path) == target:
                raise OSError("fixture metadata failure")
            return utime(path, *args, **kwargs)
        with mock.patch.object(migrate_mrs.os, "utime", fail_metadata):
            with self.assertRaises(OSError):
                migrate_mrs.rollback(self.root, manifest)
        migrate_mrs.rollback(self.root, manifest)
        self.assertEqual((source / "utils.md").stat().st_mtime_ns, stamp)
        self.assertEqual((source / "utils.md").stat().st_mode & 0o777, 0o640)


    def test_encoded_parent_reference_keeps_document_relative_meaning(self):
        source = self.mrs(".task-state-auth")
        external_to_slot = self.root / "secret.txt"
        external_to_slot.write_text("do-not-touch\n")
        spellings = [".task-state-auth/%2e%2e/secret.txt", ".task-state-auth%2f..%2fsecret.txt"]
        (source / "utils.md").write_text("\n".join(f"`{p}`" for p in spellings) + "\n")
        self.apply()
        document = self.root / ".task-state/auth/utils.md"
        for line in document.read_text().splitlines():
            answer = json.loads(self.run_migration("--resolve", line.strip("`"), "--from-file", document).stdout)
            self.assertTrue(answer["exists"])
            self.assertEqual(answer["path"], str(external_to_slot))
        self.assertEqual(external_to_slot.read_text(), "do-not-touch\n")

    def test_encoded_filename_links_and_resolved_locators_round_trip(self):
        source = self.mrs(".task-state-auth")
        names = [("my file.txt", "my%20file.txt"), ("my#file.txt", "my%23file.txt"),
                 ("my?file.txt", "my%3Ffile.txt"), ("my%file.txt", "my%25file.txt"),
                 ("my(file).txt", "my%28file%29.txt"), ("report:3", "report%3A3")]
        suffix = ":7?view=all#section"
        for name, _ in names:
            (source / name).write_text("encoded evidence\n")
        (source / "utils.md").write_text("\n".join(
            f"[Evidence](.task-state-auth/{encoded}{suffix})" for _, encoded in names) + "\n")
        self.apply()
        text = (self.root / ".task-state/auth/utils.md").read_text()
        for name, encoded in names:
            with self.subTest(name=name):
                self.assertIn(f"[Evidence](.task-state/auth/{encoded}{suffix})", text)
                answer = json.loads(self.run_migration("--resolve", ".task-state-auth/" + encoded + suffix).stdout)
                self.assertTrue(answer["exists"])
                self.assertEqual(Path(answer["path"]).name, name)
                repeated = json.loads(self.run_migration("--resolve", answer["resolved"]).stdout)
                self.assertTrue(repeated["exists"])
                self.assertEqual(repeated["path"], answer["path"])

    def test_locator_output_escapes_reserved_characters_in_project_root(self):
        sys.path.insert(0, str(SCRIPTS))
        import migrate_mrs
        from _mrs_paths import resolve_locator
        root = self.root / "project#1"
        source = root / ".task-state-auth"
        source.mkdir(parents=True)
        (source / "task_state.md").write_text("fixture\n")
        migrate_mrs.apply(root, [], [])
        answer = resolve_locator(".task-state-auth/task_state.md", root)
        self.assertTrue(answer["exists"])
        self.assertTrue(resolve_locator(answer["resolved"], root)["exists"])

    def test_rewrite_preserves_prose_punctuation_and_delimited_filename_period(self):
        source = self.mrs(".task-state-auth")
        (source / "trailing.").write_text("literal filename\n")
        (source / "utils.md").write_text(
            "See .task-state-auth/evidence.txt.\nSee .task-state-auth/evidence.txt,\n"
            "See .task-state-auth/evidence.txt;\n`.task-state-auth/trailing.`\n")
        tx = self.apply()
        text = (self.root / ".task-state/auth/utils.md").read_text()
        for punctuation in (".", ",", ";"):
            self.assertIn("See .task-state/auth/evidence.txt" + punctuation + "\n", text)
        self.assertIn("`.task-state/auth/trailing.`", text)
        self.assertFalse(any(r["status"] == "preexisting_missing" for r in tx["references"]))

    def test_null_byte_current_references_block_but_do_not_abort_remaining_audit(self):
        source = self.mrs(".task-state-auth")
        (source / "utils.md").write_text(
            f"`.task-state-auth/%00bad`\n[Bad]({source}/%00other)\n`.task-state-auth/evidence.txt`\n")
        preview = json.loads(self.run_migration().stdout)
        self.assertTrue(preview["blocked"])
        statuses = [r["status"] for r in preview["references"]]
        self.assertEqual(statuses.count("invalid_reference"), 2)
        self.assertIn("rewritten", statuses)
        self.assertNotEqual(self.run_migration("--apply").returncode, 0)
        self.assertTrue(source.exists())
        answer = self.run_migration("--resolve", ".task-state-auth/%00bad")
        self.assertNotEqual(answer.returncode, 0)
        self.assertNotIn("lstat", answer.stdout)

    def test_null_byte_history_reference_is_reported_without_blocking_valid_data(self):
        source = self.mrs(".task-state-auth")
        history = "`.task-state-auth/%00bad`\n`.task-state-auth/evidence.txt`\n"
        (source / "progress.md").write_text(history)
        preview = subprocess.run([sys.executable, str(SCRIPTS / "migrate_mrs.py"), str(self.root)],
                                 capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("SKIPPED invalid reference", preview.stdout)
        tx = self.apply()
        self.assertEqual((self.root / ".task-state/auth/progress.md").read_text(), history)
        self.assertTrue(any(r["status"] == "invalid_reference" for r in tx["references"]))


if __name__ == "__main__":
    unittest.main()
