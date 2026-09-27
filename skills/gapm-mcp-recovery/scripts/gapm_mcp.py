#!/usr/bin/env python3
"""Diagnose and call the internal GAPM MCP without relying on task tool injection."""

import argparse
import json
import os
import select
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


SERVER_NAME = "gapm_agent_tools"
SERVER_URL = "https://tech.baijia.com/mcp-server/gapm_agent_tools/mcp"
EXPECTED_TOOLS = {
    "gapm_log_query_v2",
    "gapm_trace_query_v2",
    "gapm_trace_and_log_query_v2",
}


class AppServerError(RuntimeError):
    pass


class AppServerClient:
    def __init__(self, codex_bin: str, timeout: int) -> None:
        self.timeout = timeout
        self.process = subprocess.Popen(
            [codex_bin, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._next_id = 1

    def __enter__(self):
        self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "gapm-mcp-recovery",
                    "title": "GAPM MCP recovery",
                    "version": "1.0",
                }
            },
        )
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            raise AppServerError("App Server pipes are unavailable")
        request_id = self._next_id
        self._next_id += 1
        payload = {"method": method, "id": request_id, "params": params}
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            remaining = max(0.0, deadline - time.time())
            ready, _, _ = select.select(
                [self.process.stdout], [], [], min(1.0, remaining)
            )
            if not ready:
                continue
            line = self.process.stdout.readline()
            if not line:
                break
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise AppServerError(
                    f"{method}: {json.dumps(message['error'], ensure_ascii=False)}"
                )
            result = message.get("result", {})
            return result if isinstance(result, dict) else {"value": result}
        raise AppServerError(f"{method} timed out after {self.timeout}s")


def classify_status(configured: bool, server: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not configured:
        return {
            "state": "CONFIG_MISSING",
            "bridge_available": False,
            "needs_restart": False,
            "recommended_command": (
                f"codex mcp add {SERVER_NAME} --url {SERVER_URL}"
            ),
        }
    if server is None:
        return {
            "state": "STARTUP_FAILED",
            "bridge_available": False,
            "needs_restart": False,
            "recommended_command": f"codex mcp get {SERVER_NAME}",
        }

    server_info = server.get("serverInfo")
    tools = server.get("tools") or {}
    tool_names = set(tools) if isinstance(tools, dict) else {
        item.get("name") for item in tools if isinstance(item, dict)
    }
    error = server.get("error")
    auth_status = server.get("authStatus")

    if server_info and EXPECTED_TOOLS.issubset(tool_names) and not error:
        state = "HEALTHY"
        command = None
        bridge_available = True
    elif not server_info and not tool_names and auth_status == "oAuth":
        state = "AUTH_REQUIRED"
        command = f"codex mcp login {SERVER_NAME}"
        bridge_available = False
    elif server_info and not EXPECTED_TOOLS.issubset(tool_names):
        state = "TOOLS_MISSING"
        command = None
        bridge_available = False
    else:
        state = "STARTUP_FAILED"
        command = None
        bridge_available = False

    return {
        "state": state,
        "bridge_available": bridge_available,
        "needs_restart": False,
        "recommended_command": command,
        "server_info": server_info,
        "tool_names": sorted(name for name in tool_names if name),
        "auth_status": auth_status,
        "error": error,
    }


def parse_configuration(
    returncode: int, stdout: str, stderr: str
) -> Dict[str, Any]:
    configured = returncode == 0
    valid = configured and SERVER_URL in stdout and "enabled: true" in stdout
    if not configured:
        state = "CONFIG_MISSING"
    elif not valid:
        state = "CONFIG_INVALID"
    else:
        state = "CONFIG_VALID"
    return {
        "configured": configured,
        "configuration_valid": valid,
        "configuration_state": state,
        "configuration_error": None if configured else stderr.strip(),
    }


def get_configuration(codex_bin: str) -> Dict[str, Any]:
    completed = subprocess.run(
        [codex_bin, "mcp", "get", SERVER_NAME],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return parse_configuration(
        completed.returncode, completed.stdout, completed.stderr
    )


def get_status(codex_bin: str, timeout: int) -> Dict[str, Any]:
    config = get_configuration(codex_bin)
    if not config["configured"]:
        return {**classify_status(False, None), **config}
    if not config["configuration_valid"]:
        return {
            "state": "CONFIG_INVALID",
            "bridge_available": False,
            "needs_restart": False,
            "recommended_commands": [
                f"codex mcp remove {SERVER_NAME}",
                f"codex mcp add {SERVER_NAME} --url {SERVER_URL}",
            ],
            **config,
        }
    try:
        with AppServerClient(codex_bin, timeout) as client:
            result = client.request("mcpServerStatus/list", {})
        servers = result.get("data", result.get("servers", []))
        server = next(
            (
                item
                for item in servers
                if isinstance(item, dict) and item.get("name") == SERVER_NAME
            ),
            None,
        )
        return {**classify_status(True, server), **config}
    except (AppServerError, OSError, json.JSONDecodeError) as exc:
        return {
            **classify_status(True, None),
            **config,
            "error": str(exc),
        }


def validate_output_path(cwd: Path, path: Path) -> Path:
    root = (cwd / ".local").resolve()
    resolved = path.resolve() if path.is_absolute() else (cwd / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path must stay under {root}") from exc
    return resolved


def load_arguments(cwd: Path, path: Path) -> Dict[str, Any]:
    resolved = validate_output_path(cwd, path)
    with resolved.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("arguments file must contain a JSON object")
    return value


def write_private_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(path, 0o600)


def call_tool(
    codex_bin: str,
    timeout: int,
    cwd: Path,
    tool: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    if tool not in EXPECTED_TOOLS:
        raise ValueError(f"unsupported GAPM tool: {tool}")
    with AppServerClient(codex_bin, timeout) as client:
        started = client.request(
            "thread/start",
            {
                "cwd": str(cwd),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "ephemeral": True,
            },
        )
        thread_id = started.get("thread", {}).get("id")
        if not thread_id:
            raise AppServerError("thread/start returned no thread id")
        return client.request(
            "mcpServer/tool/call",
            {
                "threadId": thread_id,
                "server": SERVER_NAME,
                "tool": tool,
                "arguments": arguments,
            },
        )


def print_json(value: Dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def command_status(args: argparse.Namespace) -> int:
    status = get_status(args.codex_bin, args.timeout)
    print_json(status)
    return 0 if status["state"] == "HEALTHY" else 2


def command_login(args: argparse.Namespace) -> int:
    completed = subprocess.run(
        [args.codex_bin, "mcp", "login", SERVER_NAME],
        check=False,
    )
    if completed.returncode != 0:
        print_json({"state": "LOGIN_FAILED", **login_failure_guidance()})
        return completed.returncode
    return command_status(args)


def login_failure_guidance() -> Dict[str, Any]:
    return {
        "recommended_command": f"codex mcp login {SERVER_NAME}",
        "fallback_command": (
            f"codex mcp logout {SERVER_NAME} && codex mcp login {SERVER_NAME}"
        ),
        "fallback_condition": "only after repeated direct login failure",
    }


def command_smoke(args: argparse.Namespace) -> int:
    status = get_status(args.codex_bin, args.timeout)
    if status["state"] != "HEALTHY":
        print_json(status)
        return 2
    arguments = {
        "env": args.env,
        "serviceName": "ai-search-platform",
        "keyword": f"gapm-recovery-smoke-no-match-{uuid.uuid4().hex}",
        "logType": "app",
        "fromTimestampInSeconds": 0,
        "toTimestampInSeconds": 0,
        "limit": 1,
    }
    result = call_tool(
        args.codex_bin,
        args.timeout,
        Path.cwd().resolve(),
        "gapm_log_query_v2",
        arguments,
    )
    content = result.get("content", [])
    print_json(
        {
            "state": "SMOKE_OK",
            "bridge_available": True,
            "tool": "gapm_log_query_v2",
            "content_items": len(content) if isinstance(content, list) else None,
            "raw_result_persisted": False,
        }
    )
    return 0


def command_call(args: argparse.Namespace) -> int:
    cwd = Path.cwd().resolve()
    arguments = load_arguments(cwd, Path(args.arguments_file))
    output = validate_output_path(cwd, Path(args.output))
    result = call_tool(
        args.codex_bin,
        args.timeout,
        cwd,
        args.tool,
        arguments,
    )
    write_private_json(output, result)
    print_json(
        {
            "state": "CALL_SUCCEEDED",
            "bridge_available": True,
            "tool": args.tool,
            "output": str(output),
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose and call gapm_agent_tools without restarting Codex"
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--timeout", type=int, default=90)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.set_defaults(handler=command_status)

    login_parser = subparsers.add_parser("login")
    login_parser.set_defaults(handler=command_login)

    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument("--env", choices=("prod", "test", "dev"), default="prod")
    smoke_parser.set_defaults(handler=command_smoke)

    call_parser = subparsers.add_parser("call")
    call_parser.add_argument("--tool", choices=sorted(EXPECTED_TOOLS), required=True)
    call_parser.add_argument("--arguments-file", required=True)
    call_parser.add_argument("--output", required=True)
    call_parser.set_defaults(handler=command_call)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (AppServerError, OSError, ValueError, json.JSONDecodeError) as exc:
        print_json({"state": "ERROR", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
