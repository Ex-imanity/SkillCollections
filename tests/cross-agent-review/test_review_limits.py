"""Regression coverage for the P1 review-attempt safety contract."""

from __future__ import annotations

import contextlib
import os
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"
sys.path.insert(0, str(SKILL_DIR))

from scripts import common, to_agy, to_claude, to_codex, to_grok


def assert_style_review_contract(test: unittest.TestCase, prompt: str) -> None:
    """Check instructions reaching a reviewer, not semantic review quality."""
    for required in (
        "Style consistency:",
        "PASS",
        "NEEDS CHANGES",
        "NOT VERIFIED",
        "NOT APPLICABLE",
        "independently",
        "pre-existing",
        "untracked",
        "do not require a code diff",
    ):
        test.assertIn(required, prompt)


class ReviewLimitTests(unittest.TestCase):
    def test_forward_adapter_emits_started_event_after_reserving_attempt(self) -> None:
        observed_before_runner = ""
        observed_prompt = ""

        def successful_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal observed_before_runner, observed_prompt
            observed_before_runner = captured_stderr.getvalue()
            observed_prompt = _kwargs["input"]
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
                mock.patch.object(to_claude, "claude_available", return_value=True),
                contextlib.redirect_stderr(captured_stderr),
            ):
                request_prompt = "Review the artifact and return a verdict."
                result = to_claude.review_gate(
                    request_prompt=request_prompt,
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
            self.assertEqual("Review the artifact and return a verdict.", request_prompt)
            self.assertIn("Review execution contract", observed_prompt)
            self.assertIn("untrusted evidence", observed_prompt)
            assert_style_review_contract(self, observed_prompt)
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
        observed_prompt = ""

        def successful_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal observed_before_runner, observed_prompt
            observed_before_runner = captured_stderr.getvalue()
            observed_prompt = _kwargs["input"]
            output_path = Path(argv[argv.index("--output-last-message") + 1])
            output_path.write_text("APPROVE", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout="\n".join(
                    (
                        json.dumps({"type": "thread.started", "thread_id": "fde14ccd-66f7-481c-90fe-bd9534d69f59"}),
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
                mock.patch.object(to_codex, "codex_available", return_value=True),
                contextlib.redirect_stderr(captured_stderr),
            ):
                result = to_codex.codex_review_gate(
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
            assert_style_review_contract(self, observed_prompt)
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

    def test_user_docs_require_a_trackable_gate_handle_before_closure(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        protocol = (SKILL_DIR / "references" / "cross-agent-review-protocol.md").read_text(
            encoding="utf-8"
        )
        checklist = (
            SKILL_DIR / "references" / "codex-primary-claudecode-review-loop.md"
        ).read_text(encoding="utf-8")

        for document in (skill, protocol, checklist):
            normalized = " ".join(document.split())
            self.assertIn("trackable runner handle", normalized)
            self.assertIn("terminal tool returning early", normalized)
            self.assertIn("original process is observed to have exited", normalized)
            self.assertIn("prefer a recorded PID whenever the host exposes it", normalized)
            self.assertIn("reattach through the recorded PID", normalized)
            self.assertIn("report the process as unobservable", normalized)
            self.assertIn(
                "validate final stdout JSON first, then the output or handoff", normalized
            )
            self.assertIn("PIDs can be reused", normalized)

        self.assertIn("POSIX", skill)
        self.assertIn("Windows", skill)

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

            result = to_claude.review_gate(
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
                to_claude,
                "claude_available",
                return_value=False,
                create=True,
            ):
                result = to_claude.review_gate(
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
                mock.patch.object(to_claude, "claude_available", return_value=True),
                mock.patch.dict(to_claude.os.environ, inherited_identity),
            ):
                result = to_claude.review_gate(
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
                mock.patch.object(to_claude, "claude_available", return_value=True),
                mock.patch.object(to_claude.shutil, "which", return_value="/opt/claude"),
            ):
                result = to_claude.review_gate(
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
                mock.patch.object(to_claude, "claude_available", return_value=True),
                mock.patch.object(to_claude.shutil, "which", return_value="/opt/claude"),
            ):
                result = to_claude.review_gate(
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
        parser = to_claude._build_parser()
        self.assertIn("--gateway-compat-cli-identity", parser.format_help())

    def test_forward_cli_rejects_caller_supplied_cli_user_agent(self) -> None:
        parser = to_claude._build_parser()

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
                common.check_round_cap(
                    marker_path,
                    "artifact-a",
                    max_rounds=3,
                )

    def test_cli_does_not_accept_a_max_rounds_override(self) -> None:
        parser = to_claude._build_parser()

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
                to_claude,
                "claude_available",
                return_value=True,
                create=True,
            ):
                first = to_claude.review_gate(**arguments)
                second = to_claude.review_gate(**arguments)
                third = to_claude.review_gate(**arguments)

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
                to_claude,
                "claude_available",
                return_value=True,
                create=True,
            ):
                first = to_claude.review_gate(**arguments)
                second = to_claude.review_gate(**arguments)
                third = to_claude.review_gate(**arguments)

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

            with mock.patch.object(to_codex.shutil, "which", return_value="/opt/codex"):
                first = to_codex.codex_review_gate(**arguments)
                second = to_codex.codex_review_gate(**arguments)
                third = to_codex.codex_review_gate(**arguments)

            self.assertEqual("other_error", first.status)
            self.assertEqual("other_error", second.status)
            self.assertEqual("attempt_cap_exceeded", third.status)

    def test_reverse_cli_does_not_accept_a_max_rounds_override(self) -> None:
        parser = to_codex._build_parser()

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
        readiness = to_claude.check_readiness(
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
                mock.patch.object(to_claude, "claude_available", return_value=True),
                mock.patch.dict(to_claude.os.environ, {"PATH": "/usr/bin"}, clear=True),
            ):
                result = to_claude.review_gate(
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
            with common.round_cap_guard(marker_path, "artifact-a") as decision:
                self.assertTrue(decision.allowed)
            self.assertTrue(Path(f"{marker_path}.lock").exists())

    def test_lock_fails_closed_when_no_locking_primitive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "x.lock"
            with open(lock_path, "a+", encoding="utf-8") as handle:
                with (
                    mock.patch.object(common, "_fcntl", None),
                    mock.patch.object(common, "_msvcrt", None),
                ):
                    with self.assertRaises(OSError):
                        common._lock_exclusive(handle)

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
                    mock.patch.object(common, "_fcntl", None),
                    mock.patch.object(common, "_msvcrt", fake),
                    mock.patch.object(common.time, "sleep", lambda *_a: None),
                ):
                    common._lock_exclusive(handle)  # returns after retries
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
                    mock.patch.object(common, "_fcntl", None),
                    mock.patch.object(common, "_msvcrt", FailMsvcrt()),
                    mock.patch.object(common.time, "sleep", lambda *_a: None),
                ):
                    with self.assertRaises(OSError) as ctx:
                        common._lock_exclusive(handle)
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
            to_claude.claude_supports_max_budget(executable="claude", help_runner=with_flag),
        )
        self.assertIs(
            False,
            to_claude.claude_supports_max_budget(
                executable="claude", help_runner=without_flag
            ),
        )
        self.assertIsNone(
            to_claude.claude_supports_max_budget(executable="claude", help_runner=unreadable)
        )

    def test_forward_gate_fails_closed_when_claude_lacks_max_budget(self) -> None:
        def help_without_flag(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "usage: claude -p [--output-format]\n", "")

        def runner_must_not_start(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start when the flag is unsupported")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_claude, "claude_available", return_value=True):
                result = to_claude.review_gate(
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
    def test_file_reference_only_claude_result_is_not_a_valid_review(self) -> None:
        def file_reference_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["claude"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "is_error": False,
                        "api_error_status": None,
                        "result": "I wrote the review to Review/ByClaudeCode/result.md.",
                    }
                ),
                stderr="",
            )

        result = to_claude.run_review(
            ["claude"], runner=file_reference_runner, request_prompt="Review the artifact."
        )

        self.assertEqual("other_error", result.status)
        self.assertIsNone(result.text)

    def test_command_builders_enable_noninteractive_full_access(self) -> None:
        forward = to_claude.build_command("review", max_budget_usd=1.0)
        reverse = to_codex.build_codex_command("/repo", "/tmp/last.txt")
        grok = to_grok.build_grok_command("/tmp/prompt.txt", "/repo")

        self.assertEqual(
            ["--permission-mode", "bypassPermissions"],
            forward[forward.index("--permission-mode") : forward.index("--permission-mode") + 2],
        )
        self.assertIn("--dangerously-skip-permissions", forward)
        self.assertNotIn("--allowedTools", forward)
        self.assertEqual(
            ["--sandbox", "danger-full-access"],
            reverse[reverse.index("--sandbox") : reverse.index("--sandbox") + 2],
        )
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", reverse)
        self.assertIn("--always-approve", grok)
        self.assertEqual(
            ["--prompt-file", "/tmp/prompt.txt"],
            grok[grok.index("--prompt-file") : grok.index("--prompt-file") + 2],
        )
        self.assertEqual(
            ["--output-format", "json"],
            grok[grok.index("--output-format") : grok.index("--output-format") + 2],
        )
        self.assertEqual(["--cwd", "/repo"], grok[grok.index("--cwd") : grok.index("--cwd") + 2])
        self.assertNotIn("-p", grok)

    def test_reviewer_prompt_requires_self_contained_final_verdict(self) -> None:
        prompt = common.build_reviewer_prompt("Review the artifact.")

        self.assertIn("self-contained", prompt)
        self.assertIn("Do not reply only with a file path", prompt)
        self.assertIn("untrusted evidence", prompt)
        self.assertIn("Review the artifact.", prompt)

    def test_requested_model_validation_is_opaque_and_bounded(self) -> None:
        self.assertIsNone(common.validate_requested_model(None))
        self.assertEqual("sonnet", common.validate_requested_model("sonnet"))
        self.assertEqual(
            "claude-sonnet-4-5-20250929",
            common.validate_requested_model("claude-sonnet-4-5-20250929"),
        )
        self.assertEqual(
            "gpt-5.6-terra", common.validate_requested_model("gpt-5.6-terra")
        )
        for invalid in ("", "-not-a-model", "gpt-5\nmodel", "m" * 129):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    common.validate_requested_model(invalid)

    def test_command_builders_preserve_default_or_emit_single_model_token(self) -> None:
        forward_default = to_claude.build_command("review", max_budget_usd=1.0)
        reverse_default = to_codex.build_codex_command("/repo", "/tmp/last.txt")
        grok_default = to_grok.build_grok_command("/tmp/prompt.txt", "/repo")
        self.assertFalse(any(token.startswith("--model") for token in forward_default))
        self.assertFalse(any(token.startswith("--model") for token in reverse_default))
        self.assertFalse(any(token.startswith("--model") for token in grok_default))

        forward_selected = to_claude.build_command(
            "review", model="sonnet", max_budget_usd=1.0
        )
        reverse_selected = to_codex.build_codex_command(
            "/repo", "/tmp/last.txt", model="gpt-5.6-terra"
        )
        grok_selected = to_grok.build_grok_command(
            "/tmp/prompt.txt", "/repo", model="grok-4.5"
        )
        self.assertIn("--model=sonnet", forward_selected)
        self.assertIn("--model=gpt-5.6-terra", reverse_selected)
        self.assertIn("--model=grok-4.5", grok_selected)

    def test_invalid_model_fails_before_runner_or_marker(self) -> None:
        def runner_must_not_start(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start for an invalid model")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_claude, "claude_available", return_value=True):
                result = to_claude.review_gate(
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
            with mock.patch.object(to_claude, "claude_available", return_value=True):
                result = to_claude.review_gate(
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
            with mock.patch.object(to_codex.shutil, "which", return_value="/opt/codex"):
                result = to_codex.codex_review_gate(
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
                        json.dumps({"type": "thread.started", "thread_id": "dc0e2f81-e79f-4fe5-bf9d-03d9a494c7be"}),
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

        def grok_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            prompt_path = Path(argv[argv.index("--prompt-file") + 1])
            self.assertTrue(prompt_path.is_file())
            self.assertIn("Review execution contract", prompt_path.read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout=json.dumps(
                    {
                        "text": "APPROVE",
                        "sessionId": "grok-model-session",
                        "stopReason": "end_turn",
                        "total_cost_usd": 0.01,
                        "usage": {"input_tokens": 2, "output_tokens": 3},
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_claude, "claude_available", return_value=True):
                forward = to_claude.review_gate(
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
            with mock.patch.object(to_codex, "codex_available", return_value=True):
                reverse = to_codex.codex_review_gate(
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
            with mock.patch.object(to_grok, "grok_available", return_value=True):
                grok = to_grok.grok_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "grok-rounds.json"),
                    gate_id="grok-model-audit",
                    artifact_key="grok-model-audit",
                    cost_log_path=str(root / "grok-cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=grok_runner,
                    timeout_seconds=1,
                    model="grok-4.5",
                )

            self.assertEqual("success", forward.status)
            self.assertEqual("success", reverse.status)
            self.assertEqual("success", grok.status)
            self.assertEqual(
                "sonnet",
                json.loads((root / "forward-cost.jsonl").read_text(encoding="utf-8"))["requested_model"],
            )
            self.assertEqual(
                "gpt-5.6-terra",
                json.loads((root / "reverse-cost.jsonl").read_text(encoding="utf-8"))["requested_model"],
            )
            grok_cost = json.loads((root / "grok-cost.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("grok-4.5", grok_cost["requested_model"])
            self.assertEqual("grok", grok_cost["provider"])


class GrokReviewerTests(unittest.TestCase):
    """Any-primary -> Grok reviewer gate: envelope, provenance, caps."""

    def test_grok_adapter_emits_started_event_and_uses_prompt_file(self) -> None:
        observed_before_runner = ""
        observed_prompt = ""
        seen_argv: list[str] = []

        def successful_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal observed_before_runner, observed_prompt, seen_argv
            observed_before_runner = captured_stderr.getvalue()
            seen_argv = list(argv)
            prompt_path = Path(argv[argv.index("--prompt-file") + 1])
            body = prompt_path.read_text(encoding="utf-8")
            observed_prompt = body
            self.assertIn("Review the artifact and return a verdict.", body)
            self.assertIn("Review execution contract", body)
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout=json.dumps(
                    {
                        "text": "APPROVE\n\nLooks solid.",
                        "sessionId": "sess-grok-1",
                        "stopReason": "end_turn",
                        "total_cost_usd": 0.02,
                        "usage": {"input_tokens": 10, "output_tokens": 4},
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captured_stderr = io.StringIO()
            output_path = root / "ByGrok" / "review.md"

            with (
                mock.patch.object(to_grok, "grok_available", return_value=True),
                contextlib.redirect_stderr(captured_stderr),
            ):
                result = to_grok.grok_review_gate(
                    request_prompt="Review the artifact and return a verdict.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-grok",
                    artifact_key="artifact-grok",
                    cost_log_path=str(root / "cost.jsonl"),
                    output_path=str(output_path),
                    settings_path=str(root / "settings.json"),
                    runner=successful_runner,
                    timeout_seconds=1,
                )

            self.assertEqual("success", result.status)
            self.assertEqual("sess-grok-1", result.envelope["session_id"])
            assert_style_review_contract(self, observed_prompt)
            self.assertEqual(0.02, result.envelope["total_cost_usd"])
            self.assertEqual(captured_stderr.getvalue(), observed_before_runner)
            self.assertEqual(
                {
                    "status": "review_started",
                    "gate_id": "gate-grok",
                    "artifact_key": "artifact-grok",
                    "attempt": 1,
                    "timeout_seconds": 1,
                },
                json.loads(captured_stderr.getvalue()),
            )
            self.assertIn("--always-approve", seen_argv)
            self.assertIn("--prompt-file", seen_argv)
            self.assertTrue(output_path.is_file())
            body = output_path.read_text(encoding="utf-8")
            self.assertIn("Reviewer: Grok", body)
            self.assertIn("APPROVE", body)
            # Prompt file is cleaned up after the gate.
            prompt_tokens = seen_argv[seen_argv.index("--prompt-file") + 1]
            self.assertFalse(Path(prompt_tokens).exists())

    def test_grok_adapter_refuses_when_cli_missing(self) -> None:
        calls = 0

        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            raise AssertionError("runner must not execute when grok is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_grok, "grok_available", return_value=False):
                result = to_grok.grok_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-missing",
                    artifact_key="artifact-missing",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner,
                    timeout_seconds=1,
                )

            self.assertEqual("grok_unavailable", result.status)
            self.assertEqual(0, calls)
            self.assertFalse((root / "rounds.json").exists())

    def test_grok_missing_session_id_is_provenance_failure(self) -> None:
        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=0,
                stdout=json.dumps({"text": "APPROVE", "total_cost_usd": 0.01}),
                stderr="",
            )

        result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
        self.assertEqual("provenance_failure", result.status)
        self.assertIn("sessionId", result.envelope["detail"])


    def test_grok_missing_usage_pair_is_provenance_failure(self) -> None:
        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "text": "APPROVE",
                        "sessionId": "sess-no-usage",
                        "stopReason": "end_turn",
                        "total_cost_usd": 0.01,
                    }
                ),
                stderr="",
            )

        result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
        self.assertEqual("provenance_failure", result.status)
        self.assertIn("usage.input_tokens/output_tokens", result.envelope["detail"])

    def test_grok_partial_cost_is_null_not_zero(self) -> None:
        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "text": "APPROVE",
                        "sessionId": "sess-partial",
                        "stopReason": "end_turn",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                        # Non-numeric cost must stay null — never fabricate 0.
                        "total_cost_usd": "unknown",
                    }
                ),
                stderr="",
            )

        result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
        self.assertEqual("success", result.status)
        self.assertIsNone(result.envelope["total_cost_usd"])

    def test_grok_auth_error_envelope_classifies_as_auth_failure(self) -> None:
        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=1,
                stdout=json.dumps(
                    {"type": "error", "message": "Unauthorized: invalid api key"}
                ),
                stderr="",
            )

        result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
        self.assertEqual("auth_failure", result.status)

    def test_grok_third_failed_started_call_is_refused(self) -> None:
        def failing_runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=1,
                stdout=json.dumps({"type": "error", "message": "boom"}),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_grok, "grok_available", return_value=True):
                for _ in range(2):
                    result = to_grok.grok_review_gate(
                        request_prompt="Review the artifact.",
                        cd=str(root),
                        handoff_dir=str(root / "handoffs"),
                        marker_path=str(root / "rounds.json"),
                        gate_id="gate-fail",
                        artifact_key="artifact-fail",
                        cost_log_path=str(root / "cost.jsonl"),
                        settings_path=str(root / "settings.json"),
                        runner=failing_runner,
                        timeout_seconds=1,
                    )
                    self.assertEqual("other_error", result.status)

                third = to_grok.grok_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-fail-3",
                    artifact_key="artifact-fail",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=failing_runner,
                    timeout_seconds=1,
                )

            self.assertEqual("attempt_cap_exceeded", third.status)

    def test_grok_cli_does_not_accept_a_max_rounds_override(self) -> None:
        parser = to_grok._build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--request-file",
                    "r.md",
                    "--cd",
                    ".",
                    "--handoff-dir",
                    "h",
                    "--marker-path",
                    "m.json",
                    "--gate-id",
                    "g",
                    "--artifact-key",
                    "a",
                    "--cost-log",
                    "c.jsonl",
                    "--output",
                    "o.md",
                    "--max-rounds",
                    "9",
                ]
            )

    def test_grok_model_preflight_fails_closed_when_help_lacks_flag(self) -> None:
        def runner_must_not_start(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("reviewer subprocess must not start for an unsupported CLI flag")

        def help_without_model(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "--always-approve\n", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_grok.shutil, "which", return_value="/opt/grok"):
                result = to_grok.grok_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="grok-model-help",
                    artifact_key="grok-model-help",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                    model_help_runner=help_without_model,
                    model="grok-4.5",
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())



    def test_grok_requires_end_turn_stop_reason(self) -> None:
        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "text": "APPROVE",
                        "sessionId": "sess-trunc",
                        "stopReason": "max_tokens",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                        "total_cost_usd": 0.01,
                    }
                ),
                stderr="",
            )

        result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
        self.assertEqual("completion_failure", result.status)
        self.assertIn("end_turn", result.envelope["detail"])
        self.assertIn("max_tokens", result.envelope["detail"])

    def test_grok_parses_json_object_after_leading_banner(self) -> None:
        def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            payload = json.dumps(
                {
                    "text": "APPROVE",
                    "sessionId": "sess-banner",
                    "stopReason": "end_turn",
                    "usage": {"input_tokens": 2, "output_tokens": 2},
                    "total_cost_usd": 0.02,
                }
            )
            return subprocess.CompletedProcess(
                args=["grok"],
                returncode=0,
                stdout=f"warning: noisy banner\n{payload}\n",
                stderr="",
            )

        result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
        self.assertEqual("success", result.status)
        self.assertEqual("sess-banner", result.envelope["session_id"])
        self.assertEqual(0.02, result.envelope["total_cost_usd"])

    def test_grok_nan_or_inf_cost_is_null(self) -> None:
        for raw in (float("nan"), float("inf"), float("-inf")):
            def runner(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(
                    args=["grok"],
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "text": "APPROVE",
                            "sessionId": "sess-cost",
                            "stopReason": "end_turn",
                            "usage": {"input_tokens": 1, "output_tokens": 1},
                            "total_cost_usd": raw,
                        },
                        allow_nan=True,
                    ),
                    stderr="",
                )

            result = to_grok.run_grok_review(["grok"], runner=runner, timeout_seconds=1)
            self.assertEqual("success", result.status)
            self.assertIsNone(result.envelope["total_cost_usd"])

    def test_grok_cleanup_failure_does_not_drop_successful_review(self) -> None:
        def successful_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=argv,
                returncode=0,
                stdout=json.dumps(
                    {
                        "text": "APPROVE",
                        "sessionId": "sess-cleanup",
                        "stopReason": "end_turn",
                        "usage": {"input_tokens": 3, "output_tokens": 3},
                        "total_cost_usd": 0.03,
                    }
                ),
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "review.md"
            real_unlink = os.unlink

            def flaky_unlink(path: str, *args: object, **kwargs: object) -> None:
                if ".grok-prompt-" in str(path):
                    raise OSError("simulated unlink failure")
                return real_unlink(path, *args, **kwargs)

            with (
                mock.patch.object(to_grok, "grok_available", return_value=True),
                mock.patch.object(to_grok.os, "unlink", side_effect=flaky_unlink),
            ):
                result = to_grok.grok_review_gate(
                    request_prompt="Review the artifact.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-cleanup",
                    artifact_key="artifact-cleanup",
                    cost_log_path=str(root / "cost.jsonl"),
                    output_path=str(output_path),
                    settings_path=str(root / "settings.json"),
                    runner=successful_runner,
                    timeout_seconds=1,
                )

            self.assertEqual("success", result.status)
            self.assertIn("cleanup_warning", result.envelope)
            self.assertTrue(output_path.is_file())
            self.assertIn("APPROVE", output_path.read_text(encoding="utf-8"))
            counts = json.loads((root / "rounds.json").read_text(encoding="utf-8"))
            self.assertEqual(1, counts["artifact-cleanup"]["successes"])

    def test_grok_sensitive_values_redact_xai_keys_in_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handoff = common.fail_closed(
                str(root),
                "gate-secret",
                "other_error",
                "token leak xai-secret-value-123456",
                "request mentions xai-secret-value-123456",
                sensitive_values=["xai-secret-value-123456"],
                reviewer="Grok",
            )
            body = Path(handoff).read_text(encoding="utf-8")
            self.assertNotIn("xai-secret-value-123456", body)
            self.assertIn("[REDACTED]", body)
            self.assertIn("Grok adapter", body)
            self.assertNotIn("Codex->ClaudeCode", body)

    def test_fail_closed_names_reviewer_without_legacy_direction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = common.fail_closed(
                str(root),
                "gate-x",
                "other_error",
                "boom",
                "request",
                reviewer="Codex",
            )
            body = Path(path).read_text(encoding="utf-8")
            self.assertIn("Codex adapter", body)
            self.assertNotIn("Codex->ClaudeCode", body)




    def test_grok_setup_error_before_invoke_does_not_burn_attempt(self) -> None:
        def runner_must_not_start(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("runner must not start when prepare fails")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_grok, "grok_available", return_value=True):
                result = to_grok.grok_review_gate(
                    request_prompt="Review the artifact.",
                    cd="",  # fails build_grok_command in prepare
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-preflight",
                    artifact_key="artifact-preflight",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())

    def test_claude_env_resolve_failure_before_reserve_does_not_burn_attempt(self) -> None:
        def runner_must_not_start(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("runner must not start when prepare fails")

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

            def vanishing_resolve(*_a: object, **_k: object) -> dict:
                raise ValueError("configured ANTHROPIC_BASE_URL disappeared before invocation")

            with (
                mock.patch.object(to_claude, "claude_available", return_value=True),
                mock.patch.object(to_claude, "resolve_subprocess_env", side_effect=vanishing_resolve),
            ):
                result = to_claude.review_gate(
                    request_prompt="Review the artifact.",
                    add_dirs=[str(root)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-env",
                    artifact_key="artifact-env",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(settings_path),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                    max_budget_usd=1.0,
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())




    def test_codex_setup_error_before_invoke_does_not_burn_attempt(self) -> None:
        def runner_must_not_start(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
            raise AssertionError("runner must not start when prepare fails")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_codex, "codex_available", return_value=True):
                result = to_codex.codex_review_gate(
                    request_prompt="Review the artifact.",
                    cd="",
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-codex-preflight",
                    artifact_key="artifact-codex-preflight",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "settings.json"),
                    runner=runner_must_not_start,
                    timeout_seconds=1,
                )

            self.assertEqual("setup_failure", result.status)
            self.assertFalse((root / "rounds.json").exists())



class CodexProvenanceTests(unittest.TestCase):
    """Tolerant, fail-closed provenance extraction across codex schema drift."""

    def test_accepts_current_probed_schema(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-a"}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 5}}),
            ]
        )
        meta = to_codex._parse_codex_json_stream(stdout)
        self.assertEqual("thread-a", meta["session_id"])
        self.assertEqual({"input_tokens": 3, "output_tokens": 5}, meta["usage"])
        self.assertTrue(to_codex._valid_codex_provenance(meta))

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
        meta = to_codex._parse_codex_json_stream(stdout)
        self.assertIsNone(meta.get("session_id"))
        self.assertIsNone(meta.get("usage"))
        self.assertFalse(to_codex._valid_codex_provenance(meta))
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
        meta = to_codex._parse_codex_json_stream(stdout)
        self.assertEqual(
            {
                "input_tokens": 10,
                "output_tokens": 20,
                "cached_input_tokens": 4,
                "reasoning_output_tokens": 6,
            },
            meta["usage"],
        )
        self.assertTrue(to_codex._valid_codex_provenance(meta))

    def test_bare_id_on_non_session_event_is_not_a_session_id(self) -> None:
        stdout = json.dumps({"type": "item.completed", "id": "item-123"})
        meta = to_codex._parse_codex_json_stream(stdout)
        self.assertIsNone(meta.get("session_id"))

    def test_incomplete_token_pair_is_invalid(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-c"}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 4}}),
            ]
        )
        meta = to_codex._parse_codex_json_stream(stdout)
        self.assertIsNone(meta.get("usage"))
        self.assertFalse(to_codex._valid_codex_provenance(meta))

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

            result = to_codex.run_codex_review(
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


class CommonHardeningTests(unittest.TestCase):
    def test_fail_closed_redacts_secret_in_gate_id_filename_and_heading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            handoff_dir = Path(directory) / "handoffs"
            gate_id = "gate-AIzaSySecretTokenValue1234567890-custom-secret-xyz"
            written = common.fail_closed(
                str(handoff_dir),
                gate_id,
                "other_error",
                "boom",
                "Review request",
                sensitive_values=["custom-secret-xyz"],
                reviewer="Antigravity",
            )
            self.assertNotIn("AIzaSySecretTokenValue1234567890", written)
            self.assertNotIn("custom-secret-xyz", written)
            body = Path(written).read_text(encoding="utf-8")
            self.assertNotIn("AIzaSySecretTokenValue1234567890", body)
            self.assertNotIn("custom-secret-xyz", body)

            failure = common.gate_failure_result(
                str(handoff_dir),
                gate_id,
                "other_error",
                "boom",
                "Review request",
                sensitive_values=["custom-secret-xyz"],
                reviewer="Antigravity",
            )
            self.assertEqual(written, failure.envelope["handoff_path"])

    def test_fail_closed_respects_explicit_resumable_false_for_timeout(self) -> None:
        self.assertIn("Antigravity", common.RESUMABLE_REVIEWERS)
        with tempfile.TemporaryDirectory() as directory:
            handoff_dir = Path(directory) / "handoffs"
            non_resumable = common.fail_closed(
                str(handoff_dir),
                "gate-non-resumable",
                "timeout",
                "timed out without artifact-path",
                "Review request",
                reviewer="Antigravity",
                resumable=False,
            )
            self.assertNotIn("--resume", Path(non_resumable).read_text(encoding="utf-8"))

            explicit_resumable = common.fail_closed(
                str(handoff_dir),
                "gate-resumable",
                "timeout",
                "timed out",
                "Review request",
                reviewer="Antigravity",
                resumable=True,
            )
            self.assertIn("--resume", Path(explicit_resumable).read_text(encoding="utf-8"))

            default_resumable = common.fail_closed(
                str(handoff_dir),
                "gate-default-resumable",
                "timeout",
                "timed out",
                "Review request",
                reviewer="Antigravity",
            )
            self.assertIn("--resume", Path(default_resumable).read_text(encoding="utf-8"))

    def test_log_cost_redacts_string_fields_and_google_api_key_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "cost.jsonl"
            common.log_cost(
                {"total_cost_usd": None},
                str(log_path),
                "gate-GEMINI_API_KEY=secretval",
                1.23,
                extra={
                    "requested_model": "m-AIzaSyABCDEFGHIJKLMNOPQRSTUV",
                    "usage": {"input_tokens": 5},
                },
                sensitive_values=["secretval"],
            )
            raw = log_path.read_text(encoding="utf-8")
            self.assertNotIn("secretval", raw)
            self.assertNotIn("AIzaSy", raw)
            record = json.loads(raw.strip())
            self.assertEqual({"input_tokens": 5}, record["usage"])
            self.assertEqual(1.23, record["wall_seconds"])

    def test_persist_success_redacts_secret_in_gate_id_before_sanitizing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_path = Path(directory) / "review.md"
            result = common.ReviewResult(
                "success",
                "APPROVE\nChecked.",
                {"session_id": "sess-1", "total_cost_usd": None},
                0,
            )
            common.persist_success(
                str(out_path),
                "gate-GEMINI_API_KEY=secretval-http://localhost:8080/tok",
                result,
                sensitive_values=["tok/val+secret"],
                reviewer="Antigravity",
            )
            body = out_path.read_text(encoding="utf-8")
            self.assertNotIn("secretval", body)
            self.assertNotIn("localhost", body)

            out_path2 = Path(directory) / "review2.md"
            common.persist_success(
                str(out_path2),
                "gate-tok/val+secret",
                result,
                sensitive_values=["tok/val+secret"],
                reviewer="Antigravity",
            )
            body2 = out_path2.read_text(encoding="utf-8")
            self.assertNotIn("tok-val-secret", body2)
            self.assertNotIn("tok/val+secret", body2)

    def test_claude_and_grok_main_use_redacted_handoff_path_from_envelope(self) -> None:
        secret = "AIzaSySecretTokenValue1234567890"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = root / "req.md"
            req.write_text("Review this.", encoding="utf-8")
            handoff_dir = root / "handoffs"

            # to_grok.main()
            grok_out = io.StringIO()
            with mock.patch.object(to_grok, "grok_available", return_value=False), \
                    contextlib.redirect_stdout(grok_out):
                rc_g = to_grok.main([
                    "--request-file", str(req),
                    "--cd", str(root),
                    "--handoff-dir", str(handoff_dir),
                    "--marker-path", str(root / "rounds-g.json"),
                    "--gate-id", f"gate-{secret}",
                    "--artifact-key", "art-g",
                    "--cost-log", str(root / "cost-g.jsonl"),
                    "--output", str(root / "out-g.md"),
                    "--settings", str(root / "absent"),
                ])
            self.assertEqual(1, rc_g)
            grok_payload = json.loads(grok_out.getvalue())
            self.assertNotIn(secret, grok_out.getvalue())
            self.assertTrue(Path(grok_payload["handoff_path"]).is_file())

            # to_claude.main()
            claude_out = io.StringIO()
            with mock.patch.object(to_claude, "claude_available", return_value=False), \
                    contextlib.redirect_stdout(claude_out):
                rc_c = to_claude.main([
                    "--request-file", str(req),
                    "--add-dir", str(root),
                    "--handoff-dir", str(handoff_dir),
                    "--marker-path", str(root / "rounds-c.json"),
                    "--gate-id", f"gate-{secret}",
                    "--artifact-key", "art-c",
                    "--cost-log", str(root / "cost-c.jsonl"),
                    "--output", str(root / "out-c.md"),
                    "--settings", str(root / "absent"),
                    "--max-budget-usd", "1",
                ])
            self.assertEqual(1, rc_c)
            claude_payload = json.loads(claude_out.getvalue())
            self.assertNotIn(secret, claude_out.getvalue())
            self.assertTrue(Path(claude_payload["handoff_path"]).is_file())

            # to_codex.main()
            codex_out = io.StringIO()
            with mock.patch.object(to_codex, "codex_available", return_value=False), \
                    contextlib.redirect_stdout(codex_out):
                rc_x = to_codex.main([
                    "--request-file", str(req),
                    "--cd", str(root),
                    "--handoff-dir", str(handoff_dir),
                    "--marker-path", str(root / "rounds-x.json"),
                    "--gate-id", f"gate-{secret}",
                    "--artifact-key", "art-x",
                    "--cost-log", str(root / "cost-x.jsonl"),
                    "--output", str(root / "out-x.md"),
                    "--settings", str(root / "absent"),
                ])
            self.assertEqual(1, rc_x)
            codex_payload = json.loads(codex_out.getvalue())
            self.assertNotIn(secret, codex_out.getvalue())
            self.assertTrue(Path(codex_payload["handoff_path"]).is_file())

            # Distinct secrets sharing the same gate prefix must produce distinct redacted handoff files.
            p1 = common.fail_closed(
                str(handoff_dir), "gate-secret-alpha", "other_error", "err1", "req",
                sensitive_values=["secret-alpha", "secret-beta"], reviewer="Antigravity",
            )
            p2 = common.fail_closed(
                str(handoff_dir), "gate-secret-beta", "other_error", "err2", "req",
                sensitive_values=["secret-alpha", "secret-beta"], reviewer="Antigravity",
            )
            self.assertNotEqual(p1, p2)
            self.assertNotIn("secret-alpha", p1)
            self.assertNotIn("secret-beta", p2)
            self.assertTrue(Path(p1).is_file())
            self.assertTrue(Path(p2).is_file())

    def test_log_cost_normalizes_non_finite_and_secret_total_cost_usd_to_null(self) -> None:
        secret = "sk-ant-secret-cost-value-999"
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "cost.jsonl"
            for bad_cost in (secret, float("nan"), float("inf"), float("-inf"), True, {"nested": secret}):
                common.log_cost(
                    {"total_cost_usd": bad_cost},
                    str(log_path),
                    gate_id="gate-bad-cost",
                    wall_seconds=1.25,
                    extra={"provider": "claude", "note": f"ok {secret}"},
                    sensitive_values=[secret],
                )
            raw = log_path.read_text(encoding="utf-8")
            self.assertNotIn(secret, raw)
            self.assertNotIn("NaN", raw)
            self.assertNotIn("Infinity", raw)
            lines = raw.splitlines()
            self.assertEqual(6, len(lines))
            for line in lines:
                rec = json.loads(line)
                self.assertIsNone(rec["total_cost_usd"])

    def test_huge_int_cost_completes_full_gate_and_persist_success_normalizes_cost(self) -> None:
        huge_cost = 10**309
        multiline_secret = "X-Auth: secret-line-1\nX-Token: secret-line-2"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # 1) Full gate with huge JSON integer (10**309) must NOT raise OverflowError.
            out_huge = root / "huge-review.md"
            cost_huge = root / "huge-cost.jsonl"
            marker_huge = root / "huge-rounds.json"
            from scripts.continuation import ReviewContinuation

            cont_huge = ReviewContinuation(
                resume=False,
                cwd=str(root),
                artifact_paths=[],
                session_store=str(root / "store"),
            )
            with contextlib.redirect_stderr(io.StringIO()):
                res = common.run_review_gate(
                    request_prompt="Review.",
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(marker_huge),
                    gate_id="gate-huge-int",
                    artifact_key="art-huge-int",
                    cost_log_path=str(cost_huge),
                    sensitive_values=[],
                    reviewer="ClaudeCode",
                    invoke=lambda _state: common.ReviewResult(
                        "success",
                        "APPROVE\nChecked.",
                        {"session_id": cont_huge.session_id, "total_cost_usd": huge_cost},
                        0,
                    ),
                    output_path=str(out_huge),
                    timeout_seconds=10,
                    continuation=cont_huge,
                )
            self.assertEqual("success", res.status)
            self.assertTrue(out_huge.is_file())
            self.assertEqual(huge_cost, json.loads(cost_huge.read_text(encoding="utf-8").splitlines()[0])["total_cost_usd"])
            state = json.loads(Path(res.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
            self.assertEqual("completed", state["state"])

            # 2) persist_success must normalize NaN and dict-with-multiline-secret total_cost_usd to None.
            out_nan = root / "nan-review.md"
            common.persist_success(
                str(out_nan),
                "gate-nan",
                common.ReviewResult("success", "APPROVE", {"session_id": "sess-1", "total_cost_usd": float("nan")}, 0),
                sensitive_values=[multiline_secret],
                reviewer="ClaudeCode",
            )
            nan_md = out_nan.read_text(encoding="utf-8")
            self.assertIn("Reported cost USD: `None`", nan_md)
            self.assertNotIn("`nan`", nan_md.lower())

            out_dict = root / "dict-review.md"
            common.persist_success(
                str(out_dict),
                "gate-dict",
                common.ReviewResult(
                    "success",
                    "APPROVE",
                    {"session_id": "sess-2", "total_cost_usd": {"hdr": multiline_secret}},
                    0,
                ),
                sensitive_values=[multiline_secret],
                reviewer="ClaudeCode",
            )
            dict_md = out_dict.read_text(encoding="utf-8")
            self.assertIn("Reported cost USD: `None`", dict_md)
            self.assertNotIn("secret-line-1", dict_md)
            self.assertNotIn("secret-line-2", dict_md)


_AGY_VALID_HELP = """Usage of agy:
  --add-dir                       Add a directory to the workspace (repeatable)
  --conversation                  Resume a previous conversation by ID
  --dangerously-skip-permissions  Auto-approve all tool permission requests
  --disable-slash-commands        Disable slash command expansion
  --input-format                  Input format for print mode (text, stream-json)
  --model                         Model for the current CLI session
  --output-format                 Output format for print mode (text, json, stream-json)
"""
_AGY_UUID = "f7965130-c060-4181-abcf-4fadb1054401"
_AGY_OTHER_UUID = "11111111-2222-4333-8444-555555555555"


def _agy_stream_bytes(
    *,
    conv_id: str = _AGY_UUID,
    result_conv_id: str | None = None,
    status: str = "SUCCESS",
    response: str = "APPROVE\nVerified against source.",
    error: str | None = None,
    usage: object = None,
) -> bytes:
    if usage is None:
        usage = {
            "input_tokens": 100,
            "output_tokens": 25,
            "thinking_tokens": 10,
            "cache_read_tokens": 50,
            "total_tokens": 125,
        }
    result_obj = {
        "conversation_id": conv_id if result_conv_id is None else result_conv_id,
        "status": status,
        "response": response,
        "num_turns": 1,
        "usage": usage,
    }
    if error is not None:
        result_obj["error"] = error
    lines = [
        json.dumps({"event": "init", "conversation_id": conv_id, "init": {"permission_mode": "always-proceed"}}),
        json.dumps({"event": "result", "result": result_obj}),
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


class AgyAdapterTests(unittest.TestCase):
    def test_build_agy_command_and_encode_prompt(self) -> None:
        argv = to_agy.build_agy_command(
            agy_executable="/opt/bin/agy",
            add_dirs=["/repo/fe", "/repo/be"],
            model="gemini-4-neon-high",
        )
        self.assertEqual("/opt/bin/agy", argv[0])
        self.assertIn("--input-format", argv)
        self.assertEqual("stream-json", argv[argv.index("--input-format") + 1])
        self.assertIn("--output-format", argv)
        self.assertEqual("stream-json", argv[argv.index("--output-format") + 1])
        self.assertIn("--dangerously-skip-permissions", argv)
        self.assertIn("--disable-slash-commands", argv)
        self.assertIn("--model=gemini-4-neon-high", argv)
        self.assertEqual(["/repo/fe", "/repo/be"], [argv[i + 1] for i, tok in enumerate(argv) if tok == "--add-dir"])
        for forbidden in ("--continue", "-c", "--print-timeout", "--effort", "--agent", "--mode", "--sandbox"):
            self.assertNotIn(forbidden, argv)

        resumed = to_agy.build_agy_command(
            agy_executable="/opt/bin/agy",
            session_id=_AGY_UUID,
            resume=True,
        )
        self.assertIn(f"--conversation={_AGY_UUID}", resumed)

        with self.assertRaises(ValueError):
            to_agy.build_agy_command(model="--bad-flag")
        with self.assertRaises(ValueError):
            to_agy.build_agy_command(session_id="not-a-uuid", resume=True)
        with self.assertRaises(ValueError):
            to_agy.build_agy_command(resume=True)

        encoded = to_agy.encode_agy_prompt("Review line1\nline2")
        self.assertIsInstance(encoded, bytes)
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(1, encoded.count(b"\n"))
        payload = json.loads(encoded.decode("utf-8"))
        self.assertEqual({"event": "user", "message": {"content": "Review line1\nline2"}}, payload)

    def test_agy_help_preflight_requires_usage_and_both_stream_json_directions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extra = root / "extra"
            extra.mkdir()

            seen_calls: list[tuple[list[str], dict]] = []

            def make_help_runner(rc: int, stdout: str, stderr: str = "", exc: Exception | None = None):
                def _runner(argv, **kwargs):
                    seen_calls.append((list(argv), dict(kwargs)))
                    if exc is not None:
                        raise exc
                    return subprocess.CompletedProcess(argv, rc, stdout, stderr)
                return _runner

            def ok_runner(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, _agy_stream_bytes(), b"")

            def must_not_run(*_a, **_k):
                raise AssertionError("reviewer subprocess must not run after preflight refusal")

            # Valid help passes and pins absolute executable + explicit timeout=5.
            with mock.patch.object(to_agy.shutil, "which", return_value="./bin/agy"), \
                    contextlib.redirect_stderr(io.StringIO()):
                res = to_agy.agy_review_gate(
                    request_prompt="Review this.",
                    cd=str(root),
                    add_dirs=[str(extra)],
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-help-ok",
                    artifact_key="art-help-ok",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "absent"),
                    runner=ok_runner,
                    help_runner=make_help_runner(0, _AGY_VALID_HELP),
                    model="gemini-4-neon-high",
                    timeout_seconds=10,
                )
            self.assertEqual("success", res.status)
            self.assertEqual(os.path.abspath("./bin/agy"), seen_calls[-1][0][0])
            self.assertEqual(5, seen_calls[-1][1]["timeout"])

            # Conclusive missing capabilities fail closed with zero attempt reservation.
            missing_variants = [
                (_AGY_VALID_HELP.replace("--conversation", "--other"), None, []),
                (_AGY_VALID_HELP.replace("--disable-slash-commands", "--other"), None, []),
                (_AGY_VALID_HELP.replace("--model", "--other"), "gemini-4-neon-high", []),
                (_AGY_VALID_HELP.replace("--add-dir", "--other"), None, [str(extra)]),
                (_AGY_VALID_HELP.replace("(text, stream-json)", "(text)"), None, []),
            ]
            for idx, (help_text, model_arg, dirs_arg) in enumerate(missing_variants):
                marker = root / f"rounds-missing-{idx}.json"
                with self.subTest(idx=idx), \
                        mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"):
                    r = to_agy.agy_review_gate(
                        request_prompt="Review.",
                        cd=str(root),
                        add_dirs=dirs_arg,
                        handoff_dir=str(root / "handoffs"),
                        marker_path=str(marker),
                        gate_id=f"gate-miss-{idx}",
                        artifact_key=f"art-miss-{idx}",
                        cost_log_path=str(root / "cost.jsonl"),
                        settings_path=str(root / "absent"),
                        runner=must_not_run,
                        help_runner=make_help_runner(0, help_text),
                        model=model_arg,
                        timeout_seconds=10,
                    )
                    self.assertEqual("setup_failure", r.status)
                    self.assertFalse(marker.exists())

            # Inconclusive probes (exit-0 error page, non-zero echoing flags, empty, TimeoutExpired) do not block.
            inconclusive = [
                make_help_runner(0, "Error: daemon unreachable"),
                make_help_runner(1, "error: unknown flag --help\n--conversation --input-format stream-json"),
                make_help_runner(0, ""),
                make_help_runner(0, "", exc=subprocess.TimeoutExpired(["agy", "--help"], 5)),
            ]
            for idx, hrunner in enumerate(inconclusive):
                with self.subTest(inconclusive=idx), \
                        mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                        contextlib.redirect_stderr(io.StringIO()):
                    r = to_agy.agy_review_gate(
                        request_prompt="Review.",
                        cd=str(root),
                        handoff_dir=str(root / "handoffs"),
                        marker_path=str(root / f"rounds-inc-{idx}.json"),
                        gate_id=f"gate-inc-{idx}",
                        artifact_key=f"art-inc-{idx}",
                        cost_log_path=str(root / "cost.jsonl"),
                        settings_path=str(root / "absent"),
                        runner=ok_runner,
                        help_runner=hrunner,
                        timeout_seconds=10,
                    )
                    self.assertEqual("success", r.status)

    def test_agy_stream_parser_strict_lf_framing_and_malformed_fields(self) -> None:
        # Unescaped U+2028 / U+2029 inside JSON string must NOT be split by LF framing.
        raw_unicode = (
            '{"event":"init","conversation_id":"' + _AGY_UUID + '"}\n'
            '{"event":"result","result":{"conversation_id":"' + _AGY_UUID + '",'
            '"status":"SUCCESS","response":"APPROVE\u2028line\u2029ok",'
            '"usage":{"input_tokens":10,"output_tokens":5}}}\n'
        ).encode("utf-8")
        res = to_agy.run_agy_review(
            ["agy"],
            runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, raw_unicode, b""),
            prompt="Review.",
        )
        self.assertEqual("success", res.status)
        self.assertIn("\u2028", res.text)
        self.assertIn("\u2029", res.text)

        # Provenance failures on exit 0.
        bad_streams = [
            # duplicate init
            (json.dumps({"event": "init", "conversation_id": _AGY_UUID}) + "\n"
             + json.dumps({"event": "init", "conversation_id": _AGY_UUID}) + "\n"
             + json.dumps({"event": "result", "result": {"conversation_id": _AGY_UUID, "status": "SUCCESS", "response": "APPROVE", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n").encode(),
            # duplicate result
            _agy_stream_bytes() + (json.dumps({"event": "result", "result": {"conversation_id": _AGY_UUID, "status": "SUCCESS", "response": "APPROVE", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n").encode(),
            # result before init
            (json.dumps({"event": "result", "result": {"conversation_id": _AGY_UUID, "status": "SUCCESS", "response": "APPROVE", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n"
             + json.dumps({"event": "init", "conversation_id": _AGY_UUID}) + "\n").encode(),
            # conversation_id mismatch
            _agy_stream_bytes(conv_id=_AGY_UUID, result_conv_id=_AGY_OTHER_UUID),
            # bool in token usage
            _agy_stream_bytes(usage={"input_tokens": True, "output_tokens": 5}),
            # negative tokens
            _agy_stream_bytes(usage={"input_tokens": -1, "output_tokens": 5}),
            # corrupt trailing line on exit 0
            _agy_stream_bytes() + b'{"event":"step_update",',
        ]
        for idx, stream_bytes in enumerate(bad_streams):
            with self.subTest(bad_stream=idx):
                r = to_agy.run_agy_review(
                    ["agy"],
                    runner=lambda argv, _s=stream_bytes, **kw: subprocess.CompletedProcess(argv, 0, _s, b""),
                    prompt="Review.",
                )
                self.assertEqual("provenance_failure", r.status)

        # Malformed field types & deeply nested JSON must never raise TypeError/RecursionError
        # and must preserve cost logging and handoff persistence.
        malformed_streams = [
            b'{"event":"init","conversation_id":123}\n{"event":"result","result":[]}\n',
            b'{"event":"init","conversation_id":"' + _AGY_UUID.encode() + b'"}\n{"event":"result","result":{"conversation_id":"' + _AGY_UUID.encode() + b'","status":"SUCCESS","response":"APPROVE","usage":"bad"}}\n',
            # Non-string event inserted between valid init and result on exit 0 -> provenance_failure
            (json.dumps({"event": "init", "conversation_id": _AGY_UUID}) + "\n"
             + '{"event":[]}\n'
             + json.dumps({"event": "result", "result": {"conversation_id": _AGY_UUID, "status": "SUCCESS", "response": "APPROVE", "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n").encode(),
            # Deeply nested JSON causing RecursionError in json.loads -> must still log cost + handoff
            b"[" * 2000 + b"]" * 2000 + b"\n",
            # Valid init + valid result missing trailing LF on exit 0 -> MUST NOT commit success
            _agy_stream_bytes().rstrip(b"\n"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for idx, stream_bytes in enumerate(malformed_streams):
                cost_log = root / f"cost-{idx}.jsonl"
                with mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                        contextlib.redirect_stderr(io.StringIO()):
                    r = to_agy.agy_review_gate(
                        request_prompt="Review.",
                        cd=str(root),
                        handoff_dir=str(root / "handoffs"),
                        marker_path=str(root / f"rounds-{idx}.json"),
                        gate_id=f"gate-mal-{idx}",
                        artifact_key=f"art-mal-{idx}",
                        cost_log_path=str(cost_log),
                        settings_path=str(root / "absent"),
                        runner=lambda argv, _s=stream_bytes, **kw: subprocess.CompletedProcess(argv, 0, _s, b""),
                        timeout_seconds=10,
                    )
                self.assertIn(r.status, {"provenance_failure", "other_error"})
                self.assertTrue(cost_log.is_file())
                self.assertEqual(1, len(cost_log.read_text(encoding="utf-8").splitlines()))
                self.assertTrue(Path(r.envelope["handoff_path"]).is_file())
                state = json.loads(Path(r.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
                self.assertEqual("failed", state["state"])

    def test_agy_classification_auth_vs_completion_vs_verdict(self) -> None:
        captured_prompts: list[str] = []

        def success_runner(argv, **kwargs):
            payload = json.loads(kwargs["input"].decode("utf-8"))
            captured_prompts.append(payload["message"]["content"])
            return subprocess.CompletedProcess(
                argv, 0,
                _agy_stream_bytes(response="APPROVE\nChecked HTTP 401, 403, forbidden, authentication paths."),
                b"",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                    contextlib.redirect_stderr(io.StringIO()):
                ok = to_agy.agy_review_gate(
                    request_prompt="Review auth code.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-ok",
                    artifact_key="art-ok",
                    cost_log_path=str(root / "cost.jsonl"),
                    output_path=str(root / "review.md"),
                    settings_path=str(root / "absent"),
                    runner=success_runner,
                    timeout_seconds=10,
                )
            self.assertEqual("success", ok.status)
            self.assertIsNone(ok.envelope["total_cost_usd"])
            assert_style_review_contract(self, captured_prompts[0])

        # Missing verdict -> other_error
        no_verdict = to_agy.run_agy_review(
            ["agy"],
            runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, _agy_stream_bytes(response="Written to file."), b""),
            prompt="Review.",
        )
        self.assertEqual("other_error", no_verdict.status)

        # Incomplete statuses -> completion_failure
        for status_name in ("CANCELED", "INTERRUPTED", "WAITING", "RUNNING"):
            with self.subTest(status_name=status_name):
                r = to_agy.run_agy_review(
                    ["agy"],
                    runner=lambda argv, _st=status_name, **kw: subprocess.CompletedProcess(
                        argv, 0, _agy_stream_bytes(status=_st, response="APPROVE"), b""
                    ),
                    prompt="Review.",
                )
                self.assertEqual("completion_failure", r.status)

        # Auth failures on error/stderr
        for err_text in ("authentication required: please login", "invalid_api_key provided"):
            r = to_agy.run_agy_review(
                ["agy"],
                runner=lambda argv, _e=err_text, **kw: subprocess.CompletedProcess(
                    argv, 1, _agy_stream_bytes(status="ERROR", response="", error=_e), b""
                ),
                prompt="Review.",
            )
            self.assertEqual("auth_failure", r.status)

        # Bare 403 in non-auth error message must NOT misclassify as auth_failure
        non_auth = to_agy.run_agy_review(
            ["agy"],
            runner=lambda argv, **kw: subprocess.CompletedProcess(
                argv, 1, _agy_stream_bytes(status="ERROR", response="", error="line 403 syntax error"), b""
            ),
            prompt="Review.",
        )
        self.assertEqual("other_error", non_auth.status)

    def test_agy_end_to_end_redaction_and_relative_which_resolution(self) -> None:
        gemini_secret = "AIzaSyRealSecretKeyValue1234567890"
        google_secret = "goog-secret-abc-999"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = root / "request.md"
            req.write_text(f"Review code; never leak {google_secret}", encoding="utf-8")
            out_file = root / "review.md"
            cost_log = root / "cost.jsonl"
            handoff_dir = root / "handoffs"
            seen_argv: list[list[str]] = []

            def fail_runner(argv, **kwargs):
                seen_argv.append(list(argv))
                return subprocess.CompletedProcess(
                    argv, 1,
                    _agy_stream_bytes(status="ERROR", response="", error=f"boom {gemini_secret} {google_secret}"),
                    f"stderr {gemini_secret}".encode("utf-8"),
                )

            env_patch = {
                "GEMINI_API_KEY": gemini_secret,
                "GOOGLE_API_KEY": google_secret,
            }
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            with mock.patch.dict(os.environ, env_patch), \
                    mock.patch.object(to_agy.shutil, "which", return_value="./bin/agy"), \
                    mock.patch.object(to_agy, "agy_supported_flags", return_value=None), \
                    mock.patch.object(to_agy, "_run_agy_subprocess", side_effect=fail_runner), \
                    contextlib.redirect_stdout(stdout_buf), \
                    contextlib.redirect_stderr(stderr_buf):
                rc = to_agy.main([
                    "--request-file", str(req),
                    "--cd", str(root),
                    "--handoff-dir", str(handoff_dir),
                    "--marker-path", str(root / "rounds.json"),
                    "--gate-id", f"gate-{gemini_secret}-{google_secret}",
                    "--artifact-key", "art-redact",
                    "--cost-log", str(cost_log),
                    "--output", str(out_file),
                    "--settings", str(root / "absent"),
                    "--timeout-seconds", "10",
                ])
            self.assertEqual(1, rc)
            # Pinned absolute executable used for runner even though which returned relative path.
            self.assertTrue(os.path.isabs(seen_argv[-1][0]))
            self.assertEqual(os.path.abspath("./bin/agy"), seen_argv[-1][0])

            stdout_text = stdout_buf.getvalue()
            stderr_text = stderr_buf.getvalue()
            cost_text = cost_log.read_text(encoding="utf-8")
            payload = json.loads(stdout_text)
            handoff_path = payload["handoff_path"]
            self.assertIsNotNone(handoff_path)
            self.assertTrue(Path(handoff_path).is_file())
            handoff_text = Path(handoff_path).read_text(encoding="utf-8")

            for secret in (gemini_secret, google_secret):
                self.assertNotIn(secret, stdout_text)
                self.assertNotIn(secret, stderr_text)
                self.assertNotIn(secret, cost_text)
                self.assertNotIn(secret, handoff_path)
                self.assertNotIn(secret, handoff_text)

    def test_agy_success_path_redacts_secrets_across_output_cost_stderr_and_stdout(self) -> None:
        gemini_secret = "AIzaSyRealSecretKeyValue1234567890"
        google_secret = "goog/secret+abc=999"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = root / "request.md"
            req.write_text("Review code cleanly.", encoding="utf-8")
            out_file = root / "review.md"
            cost_log = root / "cost.jsonl"
            handoff_dir = root / "handoffs"

            def ok_runner(argv, **kwargs):
                if "--help" in argv:
                    return subprocess.CompletedProcess(argv, 0, _AGY_VALID_HELP, "")
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    _agy_stream_bytes(
                        response=f"APPROVE\nChecked config {gemini_secret} and {google_secret}."
                    ),
                    b"",
                )

            env_patch = {
                "GEMINI_API_KEY": gemini_secret,
                "GOOGLE_API_KEY": google_secret,
            }
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            with mock.patch.dict(os.environ, env_patch), \
                    mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                    mock.patch.object(to_agy, "agy_supported_flags", return_value=None), \
                    mock.patch.object(to_agy, "_run_agy_subprocess", side_effect=ok_runner), \
                    contextlib.redirect_stdout(stdout_buf), \
                    contextlib.redirect_stderr(stderr_buf):
                rc = to_agy.main([
                    "--request-file", str(req),
                    "--cd", str(root),
                    "--handoff-dir", str(handoff_dir),
                    "--marker-path", str(root / "rounds.json"),
                    "--gate-id", f"gate-{gemini_secret}-{google_secret}",
                    "--artifact-key", "art-redact-ok",
                    "--cost-log", str(cost_log),
                    "--output", str(out_file),
                    "--settings", str(root / "absent"),
                    "--timeout-seconds", "10",
                ])
            self.assertEqual(0, rc)
            stdout_text = stdout_buf.getvalue()
            stderr_text = stderr_buf.getvalue()
            cost_text = cost_log.read_text(encoding="utf-8")
            review_text = out_file.read_text(encoding="utf-8")
            payload = json.loads(stdout_text)
            self.assertEqual("success", payload["status"])
            self.assertEqual(_AGY_UUID, payload["session_id"])
            for secret in (gemini_secret, google_secret, "goog-secret-abc-999"):
                self.assertNotIn(secret, stdout_text)
                self.assertNotIn(secret, stderr_text)
                self.assertNotIn(secret, cost_text)
                self.assertNotIn(secret, review_text)

    def test_agy_redacts_before_truncation_uuid_secret_in_stdout_and_bad_utf8_help(self) -> None:
        # 1) Invalid UTF-8 bytes in --help must return inconclusive None, not raise UnicodeDecodeError.
        bad_help_runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, b"\xff\xfe\x80Usage of agy:", b"")
        self.assertIsNone(to_agy.agy_supported_flags(executable="/opt/bin/agy", help_runner=bad_help_runner))

        # 2) Secret straddling the 200-char diagnostic truncation boundary must be redacted BEFORE truncation.
        long_secret = "TOPSECRET_PREFIX_SUFFIX_VALUE_9876543210"
        padded_error = ("authentication required: " + ("x" * 165) + long_secret)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": long_secret}), \
                    mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                    contextlib.redirect_stderr(io.StringIO()):
                res = to_agy.agy_review_gate(
                    request_prompt="Review.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-trunc",
                    artifact_key="art-trunc",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "absent"),
                    runner=lambda argv, **kw: subprocess.CompletedProcess(
                        argv, 1,
                        _agy_stream_bytes(status="ERROR", response="", error=padded_error),
                        b"",
                    ),
                    timeout_seconds=10,
                )
            self.assertEqual("auth_failure", res.status)
            handoff_text = Path(res.envelope["handoff_path"]).read_text(encoding="utf-8")
            self.assertNotIn("TOPSECRET_PREFIX", handoff_text)

        # 3) UUID-shaped secret in env matching conversation_id MUST be rejected during session adoption
        #    so it NEVER persists to .sessions/<hash>.json, stdout, cost.jsonl, or output.
        for mode in ("exit0", "timeout"):
            with self.subTest(uuid_secret_mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                req = root / "req.md"
                req.write_text("Review.", encoding="utf-8")
                art = root / "target.py"
                art.write_text("x = 1\n", encoding="utf-8")
                out_file = root / "review.md"
                stdout_buf = io.StringIO()
                if mode == "exit0":
                    mock_runner = mock.MagicMock(
                        return_value=subprocess.CompletedProcess(["agy"], 0, _agy_stream_bytes(conv_id=_AGY_UUID), b"")
                    )
                else:
                    init_only = (json.dumps({"event": "init", "conversation_id": _AGY_UUID}) + "\n").encode("utf-8")
                    mock_runner = mock.MagicMock(
                        side_effect=subprocess.TimeoutExpired(["agy"], 10, output=init_only, stderr=b"")
                    )
                with mock.patch.dict(os.environ, {"GEMINI_API_KEY": _AGY_UUID}), \
                        mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                        mock.patch.object(to_agy, "agy_supported_flags", return_value=None), \
                        mock.patch.object(to_agy, "_run_agy_subprocess", mock_runner), \
                        contextlib.redirect_stdout(stdout_buf), \
                        contextlib.redirect_stderr(io.StringIO()):
                    rc = to_agy.main([
                        "--request-file", str(req),
                        "--cd", str(root),
                        "--handoff-dir", str(root / "handoffs"),
                        "--marker-path", str(root / "rounds.json"),
                        "--gate-id", "gate-uuid-secret",
                        "--artifact-key", "art-uuid-secret",
                        "--artifact-path", str(art),
                        "--cost-log", str(root / "cost.jsonl"),
                        "--output", str(out_file),
                        "--settings", str(root / "absent"),
                    ])
                self.assertEqual(1, rc)
                payload = json.loads(stdout_buf.getvalue())
                self.assertEqual("provenance_failure", payload["status"])
                self.assertFalse(payload["resumable"])
                self.assertIsNone(payload["session_id"])
                self.assertNotIn(_AGY_UUID, stdout_buf.getvalue())
                self.assertFalse(out_file.exists())
                # Verify .sessions/<hash>.json does NOT contain the secret UUID either.
                sess_path = Path(payload["continuation_state_path"])
                self.assertTrue(sess_path.is_file())
                self.assertNotIn(_AGY_UUID, sess_path.read_text(encoding="utf-8"))

        # 4) Decodable terminal result lacking trailing LF on timeout MUST NOT grant resumability.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            art = root / "target.py"
            art.write_text("x = 1\n", encoding="utf-8")
            unterminated_result = _agy_stream_bytes().rstrip(b"\n")
            with mock.patch.object(to_agy.shutil, "which", return_value="/opt/bin/agy"), \
                    contextlib.redirect_stderr(io.StringIO()):
                r_unterm = to_agy.agy_review_gate(
                    request_prompt="Review.",
                    cd=str(root),
                    handoff_dir=str(root / "handoffs"),
                    marker_path=str(root / "rounds.json"),
                    gate_id="gate-unterm-res",
                    artifact_key="art-unterm-res",
                    cost_log_path=str(root / "cost.jsonl"),
                    settings_path=str(root / "absent"),
                    runner=lambda argv, **kw: (_ for _ in ()).throw(
                        subprocess.TimeoutExpired(argv, 10, output=unterminated_result, stderr=b"")
                    ),
                    timeout_seconds=10,
                    artifact_paths=[str(art)],
                )
            self.assertEqual("provenance_failure", r_unterm.status)
            self.assertFalse(r_unterm.envelope.get("resumable", False))
            state_unterm = json.loads(Path(r_unterm.envelope["continuation_state_path"]).read_text(encoding="utf-8"))
            self.assertEqual("failed", state_unterm["state"])

        # 5) When --handoff-dir itself contains a known secret, stdout MUST return null handoff_path
        #    instead of a fabricated unopenable [REDACTED] path, while still writing the handoff file.
        dir_secret = "AIzaSySecretDirPathValue9988776655"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            req = root / "req.md"
            req.write_text("Review.", encoding="utf-8")
            secret_handoff_dir = root / f"dir-{dir_secret}" / "handoffs"
            stdout_buf = io.StringIO()
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": dir_secret}), \
                    mock.patch.object(to_agy.shutil, "which", return_value=None), \
                    contextlib.redirect_stdout(stdout_buf), \
                    contextlib.redirect_stderr(io.StringIO()):
                rc = to_agy.main([
                    "--request-file", str(req),
                    "--cd", str(root),
                    "--handoff-dir", str(secret_handoff_dir),
                    "--marker-path", str(root / "rounds.json"),
                    "--gate-id", "gate-secret-dir",
                    "--artifact-key", "art-secret-dir",
                    "--cost-log", str(root / "cost.jsonl"),
                    "--output", str(root / "review.md"),
                    "--settings", str(root / "absent"),
                ])
            self.assertEqual(1, rc)
            self.assertNotIn(dir_secret, stdout_buf.getvalue())
            payload = json.loads(stdout_buf.getvalue())
            self.assertIsNone(payload["handoff_path"])
            self.assertTrue((secret_handoff_dir / "handoff-gate-secret-dir.md").is_file())


if __name__ == "__main__":
    unittest.main()
