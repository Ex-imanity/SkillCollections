"""Regression coverage for local, non-review CLI capability discovery."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"
sys.path.insert(0, str(SKILL_DIR))

try:
    from scripts import runtime_capabilities
except ImportError:
    runtime_capabilities = None


class RuntimeCapabilityTests(unittest.TestCase):
    def test_local_report_distinguishes_supported_and_detected_cli(self) -> None:
        self.assertIsNotNone(runtime_capabilities, "runtime capability report is missing")

        paths = {
            "agy": "/opt/bin/agy",
            "claude": "/opt/bin/claude",
            "gemini": "/opt/bin/gemini",
            "grok": "/opt/bin/grok",
        }

        def which(command: str) -> str | None:
            return paths.get(command)

        def version_runner(
            argv: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            self.assertEqual({"PATH": "/test/bin"}, kwargs["env"])
            if argv[0].endswith("claude"):
                version = "2.1.216 (Claude Code)"
            elif argv[0].endswith("grok"):
                version = "grok 1.0.13 (5e9a58528b76)"
            elif argv[0].endswith("agy"):
                version = "1.5.18"
            else:
                version = "0.17.1"
            return subprocess.CompletedProcess(argv, 0, stdout=version + "\n", stderr="")

        report = runtime_capabilities.discover_local_agents(
            which=which,
            version_runner=version_runner,
            path_env="/test/bin",
        )
        agents = {entry["command"]: entry for entry in report["agents"]}

        self.assertEqual("/opt/bin/agy", agents["agy"]["path"])
        self.assertEqual("1.5.18", agents["agy"]["version"])
        self.assertTrue(agents["agy"]["review_supported"])
        self.assertEqual(["to_agy"], agents["agy"]["review_directions"])
        self.assertEqual("supported", agents["agy"]["status"])
        self.assertEqual("/opt/bin/claude", agents["claude"]["path"])
        self.assertEqual("2.1.216 (Claude Code)", agents["claude"]["version"])
        self.assertTrue(agents["claude"]["review_supported"])
        self.assertEqual(["to_claude"], agents["claude"]["review_directions"])
        self.assertEqual("/opt/bin/grok", agents["grok"]["path"])
        self.assertEqual("grok 1.0.13 (5e9a58528b76)", agents["grok"]["version"])
        self.assertTrue(agents["grok"]["review_supported"])
        self.assertEqual(["to_grok"], agents["grok"]["review_directions"])
        self.assertEqual("supported", agents["grok"]["status"])
        self.assertEqual("/opt/bin/gemini", agents["gemini"]["path"])
        self.assertFalse(agents["gemini"]["review_supported"])
        self.assertEqual("detected_not_supported", agents["gemini"]["status"])
        self.assertEqual("not_found", agents["codex"]["status"])

    def test_windows_agy_version_probe_timeout_is_bounded_without_unbounded_communicate(self) -> None:
        from scripts import to_agy

        class WindowsOS:
            name = "nt"
            def __getattr__(self, name):
                return getattr(os, name)

        unblock_reader = threading.Event()

        class HungPipe:
            def read(self, _n=-1):
                unblock_reader.wait(timeout=3.0)
                return b""
            def close(self):
                pass

        class DoneStdin:
            def close(self):
                pass

        ver_proc = mock.MagicMock()
        ver_proc.pid = 777799
        ver_proc.returncode = 1
        ver_proc.stdin = DoneStdin()
        ver_proc.stdout = HungPipe()
        ver_proc.stderr = HungPipe()
        ver_proc.wait.side_effect = [subprocess.TimeoutExpired(["agy", "--version"], 0.1), 1]
        ver_proc.communicate.side_effect = AssertionError("agy --version probe must not call unbounded communicate()")

        killer_proc = mock.MagicMock()
        killer_proc.returncode = 0
        killer_proc.wait.return_value = 0

        try:
            t0 = time.monotonic()
            with mock.patch.object(to_agy, "os", WindowsOS()), \
                    mock.patch.object(to_agy, "CLEANUP_TIMEOUT_SECONDS", 0.1), \
                    mock.patch.object(
                        to_agy.subprocess,
                        "Popen",
                        side_effect=lambda argv, **kw: killer_proc if argv and argv[0] == "taskkill" else ver_proc,
                    ), \
                    mock.patch.object(
                        runtime_capabilities.subprocess,
                        "Popen",
                        side_effect=lambda argv, **kw: killer_proc if argv and argv[0] == "taskkill" else ver_proc,
                    ):
                report = runtime_capabilities.discover_local_agents(
                    which=lambda cmd: "/opt/bin/agy" if cmd == "agy" else None,
                    path_env="/test/bin",
                )
            elapsed = time.monotonic() - t0
        finally:
            unblock_reader.set()

        agents = {entry["command"]: entry for entry in report["agents"]}
        self.assertTrue(agents["agy"]["status"].startswith("version_probe_failed:"))
        self.assertLess(elapsed, 1.5, f"Windows agy --version probe blocked for {elapsed:.2f}s")
        self.assertFalse(ver_proc.communicate.called)

    def test_agy_version_probe_import_failure_fails_closed_without_unbounded_subprocess_run(self) -> None:
        real_import = __import__

        def block_to_agy(name, globals=None, locals=None, fromlist=(), level=0):
            if "to_agy" in name or (level > 0 and "to_agy" in (name or "")):
                raise ImportError("simulated to_agy import failure")
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch("builtins.__import__", side_effect=block_to_agy), \
                mock.patch.object(
                    runtime_capabilities.subprocess,
                    "run",
                    side_effect=AssertionError("import fallback must not call unbounded subprocess.run"),
                ):
            report = runtime_capabilities.discover_local_agents(
                which=lambda cmd: "/opt/bin/agy" if cmd == "agy" else None,
                path_env="/test/bin",
            )
        agents = {entry["command"]: entry for entry in report["agents"]}
        self.assertEqual("version_probe_failed:OSError", agents["agy"]["status"])


if __name__ == "__main__":
    unittest.main()
