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


class CompatibilityTests(unittest.TestCase):
    """Portability guarantees for installers on non-proxy auth and Windows."""

    def test_readiness_falls_back_to_inherited_without_proxy_credentials(self) -> None:
        readiness = codex_to_claude.check_readiness(
            settings_path="/does/not/exist.json", explicit_env={}
        )
        self.assertEqual("inherited", readiness.credential_source)

    def test_inherited_gate_runs_without_injecting_proxy_env(self) -> None:
        def successful_runner(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            child_env = kwargs["env"]
            # No proxy gateway configured and none in the (cleaned) ambient env:
            # the adapter injects nothing and does not force a temp config dir,
            # so the child uses whatever auth the local `claude` already holds.
            self.assertNotIn("ANTHROPIC_BASE_URL", child_env)
            self.assertNotIn("ANTHROPIC_AUTH_TOKEN", child_env)
            self.assertNotIn("CLAUDE_CONFIG_DIR", child_env)
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "APPROVE",
                        "session_id": "inherited-session",
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Clean ambient env so the test is independent of a proxy-configured
            # shell (this suite may itself run behind a gateway).
            with (
                mock.patch.object(codex_to_claude, "claude_available", return_value=True),
                mock.patch.dict(codex_to_claude.os.environ, {"PATH": "/usr/bin"}, clear=True),
            ):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "absent-settings.json"),
                    explicit_env={},
                    runner=successful_runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                )

            self.assertEqual("success", result.status)

    def test_round_cap_guard_serializes_with_portable_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker_path = str(Path(directory) / "rounds.json")
            with codex_to_claude.round_cap_guard(marker_path, "artifact-a") as decision:
                self.assertTrue(decision.allowed)
            self.assertTrue(Path(f"{marker_path}.lock").exists())

    def test_lock_fails_closed_when_no_locking_primitive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "x.lock"
            with open(lock_path, "a+", encoding="utf-8") as handle:
                with (
                    mock.patch.object(codex_to_claude, "_fcntl", None),
                    mock.patch.object(codex_to_claude, "_msvcrt", None),
                ):
                    with self.assertRaises(OSError):
                        codex_to_claude._lock_exclusive(handle)

    def test_windows_lock_retries_only_on_contention(self) -> None:
        import errno as _errno

        class ContendMsvcrt:
            LK_NBLCK = 1

            def __init__(self) -> None:
                self.attempts = 0

            def locking(self, _fd: int, _mode: int, _n: int) -> None:
                self.attempts += 1
                if self.attempts < 3:
                    raise OSError(_errno.EDEADLK, "region locked")

        fake = ContendMsvcrt()
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "x.lock"
            with open(lock_path, "a+", encoding="utf-8") as handle:
                with (
                    mock.patch.object(codex_to_claude, "_fcntl", None),
                    mock.patch.object(codex_to_claude, "_msvcrt", fake),
                    mock.patch.object(codex_to_claude.time, "sleep", lambda *_a: None),
                ):
                    codex_to_claude._lock_exclusive(handle)  # returns after retries
        self.assertEqual(3, fake.attempts)

    def test_windows_lock_reraises_non_contention_error(self) -> None:
        import errno as _errno

        class FailMsvcrt:
            LK_NBLCK = 1

            def locking(self, _fd: int, _mode: int, _n: int) -> None:
                raise OSError(_errno.EACCES, "permission denied")

        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "x.lock"
            with open(lock_path, "a+", encoding="utf-8") as handle:
                with (
                    mock.patch.object(codex_to_claude, "_fcntl", None),
                    mock.patch.object(codex_to_claude, "_msvcrt", FailMsvcrt()),
                    mock.patch.object(codex_to_claude.time, "sleep", lambda *_a: None),
                ):
                    with self.assertRaises(OSError) as ctx:
                        codex_to_claude._lock_exclusive(handle)
        self.assertEqual(_errno.EACCES, ctx.exception.errno)

    def test_max_budget_probe_reads_help_text(self) -> None:
        def with_flag(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "  --max-budget-usd FLOAT\n", "")

        def without_flag(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "  --output-format json\n", "")

        def unreadable(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            raise OSError("help unavailable")

        self.assertIs(
            True,
            codex_to_claude.claude_supports_max_budget(executable="claude", help_runner=with_flag),
        )
        self.assertIs(
            False,
            codex_to_claude.claude_supports_max_budget(
                executable="claude", help_runner=without_flag
            ),
        )
        self.assertIsNone(
            codex_to_claude.claude_supports_max_budget(executable="claude", help_runner=unreadable)
        )

    def test_forward_gate_fails_closed_when_claude_lacks_max_budget(self) -> None:
        def help_without_flag(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "usage: claude -p [--output-format]\n", "")

        def runner_must_not_start(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start when the flag is unsupported")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(codex_to_claude, "claude_available", return_value=True):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-a",
                    artifact_key="artifact-a",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "absent-settings.json"),
                    explicit_env={},
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                    budget_help_runner=help_without_flag,
                )

            self.assertEqual("setup_failure", result.status)
            # No attempt was reserved because we refused before the subprocess.
            self.assertFalse((root / "rounds.json").exists())


class ModelSelectionTests(unittest.TestCase):
    def test_requested_model_validation_is_opaque_and_bounded(self) -> None:
        self.assertIsNone(codex_to_claude.validate_requested_model(None))
        self.assertEqual("sonnet", codex_to_claude.validate_requested_model("sonnet"))
        self.assertEqual(
            "claude-sonnet-4-5-20250929",
            codex_to_claude.validate_requested_model("claude-sonnet-4-5-20250929"),
        )
        self.assertEqual(
            "gpt-5.6-terra", codex_to_claude.validate_requested_model("gpt-5.6-terra")
        )
        for invalid in ("", "-not-a-model", "gpt-5\nmodel", "m" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    codex_to_claude.validate_requested_model(invalid)

    def test_command_builders_preserve_default_or_emit_single_model_token(self) -> None:
        forward_default = codex_to_claude.build_command("review", max_budget_usd=1.0)
        reverse_default = claude_to_codex.build_codex_command("/repo", "/tmp/last.txt")
        self.assertFalse(any(token.startswith("--model") for token in forward_default))
        self.assertFalse(any(token.startswith("--model") for token in reverse_default))

        forward_selected = codex_to_claude.build_command(
            "review", model="sonnet", max_budget_usd=1.0
        )
        reverse_selected = claude_to_codex.build_codex_command(
            "/repo", "/tmp/last.txt", model="gpt-5.6-terra"
        )
        self.assertIn("--model=sonnet", forward_selected)
        self.assertIn("--model=gpt-5.6-terra", reverse_selected)

    def test_invalid_model_fails_before_runner_or_marker(self) -> None:
        def runner_must_not_start(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start for an invalid model")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(codex_to_claude, "claude_available", return_value=True):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="model-validation",
                    artifact_key="model-validation",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                    model="-not-a-model",
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())

    def test_model_preflight_fails_closed_only_when_help_conclusively_lacks_flag(self) -> None:
        def runner_must_not_start(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start for an unsupported CLI flag")

        def help_without_model(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "--max-budget-usd AMOUNT\n", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(codex_to_claude, "claude_available", return_value=True):
                result = codex_to_claude.review_gate(
                    request_prompt="Review the artifact.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="forward-model-help",
                    artifact_key="forward-model-help",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                    budget_help_runner=help_without_model,
                    model="sonnet",
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())

    def test_codex_model_preflight_fails_closed_when_help_lacks_flag(self) -> None:
        def runner_must_not_start(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start for an unsupported CLI flag")

        def help_without_model(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "--sandbox read-only\n", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(claude_to_codex, "codex_available", return_value=True):
                result = claude_to_codex.codex_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="reverse-model-help",
                    artifact_key="reverse-model-help",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                    model_help_runner=help_without_model,
                    model="gpt-5.6-terra",
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())

    def test_requested_model_is_logged_for_each_started_direction(self) -> None:
        def claude_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "APPROVE",
                        "session_id": "forward-model-session",
                    }
                ),
                stderr="",
            )

        def codex_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            Path(argv[argv.index("--output-last-message") + 1]).write_text("APPROVE", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout="\n".join(
                    (
                        json.dumps({"type": "thread.started", "thread_id": "reverse-model-session"}),
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
            with mock.patch.object(codex_to_claude, "claude_available", return_value=True):
                forward = codex_to_claude.review_gate(
                    request_prompt="Review the artifact.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "forward-rounds.json"),
                    gate_id="forward-model-audit",
                    artifact_key="forward-model-audit",
                    cost_log_path=str(root / "forward-cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=claude_runner,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                    model="sonnet",
                )
            with mock.patch.object(claude_to_codex, "codex_available", return_value=True):
                reverse = claude_to_codex.codex_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "reverse-rounds.json"),
                    gate_id="reverse-model-audit",
                    artifact_key="reverse-model-audit",
                    cost_log_path=str(root / "reverse-cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=codex_runner,
                    timeout_seconds=1,
                    model="gpt-5.6-terra",
                )

            self.assertEqual("success", forward.status)
            self.assertEqual("success", reverse.status)
            self.assertEqual(
                "sonnet",
                json.loads((root / "forward-cost.jsonl").read_text(encoding="utf-8"))["requested_model"],
            )
            self.assertEqual(
                "gpt-5.6-terra",
                json.loads((root / "reverse-cost.jsonl").read_text(encoding="utf-8"))["requested_model"],
            )


class CodexProvenanceTests(unittest.TestCase):
    """Tolerant, fail-closed provenance extraction across codex schema drift."""

    def test_accepts_current_probed_schema(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-a"}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 5}}),
            ]
        )
        meta = claude_to_codex._parse_codex_json_stream(stdout)
        self.assertEqual("thread-a", meta["session_id"])
        self.assertEqual({"input_tokens": 3, "output_tokens": 5}, meta["usage"])
        self.assertTrue(claude_to_codex._valid_codex_provenance(meta))

    def test_alias_shapes_do_not_flip_failure_to_success(self) -> None:
        # A hypothetical renamed schema: session event + OpenAI-style token keys.
        # These are NOT the source-verified paths, so provenance must stay
        # invalid (fail closed) and the alias names surface only as drift hints.
        stdout = "\n".join(
            [
                json.dumps({"type": "session.created", "session_id": "sess-b"}),
                json.dumps(
                    {"type": "response.completed", "usage": {"prompt_tokens": 7, "completion_tokens": 9}}
                ),
            ]
        )
        meta = claude_to_codex._parse_codex_json_stream(stdout)
        self.assertIsNone(meta.get("session_id"))
        self.assertIsNone(meta.get("usage"))
        self.assertFalse(claude_to_codex._valid_codex_provenance(meta))
        self.assertIn("session.created:session_id", meta["drift_hints"])
        self.assertIn("response.completed:usage.prompt_tokens", meta["drift_hints"])

    def test_captures_verified_optional_usage_fields(self) -> None:
        # codex rust-v0.144.1 usage struct also carries cached/reasoning tokens.
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-d"}),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 20,
                            "cached_input_tokens": 4,
                            "reasoning_output_tokens": 6,
                        },
                    }
                ),
            ]
        )
        meta = claude_to_codex._parse_codex_json_stream(stdout)
        self.assertEqual(
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "cached_input_tokens": 4,
                "reasoning_output_tokens": 6,
            },
            meta["usage"],
        )
        self.assertTrue(claude_to_codex._valid_codex_provenance(meta))

    def test_bare_id_on_non_session_event_is_not_a_session_id(self) -> None:
        stdout = json.dumps({"type": "item.completed", "id": "item-123"})
        meta = claude_to_codex._parse_codex_json_stream(stdout)
        self.assertIsNone(meta.get("session_id"))

    def test_incomplete_token_pair_is_invalid(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-c"}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 4}}),
            ]
        )
        meta = claude_to_codex._parse_codex_json_stream(stdout)
        self.assertIsNone(meta.get("usage"))
        self.assertFalse(claude_to_codex._valid_codex_provenance(meta))

    def test_provenance_failure_detail_reports_observed_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            last_message = Path(directory) / "last.txt"
            last_message.write_text("APPROVE", encoding="utf-8")

            def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(
                    args=["codex"],
                    returncode=0,
                    stdout=json.dumps({"type": "turn.completed"}),  # no usage, no id
                    stderr="",
                )

            result = claude_to_codex.run_codex_review(
                argv=["codex"],
                last_message_path=str(last_message),
                runner=runner,
                timeout_seconds=1,
                prompt="review",
            )

        self.assertEqual("provenance_failure", result.status)
        self.assertIn("session_id", result.envelope["detail"])
        self.assertIn("usage", result.envelope["detail"])
        self.assertIn("turn.completed", result.envelope["detail"])


if __name__ == "__main__":
    unittest.main()
