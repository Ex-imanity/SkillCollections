"""Claude timeout continuation preserves its isolated history, not credentials."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"))
from scripts import to_claude


class ClaudeContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = self.root / "settings.json"
        self.proxy = {"ANTHROPIC_BASE_URL": "https://fixture.invalid", "ANTHROPIC_AUTH_TOKEN": "fixture-proxy-token"}
        self.settings.write_text(json.dumps({"env": self.proxy}))
        self.artifact = self.root / "artifact.md"
        self.artifact.write_text("Original artifact\n")
        self.timeout = True
        self.calls = []
        self.stores = []
        self.mode = "settings-env"
        self.user_store = self.root / "oauth-profile"
        self.user_store.mkdir()
        (self.user_store / "user-owned.txt").write_text("keep")

    def runner(self, argv, **kwargs):
        self.calls.append(list(argv))
        store = Path(kwargs["env"]["CLAUDE_CONFIG_DIR"])
        self.stores.append(store)
        session = next(arg.split("=", 1)[1] for arg in argv if arg.startswith(("--session-id=", "--resume=")))
        checkpoint = store / "fixture-session.json"
        if any(arg.startswith("--resume=") for arg in argv):
            self.assertEqual(json.loads(checkpoint.read_text())["session"], session)
            self.assertIn("Continue the SAME unfinished review", kwargs["input"])
        else:
            checkpoint.write_text(json.dumps({"session": session}))
        if self.mode != "inherited":
            self.assertEqual(kwargs["env"]["ANTHROPIC_AUTH_TOKEN"], self.proxy["ANTHROPIC_AUTH_TOKEN"])
            self.assertNotEqual(store, self.user_store)
        self.assertEqual(Path(kwargs["cwd"]).resolve(), self.root.resolve())
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return subprocess.CompletedProcess(argv, 0, json.dumps({"is_error": False, "api_error_status": None,
                                           "result": "APPROVE\nEvidence checked.", "session_id": session,
                                           "total_cost_usd": 0.01}), "")

    def call(self, **overrides):
        if self.mode != "settings-env":
            self.settings.unlink(missing_ok=True)
        kwargs = dict(request_prompt="Review artifact.md without edits.", cd=str(self.root), add_dirs=[str(self.root)],
                      handoff_dir=str(self.root / "handoff"), marker_path=str(self.root / "rounds.json"),
                      gate_id="claude-r1", artifact_key="artifact", cost_log_path=str(self.root / "cost.jsonl"),
                      output_path=str(self.root / "review.md"), settings_path=str(self.settings),
                      runner=self.runner, timeout_seconds=1, max_budget_usd=1,
                      artifact_paths=[str(self.artifact)])
        if self.mode == "explicit-inject":
            kwargs["explicit_env"] = self.proxy
        kwargs.update(overrides)
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.user_store)}, clear=True), \
                mock.patch.object(to_claude, "claude_available", return_value=True), contextlib.redirect_stderr(io.StringIO()):
            return to_claude.review_gate(**kwargs)

    def counts(self):
        return json.loads((self.root / "rounds.json").read_text())["artifact"]

    def test_proxy_timeout_keeps_the_private_store_and_resumes_without_spending_attempt(self):
        first = self.call()
        self.assertEqual(first.status, "timeout")
        self.assertTrue(first.envelope["resumable"])
        store = self.stores[0]
        self.assertTrue(store.is_dir())
        if os.name != "nt":
            self.assertEqual(store.stat().st_mode & 0o777, 0o700)
        self.timeout = False
        result = self.call(resume=True)
        self.assertEqual(result.status, "success")
        self.assertEqual(first.envelope["session_id"], result.envelope["session_id"])
        self.assertEqual(self.stores, [store, store])
        self.assertFalse(store.exists())
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})
        self.assertTrue((self.user_store / "user-owned.txt").exists())
        self.assertEqual(self.artifact.read_text(), "Original artifact\n")

    def test_explicit_proxy_credentials_use_the_same_isolated_lifecycle(self):
        self.mode = "explicit-inject"
        self.assertEqual(self.call().status, "timeout")
        self.timeout = False
        self.assertEqual(self.call(resume=True).status, "success")
        self.assertEqual(self.stores[0], self.stores[1])
        self.assertNotEqual(self.stores[0], self.user_store)
        self.assertFalse(self.stores[0].exists())

    def test_inherited_oauth_profile_is_preserved_after_timeout_and_completion(self):
        self.mode = "inherited"
        first = self.call()
        self.assertEqual(first.status, "timeout")
        self.timeout = False
        self.assertEqual(self.call(resume=True).status, "success")
        self.assertEqual(self.stores, [self.user_store, self.user_store])
        self.assertEqual((self.user_store / "user-owned.txt").read_text(), "keep")

    def test_resolved_reviewer_cannot_be_resumed_again(self):
        self.call()
        self.timeout = False
        self.call(resume=True)
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(len(self.calls), 2)

    def test_private_history_is_not_deleted_on_a_rejected_scope_change(self):
        self.call()
        store = self.stores[0]
        for override in ({"add_dirs": []}, {"max_budget_usd": 2}, {"model": "changed"}):
            with self.subTest(override=override):
                self.assertEqual(self.call(resume=True, **override).status, "continuation_rejected")
                self.assertTrue(store.is_dir())
        self.assertEqual(len(self.calls), 1)

    def test_mismatched_session_does_not_commit_a_success(self):
        self.call()
        self.timeout = False
        def wrong_session(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, json.dumps({"is_error": False,
                "result": "APPROVE", "session_id": "different-session", "total_cost_usd": 0.01}), "")
        result = self.call(resume=True, runner=wrong_session)
        self.assertEqual(result.status, "provenance_failure")
        self.assertFalse(result.envelope["resumable"])
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})
        self.assertFalse(self.stores[0].exists())

    def test_success_without_timeout_cleans_private_store(self):
        self.timeout = False
        self.assertEqual(self.call().status, "success")
        self.assertFalse(self.stores[0].exists())

    def test_state_and_private_history_do_not_contain_injected_credentials(self):
        result = self.call()
        state = Path(result.envelope["continuation_state_path"])
        for path in [state, *self.stores[0].rglob("*")]:
            if path.is_file():
                self.assertNotIn(self.proxy["ANTHROPIC_AUTH_TOKEN"], path.read_text())
                self.assertNotIn(self.proxy["ANTHROPIC_BASE_URL"], path.read_text())

    def test_cap_exhausted_still_allows_original_timeout_to_finish(self):
        (self.root / "rounds.json").write_text(json.dumps({"artifact": {"attempts": 1, "successes": 0}}))
        self.call()
        self.timeout = False
        self.assertEqual(self.call(resume=True).status, "success")
        self.assertEqual(self.counts(), {"attempts": 2, "successes": 1})

    def test_invalid_budget_or_timeout_never_invokes(self):
        for override in ({"max_budget_usd": float("inf")}, {"max_budget_usd": float("nan")},
                         {"timeout_seconds": float("inf")}, {"timeout_seconds": 0}):
            with self.subTest(override=override):
                result = self.call(**override)
                self.assertIn(result.status, {"budget_required", "setup_failure"})
        self.assertEqual(self.calls, [])

    def test_cli_accepts_original_gate_resume_cd_and_actual_artifact_paths(self):
        args = to_claude._build_parser().parse_args([
            "--request-file", "request.md", "--cd", str(self.root), "--add-dir", str(self.root),
            "--handoff-dir", "handoff", "--marker-path", "rounds.json", "--gate-id", "gate",
            "--artifact-key", "artifact", "--cost-log", "cost.jsonl", "--output", "review.md",
            "--max-budget-usd", "1", "--resume", "--artifact-path", "artifact.md"])
        self.assertTrue(args.resume)
        self.assertEqual(args.cd, str(self.root))
        self.assertEqual(args.artifact_paths, ["artifact.md"])

    def test_missing_private_history_or_unsupported_flags_never_starts_a_replacement(self):
        def old_help(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "--max-budget-usd --model", "")
        refused = self.call(session_help_runner=old_help)
        self.assertEqual(refused.status, "setup_failure")
        self.assertFalse((self.root / "rounds.json").exists())
        self.call()
        import shutil
        shutil.rmtree(self.stores[0])
        refused = self.call(resume=True)
        self.assertEqual(refused.status, "setup_failure")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})


if __name__ == "__main__":
    unittest.main()
