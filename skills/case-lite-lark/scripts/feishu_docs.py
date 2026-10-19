#!/usr/bin/env python3
"""Standalone CLI for case-lite-lark; no MCP server or credential access."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from documents import DocumentReader
from lark_cli import CLIError, LarkCLI
from lark_runtime import CLI_INSTALL_HINT, cli_environment, load_runtime


def doctor() -> dict:
    env = cli_environment()
    runtime = load_runtime()
    checks = [("api", "--help"), ("wiki", "+node-get", "--help"),
              ("wiki", "+node-list", "--help"), ("markdown", "+fetch", "--help"),
              ("docs", "+media-preview", "--help"), ("whiteboard", "+export", "--help")]
    expected = ["--params", "--node-token", "--page-token", "--file-token", "--output", "--output-type"]
    try:
        version = subprocess.run(runtime.command("--version"), capture_output=True, text=True, timeout=15, check=False, env=env)
        if version.returncode:
            raise CLIError("无法读取 lark-cli 版本")
        for args, flag in zip(checks, expected):
            response = subprocess.run(runtime.command(*args), capture_output=True, text=True, timeout=15, check=False, env=env)
            if response.returncode or flag not in response.stdout:
                raise CLIError(f"CLI 缺少 {' '.join(args[:-1])} 所需参数 {flag}，请由平台升级 CLI")
    except FileNotFoundError as exc:
        raise CLIError(CLI_INSTALL_HINT, runtime.describe() | {"message": CLI_INSTALL_HINT}) from exc
    except subprocess.TimeoutExpired as exc:
        raise CLIError("CLI 能力检查超时") from exc
    return {**runtime.describe(), "cli_version": version.stdout.strip(), "capabilities": "available", "auth_verified": False,
            "message": "只检查命令能力；未登录、未读取凭证、未请求飞书资源。首次真实请求仍须验证 user 权限。"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor", help="离线检查 CLI 能力，不发起授权")
    children = subs.add_parser("children", help="只发现 Wiki 子文档元数据")
    children.add_argument("url")
    children.add_argument("--recursive", action="store_true")
    outline = subs.add_parser("outline", help="获取目录元数据，不向模型返回正文")
    outline.add_argument("url")
    outline.add_argument("--max-level", type=int, default=4)
    outline.add_argument("--output", type=Path, required=True)
    read = subs.add_parser("read", help="读取经用户确认的章节并直接写入语料文件")
    read.add_argument("--outline-file", type=Path, required=True)
    group = read.add_mutually_exclusive_group(required=True)
    group.add_argument("--section-id", nargs="+")
    group.add_argument("--all", action="store_true", help="仅在用户确认全文读取后使用")
    read.add_argument("--output-dir", type=Path, required=True)
    read.add_argument("--doc-key", required=True, help="按文档顺序命名，例如 01-backend")
    args = parser.parse_args(argv)
    try:
        reader = DocumentReader(LarkCLI())
        if args.command == "doctor":
            data = doctor()
        elif args.command == "children":
            data = reader.children(args.url, args.recursive)
        elif args.command == "outline":
            data = reader.outline(args.url, args.max_level)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            data = data | {"outline_path": str(args.output.resolve())}
        else:
            root = args.output_dir.resolve()
            if not root.is_relative_to(Path.cwd().resolve()):
                raise CLIError("output-dir 必须位于当前工作目录内，供 CLI 下载和 Claude Code Read 读取")
            data = reader.read(json.loads(args.outline_file.read_text(encoding="utf-8")),
                               args.section_id or [], root, args.doc_key, args.all)
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False, indent=2))
        return 0
    except CLIError as exc:
        error = exc.details
    except (ValueError, KeyError, TypeError, OSError):
        error = {"message": "输入、目录文件或任务产物无效；请重新获取目录并检查可写权限"}
    print(json.dumps({"ok": False, "error": error}, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
