"""Regression coverage for the P1 review-attempt safety contract."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

from scripts import claude_to_codex, codex_to_claude


class ReviewLimitTests(unittest.TestCase):
    def test_forward_adapter_emits_started_event_after_reserving_attempt(self) -> None:
        observed_before_runner = ""

        def successful_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal observed_before_runner
            observed_before_runner = captured_stderr.getvalue()
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "APPROVE",
                        "session_id": "test-session",
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "test-token",
                        }
                    }
                ),
                encoding="utf-8",
            )
            captured_stderr = io.StringIO()

            with (
                mock.patch.object(codex_to_claude, "claude_available", return_value=True),
                contextlib.redirect_stderr(captured_stderr),
            ):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(settings_path),
                    runner=successful_runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                )

            self.assertEqual("success", result.status)
            self.assertEqual(captured_stderr.getvalue(), observed_before_runner)
            self.assertTrue(captured_stderr.getvalue())
            self.assertEqual(
                {
                    "status": "review_started",
                    "gate_id": "gate-a",
                    "artifact_key": "artifact-a",
                    "attempt": 1,
                    "timeout_seconds": 1,
                },
                json.loads(captured_stderr.getvalue()),
            )

    def test_reverse_adapter_redacts_started_event_before_invoking_runner(self) -> None:
        observed_before_runner = ""

        def successful_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal observed_before_runner
            observed_before_runner = captured_stderr.getvalue()
            output_path = Path(argv[argv.index("--output-last-message") + 1])
            output_path.write_text("APPROVE", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout="\n".join(
                    (
                        json.dumps({"type": "thread.started", "thread_id": "thread-a"}),
                        json.dumps(
                            {
                                "type": "turn.completed",
                                "usage": {"input_tokens": 1, "output_tokens": 1},
                            }
                        ),
                    )
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured_stderr = io.StringIO()

            with (
                mock.patch.object(claude_to_codex, "codex_available", return_value=True),
                contextlib.redirect_stderr(captured_stderr),
            ):
                result = claude_to_codex.codex_review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-sk-abcdefghi",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=successful_runner,
                    timeout_seconds=1,
                )

            self.assertEqual("success", result.status)
            self.assertEqual(captured_stderr.getvalue(), observed_before_runner)
            self.assertTrue(captured_stderr.getvalue())
            self.assertEqual(
                {
                    "status": "review_started",
                    "gate_id": "gate-[REDACTED]",
                    "artifact_key": "artifact-a",
                    "attempt": 1,
                    "timeout_seconds": 1,
                },
                json.loads(captured_stderr.getvalue()),
            )

    def test_user_docs_distinguish_persistent_lock_from_marker_recovery(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        protocol = (SKILL_DIR / "references" / "cross-agent-review-protocol.md").read_text(
            encoding="utf-8"
        )
        readme = (SKILL_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("`<marker-path>.lock` remains after normal completion", skill)
        self.assertIn("not evidence of an active or failed gate", readme)
        self.assertIn("normal persistent flock coordination file", protocol)
        self.assertIn("stderr-only `review_started`", protocol)

    def test_forward_adapter_refuses_to_start_without_a_budget(self) -> None:
        calls = 0

        def runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=1,
                stdout="",
                stderr="should not run",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "test-token",
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = codex_to_claude.review_gate(
                request_prompt="Review the artifact and return a verdict.",
                add_dirs=[str(root)],
                handoff_dir=str(root / "handoffs"),
                marker_path=str(root / "rounds.json"),
                gate_id="gate-a",
                artifact_key="artifact-a",
                cost_log_path=str(root / "cost.jsonl"),
                settings_path=str(settings_path),
                runner=runner,
                timeout_seconds=1,
            )

            self.assertEqual("budget_required", result.status)
            self.assertEqual(0, calls)

    def test_forward_adapter_refuses_to_start_when_claude_is_unavailable(self) -> None:
        calls = 0

        def runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            raise AssertionError("runner must not execute when claude is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "test-token",
                        }
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                codex_to_claude,
                "claude_available",
                return_value=False,
                create=True,
            ):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(settings_path),
                    runner=runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                )

            self.assertEqual("claude_unavailable", result.status)
            self.assertEqual(0, calls)
            self.assertFalse((root / "rounds.json").exists())

    def test_forward_adapter_isolates_and_injects_settings_credentials(self) -> None:
        captured_config_dir: Path | None = None

        def successful_runner(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal captured_config_dir
            child_env = kwargs["env"]
            self.assertIsInstance(child_env, dict)
            self.assertEqual("https://settings.example.invalid", child_env["ANTHROPIC_BASE_URL"])
            self.assertEqual("settings-token", child_env["ANTHROPIC_AUTH_TOKEN"])
            self.assertNotIn("ANTHROPIC_CUSTOM_HEADERS", child_env)
            self.assertNotIn("CLAUDE_CODE_ENTRYPOINT", child_env)
            self.assertNotIn("CLAUDE_AGENT_SDK_VERSION", child_env)
            captured_config_dir = Path(child_env["CLAUDE_CONFIG_DIR"])
            self.assertTrue(captured_config_dir.is_dir())
            self.assertEqual([], list(captured_config_dir.iterdir()))
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "APPROVE",
                        "session_id": "test-session",
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://settings.example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "settings-token",
                        }
                    }
                ),
                encoding="utf-8",
            )

            inherited_identity = {
                "ANTHROPIC_CUSTOM_HEADERS": "Authorization: inherited-secret",
                "CLAUDE_CODE_ENTRYPOINT": "claude-vscode",
                "CLAUDE_AGENT_SDK_VERSION": "0.3.218",
            }
            with (
                mock.patch.object(codex_to_claude, "claude_available", return_value=True),
                mock.patch.dict(codex_to_claude.os.environ, inherited_identity),
            ):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(settings_path),
                    runner=successful_runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                )

            self.assertEqual("success", result.status)
            self.assertIsNotNone(captured_config_dir)
            self.assertFalse(captured_config_dir.exists())

    def test_forward_adapter_derives_gateway_identity_from_the_executed_cli(self) -> None:
        def successful_runner(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            self.assertEqual("/opt/claude", _args[0][0])
            child_env = kwargs["env"]
            self.assertEqual(
                "User-Agent: claude-cli/2.1.216",
                child_env["ANTHROPIC_CUSTOM_HEADERS"],
            )
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "APPROVE",
                        "session_id": "test-session",
                    }
                ),
                stderr="",
            )

        def version_runner(
            argv: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            self.assertEqual(["/opt/claude", "--version"], argv)
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout="2.1.216 (Claude Code)\n",
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://settings.example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "settings-token",
                        }
                    }
                ),
                encoding="utf-8",
            )

            with (
                mock.patch.object(codex_to_claude, "claude_available", return_value=True),
                mock.patch.object(codex_to_claude.shutil, "which", return_value="/opt/claude"),
            ):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(settings_path),
                    runner=successful_runner,
                    version_runner=version_runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                    use_local_claude_cli_identity=True,
                )

            self.assertEqual("success", result.status)

    def test_forward_adapter_rejects_unparseable_local_cli_version_before_reserving_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://settings.example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "settings-token",
                        }
                    }
                ),
                encoding="utf-8",
            )
            runner = mock.Mock()

            def version_runner(
                argv: list[str], **_kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(
                    args=argv,
                    returncode=0,
                    stdout="Claude Code development build\n",
                    stderr="",
                )

            with (
                mock.patch.object(codex_to_claude, "claude_available", return_value=True),
                mock.patch.object(codex_to_claude.shutil, "which", return_value="/opt/claude"),
            ):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(settings_path),
                    runner=runner,
                    version_runner=version_runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                    use_local_claude_cli_identity=True,
                )

            self.assertEqual("setup_failure", result.status)
            runner.assert_not_called()
            self.assertFalse((root / "rounds.json").exists())

    def test_forward_cli_accepts_local_cli_identity_compatibility_flag(self) -> None:
        parser = codex_to_claude._build_parser()
        self.assertIn("--gateway-compat-cli-identity", parser.format_help())

    def test_forward_cli_rejects_caller_supplied_cli_user_agent(self) -> None:
        parser = codex_to_claude._build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--request-file", "request.md",
                    "--handoff-dir", "handoffs",
                    "--marker-path", "rounds.json",
                    "--gate-id", "gate-a",
                    "--artifact-key", "artifact-a",
                    "--cost-log", "cost.jsonl",
                    "--output", "review.md",
                    "--max-budget-usd", "1.0",
                    "--claude-user-agent", "claude-cli/2.1.216",
                ]
            )

    def test_round_cap_rejects_a_caller_supplied_value_above_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker_path = str(Path(directory) / "rounds.json")

            with self.assertRaises(ValueError):
                codex_to_claude.check_round_cap(
                    marker_path,
                    "artifact-a",
                    max_rounds=3,
                )

    def test_cli_does_not_accept_a_max_rounds_override(self) -> None:
        parser = codex_to_claude._build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--request-file", "request.md",
                    "--handoff-dir", "handoffs",
                    "--marker-path", "rounds.json",
                    "--gate-id", "gate-a",
                    "--artifact-key", "artifact-a",
                    "--cost-log", "cost.jsonl",
                    "--output", "review.md",
                    "--max-budget-usd", "1.0",
                    "--max-rounds", "3",
                ]
            )

    def test_third_failed_started_call_is_refused_by_the_attempt_cap(self) -> None:
        def failed_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=1,
                stdout="",
                stderr="provider temporarily unavailable",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "test-token",
                        }
                    }
                ),
                encoding="utf-8",
            )
            arguments = {
                "request_prompt": "Review the artifact and return a verdict.",
                "add_dirs": [str(root)],
                "handoff_dir": str(root / "handoffs"),
                "marker_path": str(root / "rounds.json"),
                "gate_id": "gate-a",
                "artifact_key": "artifact-a",
                "cost_log_path": str(root / "cost.jsonl"),
                "settings_path": str(settings_path),
                "runner": failed_runner,
                "timeout_seconds": 1,
                "max_budget_usd": 1.0,
            }

            with mock.patch.object(
                codex_to_claude,
                "claude_available",
                return_value=True,
                create=True,
            ):
                first = codex_to_claude.review_gate(**arguments)
                second = codex_to_claude.review_gate(**arguments)
                third = codex_to_claude.review_gate(**arguments)

            self.assertEqual("other_error", first.status)
            self.assertEqual("other_error", second.status)
            self.assertEqual("attempt_cap_exceeded", third.status)

    def test_third_successful_review_is_refused_by_the_success_cap(self) -> None:
        calls = 0

        def successful_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "APPROVE",
                        "session_id": "test-session",
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_path = root / "settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "env": {
                            "ANTHROPIC_BASE_URL": "https://example.invalid",
                            "ANTHROPIC_AUTH_TOKEN": "test-token",
                        }
                    }
                ),
                encoding="utf-8",
            )
            arguments = {
                "request_prompt": "Review the artifact and return a verdict.",
                "add_dirs": [str(root)],
                "handoff_dir": str(root / "handoffs"),
                "marker_path": str(root / "rounds.json"),
                "gate_id": "gate-a",
                "artifact_key": "artifact-a",
                "cost_log_path": str(root / "cost.jsonl"),
                "output_path": str(root / "review.md"),
                "settings_path": str(settings_path),
                "runner": successful_runner,
                "timeout_seconds": 1,
                "max_budget_usd": 1.0,
            }

            with mock.patch.object(
                codex_to_claude,
                "claude_available",
                return_value=True,
                create=True,
            ):
                first = codex_to_claude.review_gate(**arguments)
                second = codex_to_claude.review_gate(**arguments)
                third = codex_to_claude.review_gate(**arguments)

            self.assertEqual("success", first.status)
            self.assertEqual("success", second.status)
            self.assertEqual("round_cap_exceeded", third.status)
            self.assertEqual(2, calls)

    def test_reverse_adapter_refuses_the_third_failed_started_call(self) -> None:
        def failed_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["codex"],
                returncode=1,
                stdout="",
                stderr="provider temporarily unavailable",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = {
                "request_prompt": "Review the artifact and return a verdict.",
                "cd": str(root),
                "handoff_dir": str(root / "handoffs"),
                "marker_path": str(root / "rounds.json"),
                "gate_id": "gate-a",
                "artifact_key": "artifact-a",
                "cost_log_path": str(root / "cost.jsonl"),
                "settings_path": str(root / "settings.json"),
                "runner": failed_runner,
                "timeout_seconds": 1,
            }

            first = claude_to_codex.codex_review_gate(**arguments)
            second = claude_to_codex.codex_review_gate(**arguments)
            third = claude_to_codex.codex_review_gate(**arguments)

            self.assertEqual("other_error", first.status)
            self.assertEqual("other_error", second.status)
            self.assertEqual("attempt_cap_exceeded", third.status)

    def test_reverse_cli_does_not_accept_a_max_rounds_override(self) -> None:
        parser = claude_to_codex._build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--request-file", "request.md",
                    "--cd", "repository",
                    "--handoff-dir", "handoffs",
                    "--marker-path", "rounds.json",
                    "--gate-id", "gate-a",
                    "--artifact-key", "artifact-a",
                    "--cost-log", "cost.jsonl",
                    "--output", "review.md",
                    "--max-rounds", "3",
                ]
            )


if __name__ == "__main__":
    unittest.main()
