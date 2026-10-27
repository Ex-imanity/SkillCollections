"""A timed-out review can continue, without spending a fresh logical attempt."""

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
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"))
from scripts import common, continuation, to_grok


class GrokContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifact = self.root / "artifact.md"
        self.artifact.write_text("Original artifact\n")
        self.marker = self.root / "rounds.json"
        self.calls = []
        self.timeout = True
        self.wrong_session = False

    def runner(self, argv, **kwargs):
        self.calls.append(list(argv))
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        session = next(a.split("=", 1)[1] for a in argv if a.startswith(("--session-id=", "--resume=")))
        return subprocess.CompletedProcess(argv, 0, json.dumps({
            "text": "APPROVE\nEvidence checked.",
            "sessionId": "wrong-session" if self.wrong_session else session,
            "stopReason": "end_turn", "usage": {"input_tokens": 2, "output_tokens": 3},
            "total_cost_usd": 0.01,
        }), "")

    def call(self, **overrides):
        kwargs = dict(request_prompt="Review artifact.md; do not edit it.", cd=str(self.root),
                      handoff_dir=str(self.root / "handoffs"), marker_path=str(self.marker),
                      gate_id="gate-a", artifact_key="artifact-a", cost_log_path=str(self.root / "cost.jsonl"),
                      output_path=str(self.root / "review.md"), settings_path=str(self.root / "absent-settings"),
                      runner=self.runner, timeout_seconds=1, artifact_paths=[str(self.artifact)])
        kwargs.update(overrides)
        with mock.patch.object(to_grok, "grok_available", return_value=True), contextlib.redirect_stderr(io.StringIO()):
            return to_grok.grok_review_gate(**kwargs)

    def counts(self):
        return json.loads(self.marker.read_text())["artifact-a"]

    def state_path(self, result):
        return Path(result.envelope["continuation_state_path"])

    def test_timeout_retains_uuid_and_unfinished_state(self):
        result = self.call()
        self.assertEqual(result.status, "timeout")
        UUID(result.envelope["session_id"])
        self.assertTrue(result.envelope["resumable"])
        state = json.loads(self.state_path(result).read_text())
        self.assertEqual(state["state"], "timed_out")
        self.assertEqual(state["session_id"], result.envelope["session_id"])
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})
        self.assertNotIn("Review artifact.md", self.state_path(result).read_text())

    def test_resume_reuses_session_and_commits_once_without_new_attempt(self):
        initial = self.call()
        self.timeout = False
        result = self.call(resume=True, timeout_seconds=600)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.envelope["session_id"], initial.envelope["session_id"])
        self.assertIn("--resume=" + initial.envelope["session_id"], self.calls[-1])
        self.assertFalse(any(a.startswith("--session-id") for a in self.calls[-1]))
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})
        self.assertEqual(json.loads(self.state_path(result).read_text())["state"], "completed")
        logs = [json.loads(line) for line in (self.root / "cost.jsonl").read_text().splitlines()]
        self.assertEqual([line["continuation"] for line in logs], [0, 1])
        self.assertEqual([line["attempt"] for line in logs], [1, 1])
        self.assertIsNone(logs[0]["total_cost_usd"])
        self.assertEqual(logs[1]["total_cost_usd"], 0.01)
        self.assertEqual(self.artifact.read_text(), "Original artifact\n")
        self.assertIn("APPROVE", (self.root / "review.md").read_text())

    def test_unlogged_timeout_cannot_be_replayed_as_free_work(self):
        with mock.patch.object(common, "log_cost", side_effect=OSError("disk unavailable")):
            failed = self.call()
        self.assertEqual(failed.status, "cost_log_failure")
        self.assertFalse(failed.envelope["resumable"])
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_resume_prompt_and_lifecycle_retain_original_review_context(self):
        initial = self.call()
        self.timeout = False
        observed = {}
        def runner(argv, **kwargs):
            observed["prompt"] = Path(argv[argv.index("--prompt-file") + 1]).read_text()
            observed["event"] = json.loads(captured.getvalue())
            return self.runner(argv, **kwargs)
        captured = io.StringIO()
        with mock.patch.object(to_grok, "grok_available", return_value=True), contextlib.redirect_stderr(captured):
            result = to_grok.grok_review_gate(
                request_prompt="Review artifact.md; do not edit it.", cd=str(self.root),
                handoff_dir=str(self.root / "handoffs"), marker_path=str(self.marker),
                gate_id="gate-a", artifact_key="artifact-a", cost_log_path=str(self.root / "cost.jsonl"),
                output_path=str(self.root / "review.md"), settings_path=str(self.root / "absent-settings"),
                runner=runner, timeout_seconds=1, artifact_paths=[str(self.artifact)], resume=True)
        self.assertEqual(result.status, "success")
        self.assertIn("Continue the SAME unfinished review", observed["prompt"])
        self.assertIn("Review artifact.md; do not edit it.", observed["prompt"])
        self.assertEqual(observed["event"]["attempt"], 1)
        self.assertEqual(observed["event"]["continuation"], 1)
        self.assertEqual(observed["event"]["session_id"], initial.envelope["session_id"])

    def test_continuation_is_allowed_when_new_attempt_cap_is_exhausted(self):
        self.marker.write_text(json.dumps({"artifact-a": {"attempts": 1, "successes": 0}}))
        self.call()
        self.timeout = False
        result = self.call(resume=True)
        self.assertEqual(result.status, "success")
        self.assertEqual(self.counts(), {"attempts": 2, "successes": 1})

    def test_repeated_timeouts_keep_the_original_attempt(self):
        initial = self.call()
        second = self.call(resume=True)
        self.assertEqual(second.status, "timeout")
        self.assertTrue(second.envelope["resumable"])
        self.timeout = False
        final = self.call(resume=True)
        self.assertEqual(final.status, "success")
        self.assertEqual(final.envelope["session_id"], initial.envelope["session_id"])
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})
        self.assertEqual(final.envelope["continuation"], 2)

    def test_completed_gate_cannot_be_resumed_for_a_free_review(self):
        self.call()
        self.timeout = False
        self.call(resume=True)
        refused = self.call(resume=True)
        self.assertEqual(refused.status, "continuation_rejected")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})

    def test_missing_continuation_never_creates_a_fresh_session(self):
        refused = self.call(resume=True)
        self.assertEqual(refused.status, "continuation_rejected")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.marker.exists())

    def test_changed_request_scope_model_or_artifact_is_rejected_before_call(self):
        initial = self.call()
        original_state = self.state_path(initial).read_text()
        for override in ({"request_prompt": "Review something else"}, {"artifact_key": "different"},
                         {"cd": str(self.root / "other")}, {"model": "different-model"},
                         {"output_path": str(self.root / "other-review.md")}, {"artifact_paths": []},
                         {"cost_log_path": str(self.root / "different-cost.jsonl")},
                         {"explicit_env": {"GROK_HOME": str(self.root / "other-home")}}):
            with self.subTest(override=override):
                refused = self.call(resume=True, **override)
                self.assertEqual(refused.status, "continuation_rejected")
                self.assertEqual(self.state_path(initial).read_text(), original_state)
        self.artifact.write_text("Changed artifact\n")
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_a_running_or_damaged_record_is_not_resumable(self):
        initial = self.call()
        path = self.state_path(initial)
        data = json.loads(path.read_text())
        data["state"] = "running"
        path.write_text(json.dumps(data))
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        path.write_text("not json")
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(path.read_text(), "not json")
        self.assertEqual(len(self.calls), 1)

    def test_non_timeout_failure_cannot_claim_the_resume_exemption(self):
        def failed(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, '{"type":"error","message":"unauthorized"}', "")
        self.assertEqual(self.call(runner=failed).status, "auth_failure")
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_resume_session_mismatch_never_commits_success(self):
        self.call()
        self.timeout, self.wrong_session = False, True
        result = self.call(resume=True)
        self.assertEqual(result.status, "provenance_failure")
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})
        self.assertFalse((self.root / "review.md").exists())
        self.assertFalse(result.envelope["resumable"])

    def test_timeout_without_resume_does_not_implicitly_spend_a_new_attempt(self):
        self.call()
        result = self.call()
        self.assertEqual(result.status, "continuation_rejected")
        self.assertEqual(len(self.calls), 1)

    def test_reset_marker_cannot_reuse_an_old_timeout_exemption(self):
        self.call()
        self.marker.unlink()
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(len(self.calls), 1)

    def test_unwritable_identity_does_not_spend_attempt_or_emit_started(self):
        with mock.patch.object(continuation, "_atomic_write_text", side_effect=OSError("not writable")):
            result = self.call()
        self.assertEqual(result.status, "setup_failure")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.marker.exists())

    def test_cli_has_explicit_resume_and_file_binding_options(self):
        args = to_grok._build_parser().parse_args([
            "--request-file", "request.md", "--cd", str(self.root), "--handoff-dir", "handoffs",
            "--marker-path", str(self.marker), "--gate-id", "gate-a", "--artifact-key", "artifact-a",
            "--cost-log", "cost.jsonl", "--output", "review.md", "--resume", "--artifact-path", str(self.artifact)])
        self.assertTrue(args.resume)
        self.assertEqual(args.artifact_paths, [str(self.artifact)])

    def test_invalid_time_limit_or_unsupported_session_flags_does_not_spend_attempt(self):
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                self.assertEqual(self.call(timeout_seconds=timeout).status, "setup_failure")
        def old_help(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "--prompt-file --model --output-format", "")
        self.assertEqual(self.call(session_help_runner=old_help).status, "setup_failure")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.marker.exists())

    def test_two_concurrent_resumes_cannot_deliver_two_free_reviews(self):
        self.call()
        self.timeout = False
        entered, release = threading.Event(), threading.Event()
        def slow_runner(argv, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return self.runner(argv, **kwargs)
        # One global redirect/patch for both workers; the shared file lock,
        # rather than per-thread test scaffolding, serializes the calls.
        with mock.patch.object(to_grok, "grok_available", return_value=True), \
                contextlib.redirect_stderr(io.StringIO()), ThreadPoolExecutor(2) as pool:
            def call():
                return to_grok.grok_review_gate(
                    request_prompt="Review artifact.md; do not edit it.", cd=str(self.root),
                    handoff_dir=str(self.root / "handoffs"), marker_path=str(self.marker),
                    gate_id="gate-a", artifact_key="artifact-a", cost_log_path=str(self.root / "cost.jsonl"),
                    output_path=str(self.root / "review.md"), settings_path=str(self.root / "absent-settings"),
                    runner=slow_runner, timeout_seconds=1, artifact_paths=[str(self.artifact)], resume=True)
            first = pool.submit(call)
            self.assertTrue(entered.wait(3))
            second = pool.submit(call)
            release.set()
            results = [first.result(3), second.result(3)]
        self.assertEqual(sorted(r.status for r in results), ["continuation_rejected", "success"])
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})
        self.assertEqual(len(self.calls), 2)

    @unittest.skipIf(os.name == "nt", "POSIX executable fixture")
    def test_real_subprocess_timeout_and_resume_without_a_model_call(self):
        fake = self.root / "grok-fixture"
        fake.write_text("#!" + sys.executable + "\n" + '''import json, sys, time
args = sys.argv[1:]
if any(arg.startswith('--session-id=') for arg in args):
    time.sleep(10)
else:
    sid = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--resume='))
    print(json.dumps({'sessionId': sid, 'text': 'APPROVE', 'stopReason': 'end_turn',
                      'usage': {'input_tokens': 1, 'output_tokens': 1}}))
''')
        fake.chmod(0o755)
        def local_runner(argv, **kwargs):
            return subprocess.run([str(fake), *argv[1:]], **kwargs)
        initial = self.call(runner=local_runner, timeout_seconds=0.1)
        self.assertEqual(initial.status, "timeout")
        result = self.call(runner=local_runner, resume=True, timeout_seconds=2)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.envelope["session_id"], initial.envelope["session_id"])
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})


if __name__ == "__main__":
    unittest.main()
