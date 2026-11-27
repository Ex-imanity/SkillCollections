"""Native Antigravity (`agy`) timeout continuation, history validation, and bounded cleanup."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"
sys.path.insert(0, str(SKILL_DIR))

from scripts import common, to_agy


SESSION = "f7965130-c060-4181-abcf-4fadb1054401"
OTHER_SESSION = "61486ce3-8e5c-48ca-821e-7a3337a7edab"


def _init_line(session_id: str = SESSION) -> bytes:
    return (json.dumps({"event": "init", "conversation_id": session_id}) + "\n").encode("utf-8")


def _result_line(
    session_id: str = SESSION,
    status: str = "SUCCESS",
    response: str = "APPROVE\nEvidence checked.",
    error: str | None = None,
) -> bytes:
    payload: dict = {
        "conversation_id": session_id,
        "status": status,
        "response": response,
        "num_turns": 1,
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }
    if error is not None:
        payload["error"] = error
    return (json.dumps({"event": "result", "result": payload}) + "\n").encode("utf-8")


class AgyContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.agy_home = self.root / "agy-home"
        self.history = self.agy_home / "conversations" / f"{SESSION}.db"
        self.artifact = self.root / "artifact.md"
        self.artifact.write_text("Original artifact\n", encoding="utf-8")
        self.extra_dir = self.root / "extra-repo"
        self.extra_dir.mkdir()
        self.marker = self.root / "rounds.json"
        self.calls: list[tuple[list[str], dict]] = []
        self.timeout = True
        self.partial = _init_line(SESSION)
        self.returned_session = SESSION

    def runner(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        self.history.parent.mkdir(parents=True, exist_ok=True)
        self.history.write_bytes(b"SQLite format 3\x00dummy-session-data")
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=self.partial)
        stream = _init_line(self.returned_session) + _result_line(self.returned_session)
        return subprocess.CompletedProcess(argv, 0, stream, b"")

    def call(self, **overrides):
        kwargs = dict(
            request_prompt="Review artifact.md; do not edit it.",
            cd=str(self.root),
            add_dirs=[str(self.extra_dir)],
            handoff_dir=str(self.root / "handoffs"),
            marker_path=str(self.marker),
            gate_id="gate-a",
            artifact_key="artifact-a",
            cost_log_path=str(self.root / "cost.jsonl"),
            output_path=str(self.root / "review.md"),
            settings_path=str(self.root / "absent-settings"),
            runner=self.runner,
            timeout_seconds=1,
            artifact_paths=[str(self.artifact)],
            agy_home=str(self.agy_home),
        )
        kwargs.update(overrides)
        with mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                contextlib.redirect_stderr(io.StringIO()):
            return to_agy.agy_review_gate(**kwargs)

    def counts(self) -> dict:
        return json.loads(self.marker.read_text(encoding="utf-8"))["artifact-a"]

    def test_timeout_captures_init_uuid_from_partial_bytes_and_truncated_tail(self) -> None:
        self.partial = _init_line(SESSION) + b'{"event":"step_update","step_update":{'
        result = self.call()
        self.assertEqual("timeout", result.status)
        self.assertEqual(SESSION, result.envelope["session_id"])
        self.assertTrue(result.envelope["resumable"])
        state = json.loads(Path(result.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual(("timed_out", SESSION), (state["state"], state["session_id"]))
        self.assertEqual({"attempts": 1, "successes": 0}, self.counts())

    def test_timeout_invalid_streams_are_not_resumable(self) -> None:
        cases = [
            ("no_init", b'{"event":"step_update","step_update":{"step_index":0}}\n', "provenance_failure"),
            ("unterminated_init_without_lf", _init_line(SESSION).rstrip(b"\n"), "provenance_failure"),
            ("valid_init_then_lf_terminated_corrupt", _init_line(SESSION) + b'{"bad\n', "provenance_failure"),
            ("one_valid_one_invalid_init", _init_line(SESSION) + b'{"event":"init","conversation_id":"bad"}\n', "provenance_failure"),
            ("non_trailing_corrupt_json", b'{"broken\n' + _init_line(SESSION), "provenance_failure"),
            ("deeply_nested_json_on_timeout", _init_line(SESSION) + (b"[" * 2000 + b"]" * 2000 + b"\n"), "provenance_failure"),
            ("complete_success_before_timeout", _init_line(SESSION) + _result_line(SESSION, status="SUCCESS"), "other_error"),
            ("complete_error_before_timeout", _init_line(SESSION) + _result_line(SESSION, status="ERROR", response="", error="boom"), "other_error"),
        ]
        for name, partial_bytes, expected_status in cases:
            with self.subTest(case=name):
                self.setUp()
                self.partial = partial_bytes
                res = self.call()
                self.assertEqual(expected_status, res.status)
                self.assertFalse(res.envelope.get("resumable", False))
                state = json.loads(Path(res.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
                self.assertEqual("failed", state["state"])
                self.assertTrue((self.root / "cost.jsonl").is_file())
                self.assertTrue(Path(res.envelope["handoff_path"]).is_file())
                self.assertEqual("continuation_rejected", self.call(resume=True).status)

    def test_timeout_without_artifact_path_is_non_resumable_everywhere(self) -> None:
        res = self.call(artifact_paths=[])
        self.assertEqual("other_error", res.status)
        self.assertFalse(res.envelope.get("resumable", False))
        state = json.loads(Path(res.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual("failed", state["state"])
        handoff_text = Path(res.envelope["handoff_path"]).read_text(encoding="utf-8")
        self.assertNotIn("--resume", handoff_text)
        self.assertEqual("continuation_rejected", self.call(resume=True, artifact_paths=[]).status)

    def test_resume_requires_matching_init_receipt_and_decorate_is_idempotent(self) -> None:
        # 1) Resumed timeout WITHOUT init receipt fails closed and is no longer resumable.
        self.call()
        self.partial = b""
        resumed_missing = self.call(resume=True)
        self.assertEqual("provenance_failure", resumed_missing.status)
        self.assertFalse(resumed_missing.envelope.get("resumable", False))
        state = json.loads(Path(resumed_missing.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual("failed", state["state"])
        self.assertEqual({"attempts": 1, "successes": 0}, self.counts())
        self.assertEqual("continuation_rejected", self.call(resume=True).status)

        # 2) Resumed timeout WITH matching init receipt remains resumable and can succeed.
        self.setUp()
        self.call()
        self.partial = _init_line(SESSION)
        second = self.call(resume=True)
        self.assertEqual("timeout", second.status)
        self.assertTrue(second.envelope["resumable"])
        self.assertEqual(SESSION, second.envelope["session_id"])
        self.assertEqual({"attempts": 1, "successes": 0}, self.counts())
        self.timeout = False
        final = self.call(resume=True)
        self.assertEqual("success", final.status)
        self.assertEqual(2, final.envelope["continuation"])
        self.assertEqual({"attempts": 1, "successes": 1}, self.counts())

        # 3) Resumed timeout or success WITH different UUID fails closed.
        for is_timeout in (True, False):
            with self.subTest(timeout=is_timeout):
                self.setUp()
                self.call()
                self.timeout = is_timeout
                self.returned_session = OTHER_SESSION
                self.partial = _init_line(OTHER_SESSION)
                res = self.call(resume=True)
                self.assertEqual("provenance_failure", res.status)
                self.assertFalse(res.envelope.get("resumable", False))
                self.assertEqual({"attempts": 1, "successes": 0}, self.counts())
                self.assertFalse((self.root / "review.md").exists())

    def test_resume_sends_conversation_flag_and_commits_single_success_with_audit(self) -> None:
        first = self.call()
        self.timeout = False
        result = self.call(resume=True, timeout_seconds=600)
        self.assertEqual("success", result.status)
        self.assertEqual(SESSION, result.envelope["session_id"])
        argv, kwargs = self.calls[-1]
        self.assertIn(f"--conversation={SESSION}", argv)
        self.assertNotIn("--continue", argv)
        self.assertNotIn("-c", argv)
        prompt_payload = json.loads(kwargs["input"].decode("utf-8"))
        self.assertIn("SAME unfinished review", prompt_payload["message"]["content"])
        self.assertIn("Review artifact.md", prompt_payload["message"]["content"])
        self.assertEqual({"attempts": 1, "successes": 1}, self.counts())
        self.assertEqual(
            "completed",
            json.loads(Path(first.envelope["continuation_state_path"]).read_text(encoding="utf-8"))["state"],
        )
        self.assertIn("APPROVE", (self.root / "review.md").read_text(encoding="utf-8"))
        self.assertTrue(self.history.exists())
        logs = [json.loads(line) for line in (self.root / "cost.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(x["attempt"], x["continuation"], x["resumed"]) for x in logs], [(1, 0, False), (1, 1, True)])
        self.assertTrue(all(x["total_cost_usd"] is None for x in logs))
        # Completed gate cannot be resumed again.
        self.assertEqual("continuation_rejected", self.call(resume=True).status)
        self.assertEqual(2, len(self.calls))

    def test_caps_concurrency_and_io_failure_close_resumability(self) -> None:
        # 2 failed fresh attempts block 3rd attempt.
        def failing(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, _init_line(SESSION) + _result_line(status="ERROR", response="", error="fail"), b"")

        self.assertEqual("other_error", self.call(gate_id="g1", runner=failing).status)
        self.assertEqual("other_error", self.call(gate_id="g2", runner=failing).status)
        self.assertEqual("attempt_cap_exceeded", self.call(gate_id="g3", runner=failing).status)

        # 2 committed successes block 3rd review.
        self.setUp()
        self.timeout = False
        self.assertEqual("success", self.call(gate_id="s1").status)
        self.assertEqual("success", self.call(gate_id="s2").status)
        self.assertEqual("round_cap_exceeded", self.call(gate_id="s3").status)

        # Resume allowed at fresh attempt cap (attempt 2).
        self.setUp()
        self.marker.write_text(json.dumps({"artifact-a": {"attempts": 1, "successes": 0}}), encoding="utf-8")
        self.assertEqual("timeout", self.call().status)
        self.timeout = False
        self.assertEqual("success", self.call(resume=True).status)
        self.assertEqual({"attempts": 2, "successes": 1}, self.counts())

        # Concurrent resume under shared marker lock commits success only once.
        self.setUp()
        self.assertEqual("timeout", self.call().status)
        self.timeout = False
        results: list = []

        def slow_runner(argv, **kwargs):
            time.sleep(0.1)
            return self.runner(argv, **kwargs)

        def worker():
            results.append(self.call(resume=True, runner=slow_runner))

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        statuses = sorted(r.status for r in results)
        self.assertEqual(["continuation_rejected", "success"], statuses)
        self.assertEqual({"attempts": 1, "successes": 1}, self.counts())

        # cost_log failure closes resumability.
        self.setUp()
        with mock.patch.object(common, "log_cost", side_effect=OSError("disk full")):
            res = self.call()
        self.assertEqual("cost_log_failure", res.status)
        self.assertFalse(res.envelope.get("resumable", False))
        self.assertEqual("continuation_rejected", self.call(resume=True).status)

        # persist_success failure closes resumability.
        self.setUp()
        self.timeout = False
        with mock.patch.object(common, "persist_success", side_effect=OSError("read-only")):
            res = self.call()
        self.assertEqual("persistence_failure", res.status)
        self.assertFalse(res.envelope.get("resumable", False))
        self.assertEqual("continuation_rejected", self.call(resume=True).status)

    def test_changed_bindings_rejected(self) -> None:
        first = self.call()
        path = Path(first.envelope["continuation_state_path"])
        original = path.read_text(encoding="utf-8")
        other_extra = self.root / "other-extra"
        other_extra.mkdir()
        other_home = self.root / "other-home"
        other_home.mkdir()
        for overrides in (
            {"request_prompt": "Different review"},
            {"artifact_key": "other"},
            {"model": "gemini-4-neon-high"},
            {"cd": str(self.extra_dir)},
            {"add_dirs": []},
            {"add_dirs": [str(self.extra_dir), str(other_extra)]},
            {"output_path": str(self.root / "other.md")},
            {"cost_log_path": str(self.root / "other.jsonl")},
            {"agy_home": str(other_home)},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual("continuation_rejected", self.call(resume=True, **overrides).status)
                self.assertEqual(original, path.read_text(encoding="utf-8"))
        self.artifact.write_text("Modified artifact\n", encoding="utf-8")
        self.assertEqual("continuation_rejected", self.call(resume=True).status)
        self.assertEqual(1, len(self.calls))
        self.assertEqual({"attempts": 1, "successes": 0}, self.counts())

    def test_native_history_validation_rejects_missing_empty_wal_only_and_escaping_symlink(self) -> None:
        # Missing .db
        first = self.call()
        before = Path(first.envelope["continuation_state_path"]).read_text(encoding="utf-8")
        self.history.unlink()
        self.assertEqual("setup_failure", self.call(resume=True).status)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(before, Path(first.envelope["continuation_state_path"]).read_text(encoding="utf-8"))

        # Empty 0-byte .db
        self.history.write_bytes(b"")
        self.assertEqual("setup_failure", self.call(resume=True).status)

        # Orphan .db-wal with missing .db (and with 0-byte .db)
        wal = self.history.with_name(self.history.name + "-wal")
        wal.write_bytes(b"wal-bytes")
        self.assertEqual("setup_failure", self.call(resume=True).status)
        self.history.unlink()
        self.assertEqual("setup_failure", self.call(resume=True).status)
        wal.unlink()

        # Symlink escaping session_store
        if os.name == "posix":
            outside = self.root / "outside.db"
            outside.write_bytes(b"non-empty")
            self.history.symlink_to(outside)
            self.assertEqual("setup_failure", self.call(resume=True).status)
            self.history.unlink()

        # Valid non-empty .db where native CLI refuses resume -> other_error, state failed
        self.history.write_bytes(b"SQLite format 3\x00data")
        def native_refuse(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv, 1,
                _init_line(SESSION) + _result_line(status="ERROR", response="", error="conversation not found"),
                b"",
            )
        res = self.call(resume=True, runner=native_refuse)
        self.assertEqual("other_error", res.status)
        self.assertFalse(res.envelope.get("resumable", False))
        state = json.loads(Path(res.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
        self.assertEqual("failed", state["state"])

    @unittest.skipUnless(os.name == "posix", "POSIX process-group regression")
    def test_posix_timeout_kills_owned_pgid_and_detached_stdout_holder_fails_bounded(self) -> None:
        # 1) Owned PGID child is killed on timeout.
        marker = self.root / "orphan-kept-working"
        script = self.root / "wrapper.py"
        script.write_text(
            "import json, subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', 'import pathlib,time,sys; time.sleep(0.6); pathlib.Path(sys.argv[1]).touch()', sys.argv[1]])\n"
            f"print(json.dumps({{'event':'init','conversation_id':'{SESSION}'}}), flush=True)\n"
            "time.sleep(10)\n",
            encoding="utf-8",
        )
        result = to_agy.run_agy_review(
            [sys.executable, str(script), str(marker)],
            timeout_seconds=0.25,
            prompt="Review.",
            cwd=str(self.root),
        )
        self.assertEqual("timeout", result.status)
        self.assertEqual(SESSION, result.envelope["session_id"])
        time.sleep(0.8)
        self.assertFalse(marker.exists(), "owned child survived agy wrapper timeout")

        # 2) Detached grandchild holding stdout open past post-exit drain fails in bounded time & releases lock.
        pid_file = self.root / "detached.pid"
        holder = self.root / "detached_holder.py"
        holder.write_text(
            "import json, pathlib, subprocess, sys\n"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)'], start_new_session=True)\n"
            "pathlib.Path(sys.argv[1]).write_text(str(p.pid), encoding='utf-8')\n"
            f"print(json.dumps({{'event':'init','conversation_id':'{SESSION}'}}), flush=True)\n",
            encoding="utf-8",
        )
        t0 = time.monotonic()
        with mock.patch.object(to_agy, "POST_EXIT_DRAIN_SECONDS", 0.2), \
                mock.patch.object(to_agy, "CLEANUP_TIMEOUT_SECONDS", 0.2):
            res2 = to_agy.run_agy_review(
                [sys.executable, str(holder), str(pid_file)],
                timeout_seconds=2.0,
                prompt="Review.",
                cwd=str(self.root),
            )
        elapsed = time.monotonic() - t0
        # Clean up the detached sleep helper so it doesn't linger in CI.
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text(encoding="utf-8").strip()), 9)
            except OSError:
                pass
        self.assertLess(elapsed, 1.5, f"detached stdout holder blocked for {elapsed:.2f}s")
        self.assertEqual("other_error", res2.status)
        self.assertFalse(res2.envelope.get("resumable", False))

        # 3) Detached stdout holder executed THROUGH agy_review_gate releases the shared marker lock.
        pid_file2 = self.root / "detached2.pid"
        gate_marker = self.root / "gate-lock-rounds.json"
        with mock.patch.object(to_agy, "POST_EXIT_DRAIN_SECONDS", 0.2), \
                mock.patch.object(to_agy, "CLEANUP_TIMEOUT_SECONDS", 0.2), \
                mock.patch.object(to_agy.shutil, "which", return_value=sys.executable), \
                mock.patch.object(to_agy, "build_agy_command", return_value=[sys.executable, str(holder), str(pid_file2)]), \
                contextlib.redirect_stderr(io.StringIO()):
            gate_res = to_agy.agy_review_gate(
                request_prompt="Review.",
                cd=str(self.root),
                handoff_dir=str(self.root / "handoffs"),
                marker_path=str(gate_marker),
                gate_id="gate-detached-lock",
                artifact_key="art-detached-lock",
                cost_log_path=str(self.root / "cost-lock.jsonl"),
                settings_path=str(self.root / "absent"),
                timeout_seconds=2.0,
                artifact_paths=[str(self.artifact)],
                agy_home=str(self.agy_home),
            )
        if pid_file2.exists():
            try:
                os.kill(int(pid_file2.read_text(encoding="utf-8").strip()), 9)
            except OSError:
                pass
        self.assertEqual("other_error", gate_res.status)
        self.assertFalse(gate_res.envelope.get("resumable", False))
        # Marker lock must be released and immediately acquirable.
        with common.round_cap_guard(str(gate_marker), "art-detached-lock") as decision:
            self.assertTrue(decision.allowed)

        # 4) Selector OSError after Popen MUST terminate the child process so it cannot keep running.
        io_marker = self.root / "survived-io-error"
        io_script = self.root / "io_err_child.py"
        io_script.write_text(
            "import pathlib, sys, time\n"
            "time.sleep(0.5)\n"
            "pathlib.Path(sys.argv[1]).touch()\n",
            encoding="utf-8",
        )
        orig_selector = to_agy.selectors.DefaultSelector

        class FailingSelector:
            def __init__(self):
                self._inner = orig_selector()
            def register(self, *a, **kw):
                return self._inner.register(*a, **kw)
            def unregister(self, *a, **kw):
                return self._inner.unregister(*a, **kw)
            def get_map(self):
                return self._inner.get_map()
            def close(self):
                return self._inner.close()
            def select(self, timeout=None):
                raise OSError("injected selector failure")

        with mock.patch.object(to_agy.selectors, "DefaultSelector", FailingSelector):
            io_res = to_agy.run_agy_review(
                [sys.executable, str(io_script), str(io_marker)],
                timeout_seconds=2.0,
                prompt="Review.",
                cwd=str(self.root),
            )
        self.assertEqual("other_error", io_res.status)
        time.sleep(0.7)
        self.assertFalse(io_marker.exists(), "child survived selector OSError and kept running")

    def test_windows_hung_stdin_writer_fails_closed_instead_of_returning_success(self) -> None:
        class WindowsOS:
            name = "nt"
            def __getattr__(self, name):
                return getattr(os, name)

        unblock_writer = threading.Event()

        class HungStdin:
            def write(self, _data):
                unblock_writer.wait(timeout=3.0)
                return 0
            def close(self):
                pass

        class DonePipe:
            def __init__(self, payload: bytes):
                self._buf = payload
            def read(self, _n=-1):
                out, self._buf = self._buf, b""
                return out
            def close(self):
                pass

        main_proc = mock.MagicMock()
        main_proc.pid = 888888
        main_proc.returncode = 0
        main_proc.stdin = HungStdin()
        main_proc.stdout = DonePipe(_init_line(SESSION) + _result_line(SESSION))
        main_proc.stderr = DonePipe(b"")
        main_proc.wait.return_value = 0

        killer_proc = mock.MagicMock()
        killer_proc.returncode = 0
        killer_proc.wait.return_value = 0

        def fake_popen(argv, **kwargs):
            if argv and argv[0] == "taskkill":
                return killer_proc
            return main_proc

        try:
            with mock.patch.object(to_agy, "os", WindowsOS()), \
                    mock.patch.object(to_agy, "POST_EXIT_DRAIN_SECONDS", 0.1), \
                    mock.patch.object(to_agy, "CLEANUP_TIMEOUT_SECONDS", 0.1), \
                    mock.patch.object(to_agy.subprocess, "Popen", side_effect=fake_popen):
                res = to_agy.run_agy_review(
                    ["agy"],
                    runner=to_agy._run_agy_subprocess,
                    timeout_seconds=1.0,
                    prompt="Review.",
                    cwd=str(self.root),
                )
        finally:
            unblock_writer.set()

        self.assertEqual("other_error", res.status)
        self.assertFalse(res.envelope.get("resumable", False))

    def test_windows_cleanup_uses_devnull_taskkill_and_never_blocks_on_hung_reader(self) -> None:
        class WindowsOS:
            name = "nt"
            def __getattr__(self, name):
                return getattr(os, name)

        unblock_reader = threading.Event()

        class HungPipe:
            def __init__(self):
                self.close_called = False
            def read(self, _n=-1):
                unblock_reader.wait(timeout=3.0)
                return b""
            def close(self):
                self.close_called = True

        class DummyStdin:
            def __init__(self):
                self.written = bytearray()
            def write(self, data):
                self.written.extend(data)
                return len(data)
            def close(self):
                pass

        hung_out = HungPipe()
        hung_err = HungPipe()
        dummy_in = DummyStdin()

        main_proc = mock.MagicMock()
        main_proc.pid = 999999
        main_proc.stdin = dummy_in
        main_proc.stdout = hung_out
        main_proc.stderr = hung_err
        main_proc.wait.side_effect = [subprocess.TimeoutExpired(["agy"], 0.1), 1]

        killer_proc = mock.MagicMock()
        killer_proc.wait.side_effect = [subprocess.TimeoutExpired(["taskkill"], 0.1), 0]
        killer_proc.returncode = 1

        popen_calls: list[tuple[list, dict]] = []

        def fake_popen(argv, **kwargs):
            popen_calls.append((list(argv), dict(kwargs)))
            if argv and argv[0] == "taskkill":
                return killer_proc
            return main_proc

        large_prompt = "X" * (300 * 1024)
        t0 = time.monotonic()
        try:
            with mock.patch.object(to_agy, "os", WindowsOS()), \
                    mock.patch.object(to_agy, "CLEANUP_TIMEOUT_SECONDS", 0.1), \
                    mock.patch.object(to_agy, "POST_EXIT_DRAIN_SECONDS", 0.1), \
                    mock.patch.object(to_agy.subprocess, "Popen", side_effect=fake_popen):
                res = to_agy.run_agy_review(
                    ["agy"],
                    runner=to_agy._run_agy_subprocess,
                    timeout_seconds=0.1,
                    prompt=large_prompt,
                    cwd=str(self.root),
                )
        finally:
            unblock_reader.set()

        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 1.5)
        self.assertEqual("other_error", res.status)
        self.assertFalse(res.envelope.get("resumable", False))
        # Verify taskkill used DEVNULL (no capture_output) and main_proc.kill() ran.
        taskkill_calls = [(a, kw) for a, kw in popen_calls if a and a[0] == "taskkill"]
        self.assertEqual(1, len(taskkill_calls))
        self.assertEqual(subprocess.DEVNULL, taskkill_calls[0][1].get("stdout"))
        self.assertEqual(subprocess.DEVNULL, taskkill_calls[0][1].get("stderr"))
        self.assertTrue(main_proc.kill.called)
        self.assertFalse(hung_out.close_called, "must not call blocking close() on hung Windows reader")

    @unittest.skipIf(os.name == "nt", "POSIX executable fixture")
    def test_source_cli_real_subprocess_timeout_resume_and_relative_path_bin(self) -> None:
        # Put fake `agy` in a relative `./relbin` directory inside skills/cross-agent-review?
        # Even cleaner: run python from self.root/work with PYTHONPATH=SKILL_DIR,
        # and PATH="./relbin:<existing>" so shutil.which("agy") returns a relative path!
        work = self.root / "work"
        relbin = work / "relbin"
        relbin.mkdir(parents=True)
        repo_dir = self.root / "target-repo"
        repo_dir.mkdir()
        art = repo_dir / "code.py"
        art.write_text("print('hi')\n", encoding="utf-8")

        fake_home = self.root / "fake-home"
        fake_home.mkdir()

        executable = relbin / "agy"
        executable.write_text(
            "#!" + sys.executable + "\n"
            "import json, os, pathlib, sys, time\n"
            "args = sys.argv[1:]\n"
            "if '--help' in args:\n"
            "    print('Usage of agy:')\n"
            "    print('  --add-dir  Add dir')\n"
            "    print('  --conversation  Resume by ID')\n"
            "    print('  --dangerously-skip-permissions  Auto approve')\n"
            "    print('  --disable-slash-commands  Disable slash')\n"
            "    print('  --input-format  Input (text, stream-json)')\n"
            "    print('  --model  Model')\n"
            "    print('  --output-format  Output (text, json, stream-json)')\n"
            "    sys.exit(0)\n"
            "line = sys.stdin.readline()\n"
            "msg = json.loads(line)\n"
            "prompt = msg['message']['content']\n"
            "assert 'Review code.py' in prompt\n"
            f"sid = '{SESSION}'\n"
            "db = pathlib.Path.home() / '.gemini' / 'antigravity-cli' / 'conversations' / (sid + '.db')\n"
            "db.parent.mkdir(parents=True, exist_ok=True)\n"
            "if not any(a.startswith('--conversation=') for a in args):\n"
            "    db.write_bytes(b'SQLite format 3\\x00fake')\n"
            "    print(json.dumps({'event': 'init', 'conversation_id': sid}), flush=True)\n"
            "    time.sleep(10)\n"
            "else:\n"
            "    assert f'--conversation={sid}' in args\n"
            "    assert 'SAME unfinished review' in prompt\n"
            "    assert db.is_file() and db.stat().st_size > 0\n"
            "    print(json.dumps({'event': 'init', 'conversation_id': sid}), flush=True)\n"
            "    print(json.dumps({'event': 'result', 'result': {'conversation_id': sid, 'status': 'SUCCESS', 'response': 'APPROVE\\nFixture checked.', 'num_turns': 2, 'usage': {'input_tokens': 5, 'output_tokens': 4}}}), flush=True)\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)

        request = self.root / "request.md"
        request.write_text("Review code.py; do not edit it.", encoding="utf-8")

        base_args = [
            sys.executable, "-B", "-m", "scripts.to_agy",
            "--request-file", str(request),
            "--cd", str(repo_dir),
            "--handoff-dir", str(self.root / "handoffs"),
            "--marker-path", str(self.marker),
            "--gate-id", "gate-cli-1",
            "--artifact-key", "artifact-a",
            "--cost-log", str(self.root / "cost.jsonl"),
            "--output", str(self.root / "review.md"),
            "--settings", str(self.root / "absent-settings"),
            "--artifact-path", "code.py",
            "--timeout-seconds", "0.35",
        ]
        env = {
            **os.environ,
            "HOME": str(fake_home),
            "PYTHONPATH": str(SKILL_DIR),
            "PATH": "./relbin" + os.pathsep + os.environ.get("PATH", ""),
        }
        first = subprocess.run(base_args, cwd=str(work), env=env, capture_output=True, text=True, timeout=10)
        first_payload = json.loads(first.stdout)
        self.assertEqual("timeout", first_payload["status"], first.stderr)
        self.assertEqual(SESSION, first_payload["session_id"])
        self.assertTrue(first_payload["resumable"])

        resume_args = list(base_args)
        resume_args[-1] = "5"
        resume_args.append("--resume")
        second = subprocess.run(resume_args, cwd=str(work), env=env, capture_output=True, text=True, timeout=10)
        second_payload = json.loads(second.stdout)
        self.assertEqual("success", second_payload["status"], second.stderr)
        self.assertEqual({"attempts": 1, "successes": 1}, self.counts())

        third = subprocess.run(resume_args, cwd=str(work), env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual("continuation_rejected", json.loads(third.stdout)["status"])
        self.assertNotIn("review_started", third.stderr)
        self.assertEqual({"attempts": 1, "successes": 1}, self.counts())


if __name__ == "__main__":
    unittest.main()
