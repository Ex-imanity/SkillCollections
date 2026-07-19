#!/usr/bin/env python3
"""Fetch a supported internal site's Cookie header into a mode-0600 file."""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Tuple
from urllib.parse import urlparse


DEFAULT_USERNAME_ENV = "SITE_USERNAME"
DEFAULT_PASSWORD_ENV = "SITE_PASSWORD"
DEFAULT_TOOL_DIR_ENV = "BAIJIA_COOKIE_TOOL_DIR"
DEFAULT_TOOL_DIR = "/Users/gaotu/Projects/baijia-cookie"
SUPPORTED_HOSTS = {
    "internal-ad.gaotu100.com",
    "test-internal-ad.gaotu100.com",
    "athena.baijia.com",
    "test-athena.baijia.com",
    "dis.baijia.com",
    "test-dis.baijia.com",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a supported internal site's Cookie into a protected file.",
    )
    parser.add_argument("--url", required=True, help="supported internal HTTPS URL")
    parser.add_argument("--output", required=True, help="destination Cookie file, written with mode 0600")
    parser.add_argument("--username", default="", help=f"CAS username; env fallback: {DEFAULT_USERNAME_ENV}")
    parser.add_argument("--username-env", default=DEFAULT_USERNAME_ENV)
    parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV)
    parser.add_argument(
        "--cookie-tool-dir",
        default=os.environ.get(DEFAULT_TOOL_DIR_ENV, DEFAULT_TOOL_DIR),
        help=f"baijia-cookie directory; env fallback: {DEFAULT_TOOL_DIR_ENV}",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="login timeout in seconds")
    return parser.parse_args()


def validate_target_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("--url 必须是 HTTPS URL")
    if parsed.hostname.lower() not in SUPPORTED_HOSTS:
        raise ValueError(f"不受支持的目标主机：{parsed.hostname}")
    return url


def resolve_credentials(
    username: str,
    username_env: str,
    password_env: str,
    interactive: bool,
    prompt: Callable[[str], str] = input,
    password_prompt: Callable[[str], str] = getpass.getpass,
) -> Tuple[str, str]:
    resolved_username = username.strip() or os.environ.get(username_env, "").strip()
    if not resolved_username and interactive:
        resolved_username = prompt("CAS username: ").strip()

    password = os.environ.get(password_env, "")
    if not password and interactive:
        password = password_prompt("CAS password: ")
    return resolved_username, password


def fetch_cookie(
    url: str,
    username: str,
    password: str,
    password_env: str,
    cookie_tool_dir: str,
    timeout: float,
    runner=subprocess.run,
) -> str:
    target_url = validate_target_url(url)
    command = [
        "node",
        "bin/get-site-cookie.mjs",
        "--url",
        target_url,
        "--username",
        username,
        "--password-env",
        password_env,
    ]
    environment = os.environ.copy()
    environment[password_env] = password
    try:
        result = runner(
            command,
            cwd=cookie_tool_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("无法运行 Cookie 工具：请安装 Node.js 并检查 --cookie-tool-dir") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Cookie 获取超时（{timeout:g} 秒）") from exc

    if result.returncode != 0:
        detail = result.stderr.strip()
        suffix = f": {detail[:500]}" if detail else ""
        raise RuntimeError(f"Cookie 获取失败（退出码 {result.returncode}）{suffix}")
    try:
        cookie = json.loads(result.stdout).get("cookieHeader", "").strip()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Cookie 工具未返回有效 JSON") from exc
    if not cookie:
        raise RuntimeError("Cookie 工具未返回 cookieHeader")
    return cookie


def write_cookie_file(path: Path, cookie: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(cookie)
    finally:
        if descriptor != -1:
            os.close(descriptor)


def main() -> int:
    args = parse_args()
    try:
        validate_target_url(args.url)
        username, password = resolve_credentials(
            args.username,
            args.username_env,
            args.password_env,
            interactive=sys.stdin.isatty(),
        )
        if not username:
            raise RuntimeError(f"请使用 --username 或设置 {args.username_env}")
        if not password:
            raise RuntimeError(f"请设置 {args.password_env} 或在交互终端输入密码")
        cookie = fetch_cookie(
            args.url,
            username,
            password,
            args.password_env,
            args.cookie_tool_dir,
            args.timeout,
        )
        output = Path(args.output)
        write_cookie_file(output, cookie)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Cookie written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
