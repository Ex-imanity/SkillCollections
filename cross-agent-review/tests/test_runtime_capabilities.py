"""Regression coverage for local, non-review CLI capability discovery."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

try:
    from scripts import runtime_capabilities
except ImportError:
    runtime_capabilities = None


class RuntimeCapabilityTests(unittest.TestCase):
    def test_local_report_distinguishes_supported_and_detected_cli(self) -> None:
        self.assertIsNotNone(runtime_capabilities, "runtime capability report is missing")

        paths = {
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
            else:
                version = "0.17.1"
            return subprocess.CompletedProcess(argv, 0, stdout=version + "\n", stderr="")

        report = runtime_capabilities.discover_local_agents(
            which=which,
            version_runner=version_runner,
            path_env="/test/bin",
        )
        agents = {entry["command"]: entry for entry in report["agents"]}

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


if __name__ == "__main__":
    unittest.main()
