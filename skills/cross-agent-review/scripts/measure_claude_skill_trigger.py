"""Measure ClaudeCode auto-triggering against a real project-installed skill.

The gauge installs the source skill only inside an isolated temporary project,
exposes only ClaudeCode's Skill tool, and stops the subprocess as soon as the
target Skill invocation appears. It never waits for the review workflow itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional


class TriggerStreamDetector:
    """Stateful detector for complete and partial Claude stream-json events."""

    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        self._pending_skill = False
        self._partial_input = ""

    def feed(self, event: dict) -> Optional[str]:
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if (
                    block.get("type") == "tool_use"
                    and block.get("name") == "Skill"
                    and self.skill_name
                    in json.dumps(block.get("input", {}), ensure_ascii=False)
                ):
                    return "triggered"

        if event.get("type") != "stream_event":
            return "result" if event.get("type") == "result" else None

        stream_event = event.get("event", {})
        event_type = stream_event.get("type")
        if event_type == "content_block_start":
            block = stream_event.get("content_block", {})
            self._pending_skill = (
                block.get("type") == "tool_use" and block.get("name") == "Skill"
            )
            self._partial_input = ""
        elif event_type == "content_block_delta" and self._pending_skill:
            delta = stream_event.get("delta", {})
            if delta.get("type") == "input_json_delta":
                self._partial_input += delta.get("partial_json", "")
                if self.skill_name in self._partial_input:
                    return "triggered"
        elif event_type == "content_block_stop":
            self._pending_skill = False
            self._partial_input = ""
        return None


def build_command(model: str, max_budget_usd: float) -> list[str]:
    if max_budget_usd <= 0:
        raise ValueError("max_budget_usd must be positive")
    return [
        "claude",
        "-p",
        "--input-format",
        "text",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--model",
        model,
        "--permission-mode",
        "plan",
        "--tools",
        "Skill",
        "--allowedTools",
        "Skill",
        "--no-session-persistence",
        "--max-budget-usd",
        str(max_budget_usd),
    ]


def balanced_order(items: list[dict]) -> list[dict]:
    positives = [item for item in items if item.get("should_trigger") is True]
    negatives = [item for item in items if item.get("should_trigger") is False]
    ordered: list[dict] = []
    for index in range(max(len(positives), len(negatives))):
        if index < len(positives):
            ordered.append(positives[index])
        if index < len(negatives):
            ordered.append(negatives[index])
    return ordered


def safe_error_metadata(stderr: bytes) -> dict:
    """Keep diagnostic identity without persisting provider stderr content."""
    return {
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        process.wait()


def run_query(
    query: str,
    skill_name: str,
    cwd: Path,
    model: str,
    max_budget_usd: float,
    timeout_seconds: float,
) -> dict:
    command = build_command(model=model, max_budget_usd=max_budget_usd)
    env = {key: value for key, value in os.environ.items() if key != "CLAUDECODE"}
    started = time.monotonic()
    detector = TriggerStreamDetector(skill_name)
    stderr_bytes = bytearray()
    result_event: dict = {}
    status = "timeout"
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdin.write(query.encode("utf-8"))
    process.stdin.close()

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout_buffer = b""
    try:
        while time.monotonic() - started < timeout_seconds:
            if process.poll() is not None and not selector.get_map():
                break
            for key, _ in selector.select(timeout=0.25):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "stderr":
                    stderr_bytes.extend(chunk)
                    continue
                stdout_buffer += chunk
                while b"\n" in stdout_buffer:
                    raw_line, stdout_buffer = stdout_buffer.split(b"\n", 1)
                    try:
                        event = json.loads(raw_line)
                    except (ValueError, TypeError, UnicodeDecodeError):
                        continue
                    outcome = detector.feed(event)
                    if outcome == "triggered":
                        status = "triggered"
                        return {
                            "triggered": True,
                            "status": status,
                            "duration_seconds": round(time.monotonic() - started, 3),
                            "total_cost_usd": None,
                        }
                    if event.get("type") == "result":
                        result_event = event
                        status = (
                            "provider_error"
                            if event.get("is_error") is True
                            else "completed_no_trigger"
                        )
                        return {
                            "triggered": False,
                            "status": status,
                            "duration_seconds": round(time.monotonic() - started, 3),
                            "total_cost_usd": event.get("total_cost_usd"),
                        }
        if process.poll() is not None and result_event:
            status = "provider_error" if result_event.get("is_error") else "completed_no_trigger"
        outcome = {
            "triggered": False,
            "status": status,
            "duration_seconds": round(time.monotonic() - started, 3),
            "total_cost_usd": result_event.get("total_cost_usd"),
        }
        if stderr_bytes:
            outcome.update(safe_error_metadata(bytes(stderr_bytes)))
        return outcome
    finally:
        selector.close()
        _stop_process(process)


def measure(args: argparse.Namespace) -> dict:
    items = json.loads(args.queries.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not all(
        isinstance(item, dict)
        and isinstance(item.get("query"), str)
        and isinstance(item.get("should_trigger"), bool)
        for item in items
    ):
        raise ValueError("queries must be a list of query/should_trigger objects")
    skill_path = args.skill_path.resolve()
    if not (skill_path / "SKILL.md").is_file():
        raise ValueError("skill_path must contain SKILL.md")

    results = []
    with tempfile.TemporaryDirectory(prefix="real-skill-trigger-") as temporary:
        project = Path(temporary)
        install_parent = project / ".claude" / "skills"
        install_parent.mkdir(parents=True)
        (install_parent / args.skill_name).symlink_to(skill_path, target_is_directory=True)
        for item in balanced_order(items):
            observed = run_query(
                query=item["query"],
                skill_name=args.skill_name,
                cwd=project,
                model=args.model,
                max_budget_usd=args.max_budget_usd_per_query,
                timeout_seconds=args.timeout_seconds,
            )
            determinate = observed["status"] in {"triggered", "completed_no_trigger"}
            observed.update(
                {
                    "query": item["query"],
                    "should_trigger": item["should_trigger"],
                    "pass": (
                        observed["triggered"] == item["should_trigger"]
                        if determinate
                        else None
                    ),
                }
            )
            results.append(observed)

    determinate_results = [result for result in results if result["pass"] is not None]
    payload = {
        "skill_name": args.skill_name,
        "mechanism": "real temporary project skill; Skill-only early-exit gauge",
        "model": args.model,
        "max_budget_usd_per_query": args.max_budget_usd_per_query,
        "summary": {
            "correct": sum(result["pass"] is True for result in determinate_results),
            "incorrect": sum(result["pass"] is False for result in determinate_results),
            "determinate": len(determinate_results),
            "ambiguous": len(results) - len(determinate_results),
            "total": len(results),
        },
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--skill-path", type=Path, required=True)
    parser.add_argument("--skill-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--timeout-seconds", type=float, default=45)
    parser.add_argument("--max-budget-usd-per-query", type=float, required=True)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = measure(args)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0 if payload["summary"]["ambiguous"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
