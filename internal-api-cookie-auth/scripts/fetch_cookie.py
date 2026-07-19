#!/usr/bin/env python3
"""Fetch a supported internal site's Cookie header into a mode-0600 file."""

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_USERNAME_ENV = "SITE_USERNAME"
DEFAULT_PASSWORD_ENV = "SITE_PASSWORD"
DEFAULT_TOOL_DIR_ENV = "BAIJIA_COOKIE_TOOL_DIR"
DEFAULT_TOOL_DIR = "/Users/gaotu/Projects/baijia-cookie"
BUILT_IN_HOSTS = {
    "internal-ad.gaotu100.com",
    "test-internal-ad.gaotu100.com",
    "athena.baijia.com",
    "test-athena.baijia.com",
    "dis.baijia.com",
    "test-dis.baijia.com",
}
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch an internal HTTPS site's Cookie into a protected file.",
    )
    parser.add_argument("--url", required=True, help="internal HTTPS URL")
    parser.add_argument("--output", required=True, help="destination Cookie file, written with mode 0600")
    parser.add_argument("--username", default="", help=f"CAS username; env fallback: {DEFAULT_USERNAME_ENV}")
    parser.add_argument("--username-env", default=DEFAULT_USERNAME_ENV)
    parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV)
    authentication = parser.add_mutually_exclusive_group()
    authentication.add_argument(
        "--cas-service-url",
        default="",
        help="explicit HTTPS CAS service URL for a host outside the built-in list",
    )
    authentication.add_argument(
        "--discover-cas",
        action="store_true",
        help="probe an authorized read-only URL once to discover a trusted CAS redirect",
    )
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
    return url


def is_built_in_host(url: str) -> bool:
    return urlparse(url).hostname.lower() in BUILT_IN_HOSTS


def expected_cas_host(target_url: str) -> str:
    hostname = urlparse(target_url).hostname.lower()
    return "test-cas.baijia.com" if hostname.startswith("test-") else "cas.baijia.com"


def _read_body(response, limit: int = 65536) -> str:
    reader = getattr(response, "read", None)
    if not callable(reader):
        return ""
    try:
        raw = reader(limit)
    except (TypeError, ValueError):
        raw = reader()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw or ""


def _service_from_cas_login(login_url_value: str, target_url: str) -> str:
    login_url = urlparse(urljoin(target_url, login_url_value))
    expected_host = expected_cas_host(target_url)
    if login_url.scheme != "https" or (login_url.hostname or "").lower() != expected_host:
        raise ValueError(f"重定向未指向可信 CAS 主机 {expected_host}")
    if login_url.path != "/cas/login":
        raise ValueError("可信 CAS 重定向不是 /cas/login 路径")

    services = parse_qs(login_url.query).get("service", [])
    if len(services) != 1:
        raise ValueError("可信 CAS 重定向缺少唯一 service 参数")
    service_url = urlparse(services[0])
    if service_url.scheme != "https" or not service_url.hostname:
        raise ValueError("CAS service 参数必须是 HTTPS URL")
    return service_url.geturl()


def _service_from_json_body(body: str, target_url: str) -> Optional[str]:
    """Extract a CAS service URL from a gaotu ``{"code":700,"data":"..."}`` body.

    Unauthenticated internal APIs frequently answer with HTTP 200/401 and a JSON
    envelope whose ``data`` field is the full ``.../cas/login?service=...`` URL,
    rather than issuing an HTTP redirect. ``data`` is validated through the same
    trusted-CAS checks as a ``Location`` redirect before it is trusted.
    """
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("code") != 700:
        return None
    data = payload.get("data")
    if not isinstance(data, str) or not data:
        return None
    return _service_from_cas_login(data, target_url)


def discover_cas_service(url: str, timeout: float, opener=None) -> str:
    target_url = validate_target_url(url)
    active_opener = opener or build_opener(NoRedirectHandler())
    request = Request(target_url, headers={"accept": "application/json, text/plain, */*"})
    try:
        response = active_opener.open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc

    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else 0

    if status in REDIRECT_STATUS_CODES:
        location = response.headers.get("Location")
        if not location:
            raise ValueError("CAS 重定向缺少 Location 响应头")
        return _service_from_cas_login(location, target_url)

    service = _service_from_json_body(_read_body(response), target_url)
    if service:
        return service
    raise ValueError(
        f"无 Cookie 探测未发现可信 CAS 重定向或 code:700 服务地址（HTTP {status}）"
    )


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
    cas_service_url: Optional[str] = None,
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
    if cas_service_url:
        command.extend(["--cas-service-url", cas_service_url])
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
        target_url = validate_target_url(args.url)
        cas_service_url = args.cas_service_url
        if args.discover_cas:
            cas_service_url = discover_cas_service(target_url, args.timeout)
        elif not is_built_in_host(target_url) and not cas_service_url:
            raise RuntimeError("未知主机需要 --discover-cas 或 --cas-service-url")
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
            target_url,
            username,
            password,
            args.password_env,
            args.cookie_tool_dir,
            args.timeout,
            cas_service_url or None,
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
