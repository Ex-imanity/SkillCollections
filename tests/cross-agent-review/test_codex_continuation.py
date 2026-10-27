"""Native Codex assigns its UUID; timeout must retain it for counted continuation."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"))
from scripts import common, to_codex


SESSION = "a2e62970-a22a-4c7e-9f88-35624d0d5a84"
OTHER_SESSION = "61486ce3-8e5c-48ca-821e-7a3337a7edab"


class CodexContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "codex-home"
        self.history = self.home / "sessions/2026/10/19" / ("rollout-2026-10-19T00-00-00-" + SESSION + ".jsonl")
        self.artifact = self.root / "artifact.md"
        self.artifact.write_text("Original artifact\n")
        self.marker = self.root / "rounds.json"
        self.calls = []
        self.timeout = True
        self.partial = json.dumps({"type": "thread.started", "thread_id": SESSION}) + "\n"
        self.returned_session = SESSION

    def runner(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        self.history.parent.mkdir(parents=True, exist_ok=True)
        self.history.write_text('{"type":"session_meta"}\n')
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=self.partial.encode())
        Path(argv[argv.index("--output-last-message") + 1]).write_text("APPROVE\nEvidence checked.")
        events = self.partial if self.returned_session == SESSION else json.dumps(
            {"type": "thread.started", "thread_id": self.returned_session}) + "\n"
        events += json.dumps({"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 3}})
        return subprocess.CompletedProcess(argv, 0, events, "")

    def call(self, **overrides):
        kwargs = dict(request_prompt="Review artifact.md; do not edit it.", cd=str(self.root),
                      handoff_dir=str(self.root / "handoffs"), marker_path=str(self.marker),
                      gate_id="gate-a", artifact_key="artifact-a", cost_log_path=str(self.root / "cost.jsonl"),
                      output_path=str(self.root / "review.md"), settings_path=str(self.root / "absent-settings"),
                      runner=self.runner, timeout_seconds=1, artifact_paths=[str(self.artifact)])
        kwargs.update(overrides)
        with mock.patch.object(to_codex, "codex_available", return_value=True), \
                mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home)}), \
                contextlib.redirect_stderr(io.StringIO()):
            return to_codex.codex_review_gate(**kwargs)

    def counts(self):
        return json.loads(self.marker.read_text())["artifact-a"]

    def test_timeout_captures_actual_native_thread_uuid_from_partial_bytes(self):
        result = self.call()
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.envelope["session_id"], SESSION)
        self.assertTrue(result.envelope["resumable"])
        state = json.loads(Path(result.envelope["continuation_state_path"]).read_text())
        self.assertEqual((state["state"], state["session_id"]), ("timed_out", SESSION))
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_timeout_without_verified_uuid_cannot_fabricate_a_resumable_session(self):
        self.partial = '{"type":"item.started","thread_id":"' + SESSION + '"}\n'
        result = self.call()
        self.assertFalse(result.envelope.get("resumable", False))
        self.assertEqual(result.status, "provenance_failure")
        self.assertIsNone(result.envelope.get("session_id"))
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_resume_keeps_native_session_and_commits_one_success(self):
        first = self.call()
        self.timeout = False
        result = self.call(resume=True, timeout_seconds=600)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.envelope["session_id"], SESSION)
        argv, kwargs = self.calls[-1]
        self.assertEqual(argv[-3:], ["resume", SESSION, "-"])
        self.assertLess(argv.index("-C"), argv.index("resume"))
        self.assertIn(str(self.root), argv)
        self.assertNotIn("--last", argv)
        self.assertNotIn("--ephemeral", argv)
        self.assertIn("Review artifact.md", kwargs["input"])
        self.assertIn("SAME unfinished review", kwargs["input"])
        self.assertNotIn("Review artifact.md", " ".join(argv))
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})
        self.assertEqual(json.loads(Path(first.envelope["continuation_state_path"]).read_text())["state"], "completed")
        self.assertIn("APPROVE", (self.root / "review.md").read_text())
        self.assertTrue(self.history.exists())
        self.assertFalse(list(self.root.glob(".codex-last-*")))
        self.assertEqual(self.artifact.read_text(), "Original artifact\n")
        logs = [json.loads(line) for line in (self.root / "cost.jsonl").read_text().splitlines()]
        self.assertEqual([(x["attempt"], x["continuation"], x["resumed"]) for x in logs], [(1, 0, False), (1, 1, True)])
        self.assertTrue(all(x["total_cost_usd"] is None for x in logs))

    def test_completed_session_cannot_be_resumed_for_a_free_review(self):
        self.call()
        self.timeout = False
        self.call(resume=True)
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})

    def test_repeated_timeout_keeps_attempt_and_uuid_then_can_finish(self):
        self.call()
        # A timeout before resume emits thread.started still retains the
        # already known identity; it must never adopt a new random UUID.
        self.partial = ""
        second = self.call(resume=True)
        self.assertEqual(second.status, "timeout")
        self.assertEqual(second.envelope["session_id"], SESSION)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})
        self.partial = json.dumps({"type": "thread.started", "thread_id": SESSION}) + "\n"
        self.timeout = False
        final = self.call(resume=True)
        self.assertEqual(final.status, "success")
        self.assertEqual(final.envelope["continuation"], 2)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})

    def test_resume_at_fresh_attempt_cap_reuses_second_attempt(self):
        self.marker.write_text(json.dumps({"artifact-a": {"attempts": 1, "successes": 0}}))
        self.call()
        self.timeout = False
        self.assertEqual(self.call(resume=True).status, "success")
        self.assertEqual(self.counts(), {"attempts": 2, "successes": 1})

    def test_changed_request_files_scope_model_or_store_is_rejected(self):
        first = self.call()
        path = Path(first.envelope["continuation_state_path"])
        original = path.read_text()
        for overrides in ({"request_prompt": "Different review"}, {"artifact_key": "other"},
                          {"model": "different-model"}, {"cd": str(self.home)},
                          {"output_path": str(self.root / "other.md")}, {"artifact_paths": []},
                          {"cost_log_path": str(self.root / "other.jsonl")}):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.call(resume=True, **overrides).status, "continuation_rejected")
                self.assertEqual(path.read_text(), original)
        old_home = self.home
        self.home = self.root / "other-home"
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.home = old_home
        self.artifact.write_text("Different content\n")
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_missing_native_history_is_refused_before_native_call(self):
        first = self.call()
        before = Path(first.envelope["continuation_state_path"]).read_text()
        self.history.unlink()
        self.assertEqual(self.call(resume=True).status, "setup_failure")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(Path(first.envelope["continuation_state_path"]).read_text(), before)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_archived_history_is_retained_and_can_resume(self):
        self.call()
        archive = self.home / "archived_sessions" / self.history.name
        archive.parent.mkdir()
        self.history.rename(archive)
        self.timeout = False
        self.assertEqual(self.call(resume=True).status, "success")
        self.assertTrue(archive.exists())

    def test_wrong_native_session_on_success_or_timeout_never_becomes_free_work(self):
        for is_timeout in (True, False):
            with self.subTest(timeout=is_timeout):
                self.setUp()
                self.call()
                self.timeout = is_timeout
                self.returned_session = OTHER_SESSION
                self.partial = json.dumps({"type": "thread.started", "thread_id": OTHER_SESSION}) + "\n"
                result = self.call(resume=True)
                self.assertEqual(result.status, "provenance_failure")
                self.assertFalse(result.envelope["resumable"])
                self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})
                self.assertFalse((self.root / "review.md").exists())

    def test_missing_damaged_or_running_state_cannot_start_a_resume(self):
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(self.calls, [])
        first = self.call()
        path = Path(first.envelope["continuation_state_path"])
        data = json.loads(path.read_text()); data["state"] = "running"
        path.write_text(json.dumps(data))
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        path.write_text("damaged")
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(path.read_text(), "damaged")
        self.assertEqual(len(self.calls), 1)

    def test_reset_counter_cannot_reuse_timeout_exemption(self):
        self.call()
        self.marker.unlink()
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(len(self.calls), 1)

    def test_fresh_call_does_not_replace_unfinished_session(self):
        self.call()
        self.assertEqual(self.call().status, "continuation_rejected")
        self.assertEqual(len(self.calls), 1)

    def test_auth_failure_is_counted_and_not_resumable(self):
        def failed(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, "", "unauthorized")
        self.assertEqual(self.call(runner=failed).status, "auth_failure")
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_cost_log_failure_cannot_leave_a_free_resumable_timeout(self):
        with mock.patch.object(common, "log_cost", side_effect=OSError("disk unavailable")):
            result = self.call()
        self.assertEqual(result.status, "cost_log_failure")
        self.assertFalse(result.envelope["resumable"])
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")

    def test_partial_text_and_truncated_final_line_keep_verified_identity(self):
        self.partial += '{"type":"item.started",'
        def text_timeout(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=self.partial)
        self.assertEqual(self.call(runner=text_timeout).envelope["session_id"], SESSION)

    def test_invalid_timeout_or_unsupported_native_resume_spends_no_attempt(self):
        for value in (0, -1, float("inf"), float("nan")):
            self.assertEqual(self.call(timeout_seconds=value).status, "setup_failure")
        def old_help(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "Usage: codex exec --json", "")
        self.assertEqual(self.call(session_help_runner=old_help).status, "setup_failure")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.marker.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX wrapper/child process regression")
    def test_timeout_stops_native_child_of_cli_wrapper_before_resuming(self):
        marker = self.root / "orphan-kept-working"
        script = self.root / "wrapper.py"
        script.write_text('''import json, subprocess, sys, time
subprocess.Popen([sys.executable, '-c', 'import pathlib,time,sys; time.sleep(0.6); pathlib.Path(sys.argv[1]).touch()', str(sys.argv[1])])
print(json.dumps({'type':'thread.started','thread_id':'a2e62970-a22a-4c7e-9f88-35624d0d5a84'}),flush=True)
time.sleep(10)
''')
        result = to_codex.run_codex_review([sys.executable, str(script), str(marker)],
                                            str(self.root / "last.txt"), timeout_seconds=0.25)
        self.assertEqual(result.status, "timeout")
        time.sleep(0.8)
        self.assertFalse(marker.exists(), "the native child survived the CLI wrapper's timeout")

    def test_windows_cleanup_timeout_cannot_reopen_a_resumable_gate(self):
        self.call()
        class WindowsOS:
            name = "nt"
            def __getattr__(self, name):
                return getattr(os, name)
        process = mock.MagicMock()
        process.__enter__.return_value = process
        process.pid = 999999
        process.communicate.side_effect = subprocess.TimeoutExpired(["codex"], 1)
        with mock.patch.object(to_codex, "os", WindowsOS()), \
                mock.patch.object(subprocess, "Popen", return_value=process), \
                mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(["taskkill"], 5)):
            result = self.call(resume=True, runner=to_codex._run_codex_subprocess)
        self.assertEqual(result.status, "other_error")
        self.assertFalse(result.envelope["resumable"])
        self.assertEqual(self.call(resume=True).status, "continuation_rejected")
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 0})

    def test_failed_windows_taskkill_is_not_a_verified_timeout_cleanup(self):
        class WindowsOS:
            name = "nt"
        process = mock.MagicMock()
        process.__enter__.return_value = process
        process.pid = 999999
        process.communicate.side_effect = [subprocess.TimeoutExpired(["codex"], 1), ("", "")]
        with mock.patch.object(to_codex, "os", WindowsOS()), \
                mock.patch.object(subprocess, "Popen", return_value=process), \
                mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(["taskkill"], 1)):
            result = to_codex.run_codex_review(["codex"], str(self.root / "last.txt"),
                                              runner=to_codex._run_codex_subprocess, timeout_seconds=1)
        self.assertEqual(result.status, "other_error")

    @unittest.skipIf(os.name == "nt", "POSIX executable fixture")
    def test_source_cli_real_subprocess_timeout_resume_and_completed_refusal(self):
        # Removing TimeoutExpired.stdout capture, using the wrong native
        # subcommand/flags, or reserving a fresh attempt breaks this contract.
        executable = self.root / "bin/codex"
        executable.parent.mkdir()
        executable.write_text("#!" + sys.executable + "\n" + '''import json, os, pathlib, sys, time
args=sys.argv[1:]
if '--help' in args:
    print('SESSION_ID --json --output-last-message'); sys.exit(0)
assert args[0]=='exec'
prompt=sys.stdin.read()
assert 'Review artifact.md' in prompt
sid='a2e62970-a22a-4c7e-9f88-35624d0d5a84'
history=pathlib.Path(os.environ['CODEX_HOME'])/'sessions'/('rollout-fixture-'+sid+'.jsonl')
history.parent.mkdir(parents=True, exist_ok=True)
if 'resume' not in args:
    history.write_text('{"type":"session_meta"}\\n')
    print(json.dumps({'type':'thread.started','thread_id':sid}), flush=True)
    time.sleep(10)
else:
    assert args[-3:]==['resume',sid,'-']
    assert args.index('-C')<args.index('resume')
    assert 'SAME unfinished review' in prompt
    assert history.exists()
    pathlib.Path(args[args.index('--output-last-message')+1]).write_text('APPROVE\\nFixture checked.')
    print(json.dumps({'type':'thread.started','thread_id':sid}))
    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':2,'output_tokens':3}}))
''')
        executable.chmod(0o755)
        request = self.root / "request.md"
        request.write_text("Review artifact.md; do not edit it.")
        args = [sys.executable, "-m", "scripts.to_codex", "--request-file", str(request),
                "--cd", str(self.root), "--handoff-dir", str(self.root / "handoffs"),
                "--marker-path", str(self.marker), "--gate-id", "gate-a", "--artifact-key", "artifact-a",
                "--cost-log", str(self.root / "cost.jsonl"), "--output", str(self.root / "review.md"),
                "--settings", str(self.root / "absent-settings"), "--artifact-path", str(self.artifact),
                "--timeout-seconds", "0.3"]
        env = {**os.environ, "CODEX_HOME": str(self.home),
               "PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", "")}
        first = subprocess.run(args, cwd=Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review", env=env,
                               capture_output=True, text=True, timeout=5)
        first_payload = json.loads(first.stdout)
        self.assertEqual(first_payload["status"], "timeout", first.stderr)
        self.assertEqual(first_payload["session_id"], SESSION)
        args[-1] = "3"
        args += ["--resume"]
        second = subprocess.run(args, cwd=Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review", env=env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(json.loads(second.stdout)["status"], "success", second.stderr)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})
        final = subprocess.run(args, cwd=Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review", env=env,
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(json.loads(final.stdout)["status"], "continuation_rejected")
        self.assertNotIn("review_started", final.stderr)
        self.assertEqual(self.counts(), {"attempts": 1, "successes": 1})


if __name__ == "__main__":
    unittest.main()
