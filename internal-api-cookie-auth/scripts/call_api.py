#!/usr/bin/env python3
"""Optional reference: replay a browser-copied curl against an internal CAS API.

This is one concrete way to apply the Skill's guidance; a hand-written Python or
bash wrapper that follows the same principles is equally valid. It recognizes a
pasted ``curl`` command, fetches a fresh Cookie for the target host through
``fetch_cookie.py``, then replays the request with the fresh Cookie.

Principles it enforces:
- Minimal headers: forwards only ``content-type`` by default (needed for a JSON
  body). Add any header the endpoint actually requires with ``--keep-header``.
  Browser noise (cookie, origin, referer, priority, sec-*, accept-language,
  user-agent, identity headers) is dropped.
- Write safety: a side-effecting method (anything but GET/HEAD) refuses to send
  without ``--confirm-write``, forcing the caller to confirm with the user first.
- Never prints the Cookie or password. Auto-retries only idempotent reads.
"""

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_cookie  # noqa: E402


# Minimal-by-default allowlist: only these headers are forwarded unless the
# caller adds more with --keep-header. content-type is kept because it governs
# how the request body is parsed; everything else a browser sends (cookie,
# origin, referer, priority, sec-*, accept, accept-language, user-agent, and
# identity headers like uid) is dropped until proven necessary.
DEFAULT_KEEP_HEADERS = {"content-type"}
# Headers that carry the caller's identity and must match the fetched account.
IDENTITY_HEADERS = {"uid"}
IDEMPOTENT_METHODS = {"GET", "HEAD"}
AUTH_FAIL_STATUS = {401}
CAS_JSON_CODE = 700
_DATA_FLAGS = {"-d", "--data", "--data-raw", "--data-binary", "--data-ascii"}


def _join_continuations(text: str) -> str:
    return text.replace("\\\r\n", " ").replace("\\\n", " ")


def parse_curl(text: str) -> Dict:
    """Parse a curl command string into its request parts."""
    tokens = shlex.split(_join_continuations(text))
    if tokens and tokens[0] == "curl":
        tokens = tokens[1:]

    url = ""
    method = ""
    headers: List[Tuple[str, str]] = []
    cookie = ""
    body: Optional[str] = None

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("-H", "--header"):
            index += 1
            name, separator, value = tokens[index].partition(":")
            if separator:
                headers.append((name.strip(), value.strip()))
        elif token in ("-b", "--cookie"):
            index += 1
            cookie = tokens[index]
        elif token in ("-X", "--request"):
            index += 1
            method = tokens[index].upper()
        elif token in _DATA_FLAGS:
            index += 1
            value = tokens[index]
            if value.startswith("@"):
                value = Path(value[1:]).read_text(encoding="utf-8")
            body = value if body is None else f"{body}&{value}"
        elif token in ("-A", "--user-agent"):
            index += 1
            headers.append(("user-agent", tokens[index]))
        elif token in ("-e", "--referer"):
            index += 1  # captured then dropped
        elif token == "--url":
            index += 1
            url = tokens[index]
        elif token.startswith("-"):
            pass  # ignore value-less flags such as --compressed, -s, -i, -k
        elif not url:
            url = token
        index += 1

    if not url:
        raise ValueError("curl 中未找到 URL")
    if not method:
        method = "POST" if body is not None else "GET"
    return {"url": url, "method": method, "headers": headers, "cookie": cookie, "body": body}


def select_headers(
    headers: List[Tuple[str, str]],
    keep: Tuple[str, ...] = (),
    drop: Tuple[str, ...] = (),
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Return (forwarded headers, dropped header names).

    Minimal by default: forward only the ``DEFAULT_KEEP_HEADERS`` allowlist plus
    anything named in ``keep``; drop everything else. ``drop`` can also remove a
    header that would otherwise be kept.
    """
    keep_set = (DEFAULT_KEEP_HEADERS | {name.lower() for name in keep}) - {name.lower() for name in drop}
    forwarded: List[Tuple[str, str]] = []
    dropped: List[str] = []
    for name, value in headers:
        if name.lower() in keep_set:
            forwarded.append((name, value))
        else:
            dropped.append(name)
    return forwarded, dropped


def should_retry(method: str, assume_idempotent: bool, no_retry: bool) -> bool:
    if no_retry:
        return False
    return method.upper() in IDEMPOTENT_METHODS or assume_idempotent


def is_auth_failure(status: int, text: str) -> bool:
    if status in AUTH_FAIL_STATUS:
        return True
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(payload, dict) and payload.get("code") == CAS_JSON_CODE


def send_request(
    url: str,
    method: str,
    headers: List[Tuple[str, str]],
    body: Optional[str],
    cookie_header: str,
    timeout: float,
    opener=None,
) -> Tuple[int, str]:
    active_opener = opener or build_opener()
    request_headers = {name: value for name, value in headers}
    request_headers["Cookie"] = cookie_header
    data = body.encode("utf-8") if body is not None else None
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        response = active_opener.open(request, timeout=timeout)
        status = getattr(response, "status", None) or response.getcode()
        payload = response.read()
    except HTTPError as exc:
        status = getattr(exc, "status", None) or exc.code
        payload = exc.read()
    text = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else (payload or "")
    return status, text


def obtain_cookie(args: argparse.Namespace, target_url: str) -> str:
    cas_service_url = args.cas_service_url
    if args.discover_cas and not cas_service_url:
        cas_service_url = fetch_cookie.discover_cas_service(target_url, args.timeout)
    elif not fetch_cookie.is_built_in_host(target_url) and not cas_service_url:
        raise RuntimeError("未知主机需要 --discover-cas 或 --cas-service-url")

    username, password = fetch_cookie.resolve_credentials(
        args.username,
        args.username_env,
        args.password_env,
        interactive=sys.stdin.isatty(),
    )
    if not username:
        raise RuntimeError(f"请使用 --username 或设置 {args.username_env}")
    if not password:
        raise RuntimeError(f"请设置 {args.password_env} 或在交互终端输入密码")
    return fetch_cookie.fetch_cookie(
        target_url,
        username,
        password,
        args.password_env,
        args.cookie_tool_dir,
        args.timeout,
        cas_service_url or None,
    )


def read_curl(args: argparse.Namespace) -> str:
    if args.curl_file:
        return Path(args.curl_file).read_text(encoding="utf-8")
    if sys.stdin.isatty():
        raise RuntimeError("请用 --curl-file 提供 curl，或从标准输入管道传入")
    return sys.stdin.read()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a pasted curl against an internal CAS-protected API with a fresh Cookie.",
    )
    parser.add_argument(
        "--curl-file",
        default="",
        help="file containing the pasted curl command; omit to read curl from stdin",
    )
    parser.add_argument("--username", default="", help=f"CAS username; env fallback: {fetch_cookie.DEFAULT_USERNAME_ENV}")
    parser.add_argument("--username-env", default=fetch_cookie.DEFAULT_USERNAME_ENV)
    parser.add_argument("--password-env", default=fetch_cookie.DEFAULT_PASSWORD_ENV)
    authentication = parser.add_mutually_exclusive_group()
    authentication.add_argument("--cas-service-url", default="", help="explicit HTTPS CAS service URL")
    authentication.add_argument("--discover-cas", action="store_true", help="probe once for a trusted CAS redirect or code:700 service URL")
    parser.add_argument(
        "--cookie-tool-dir",
        default=os.environ.get(fetch_cookie.DEFAULT_TOOL_DIR_ENV, fetch_cookie.DEFAULT_TOOL_DIR),
        help=f"baijia-cookie directory; env fallback: {fetch_cookie.DEFAULT_TOOL_DIR_ENV}",
    )
    parser.add_argument("--keep-header", action="append", default=[], metavar="NAME", help="force-forward a header otherwise dropped")
    parser.add_argument("--drop-header", action="append", default=[], metavar="NAME", help="drop an additional header")
    parser.add_argument("--confirm-write", action="store_true", help="required to send a side-effecting method (non GET/HEAD); confirm with the user first")
    parser.add_argument("--assume-idempotent", action="store_true", help="allow one auth-refresh retry for a non-GET/HEAD method")
    parser.add_argument("--no-retry", action="store_true", help="never retry after an auth failure")
    parser.add_argument("--timeout", type=float, default=30.0, help="per-request timeout in seconds")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        parsed = parse_curl(read_curl(args))
        target_url = fetch_cookie.validate_target_url(parsed["url"])
        method = parsed["method"]
        headers, dropped = select_headers(parsed["headers"], tuple(args.keep_header), tuple(args.drop_header))

        if method.upper() not in IDEMPOTENT_METHODS and not args.confirm_write:
            print(
                f"error: {method} 可能有副作用（创建/更新/删除等），重放前必须向用户确认。"
                "确认此请求可安全重放后加 --confirm-write 再运行。",
                file=sys.stderr,
            )
            return 3

        cookie = obtain_cookie(args, target_url)
        status, text = send_request(target_url, method, headers, parsed["body"], cookie, args.timeout)

        if is_auth_failure(status, text):
            if should_retry(method, args.assume_idempotent, args.no_retry):
                cookie = obtain_cookie(args, target_url)
                status, text = send_request(target_url, method, headers, parsed["body"], cookie, args.timeout)
            else:
                print(
                    f"error: 认证失败（HTTP {status}）且 {method} 非幂等，未自动重试；"
                    "确认操作幂等后加 --assume-idempotent",
                    file=sys.stderr,
                )
                return 3
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    forwarded_names = [name for name, _ in headers]
    print(f"host={urlparse(target_url).hostname or ''} method={method} status={status}", file=sys.stderr)
    print(f"forwarded headers: {', '.join(forwarded_names) or '(none)'}", file=sys.stderr)
    print(f"dropped headers: {', '.join(dropped) or '(none)'}", file=sys.stderr)
    if any(name.lower() in IDENTITY_HEADERS for name in forwarded_names):
        print("note: 已转发身份头（如 uid），请确认与登录账号一致", file=sys.stderr)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
