#!/usr/bin/env python3
"""Self-contained CAS (baijia) HTTP login — no external tool or browser.

Ports the CAS login flow to the Python standard library so the Skill is
distributable on its own. It logs in over the CAS `/cas/bg/login` JSON endpoint
and returns the `Cookie` header value for the target host. No third-party
packages, no Node.js, no hardcoded checkout path.

Built-in service entries: Internal AD / UOS, Athena, Compass. Any other internal
host needs an explicit `cas_service_url` (typically discovered from a trusted CAS
redirect or a `code:700` body — see fetch_cookie.py).
"""

import json
import re
import time
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
HTTP_UPGRADE_STATUS_CODES = {307, 308}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


# ---------------------------------------------------------------------------
# Service configuration (ported from cas-service-config)
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_internal_ad(url: str) -> bool:
    return bool(re.fullmatch(r"(test-)?internal-ad\.gaotu100\.com", _host(url)))


def is_athena(url: str) -> bool:
    return bool(re.fullmatch(r"(test-)?athena\.baijia\.com", _host(url)))


def is_compass(url: str) -> bool:
    return bool(re.fullmatch(r"(test-)?dis\.baijia\.com", _host(url)))


def has_builtin_service(url: str) -> bool:
    return is_internal_ad(url) or is_athena(url) or is_compass(url)


def athena_service_url(url: str) -> str:
    prefix = "test-" if _host(url).startswith("test-") else ""
    return f"https://{prefix}k8s-chat-web.baijia.com/auth/login/cas"


def compass_service_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/compass/api/main"


def cas_host_for(url: str) -> str:
    return "test-cas.baijia.com" if _host(url).startswith("test-") else "cas.baijia.com"


def cas_login_url_for_service(target_url: str, service_url: str) -> str:
    login = f"https://{cas_host_for(target_url)}/cas/login"
    return f"{login}?{urlencode({'service': service_url})}"


def _same_host_port_path(left: str, right: str) -> bool:
    left_url = urlparse(left)
    right_url = urlparse(right)
    try:
        return (
            (left_url.hostname or "").lower() == (right_url.hostname or "").lower()
            and left_url.port == right_url.port
            and left_url.path == right_url.path
            and left_url.params == right_url.params
        )
    except ValueError:
        return False


def is_verified_http_callback_service(target_url: str, service_url: str) -> bool:
    """Recognize the only supported HTTP CAS service exception.

    The actual 307/308 upgrade is checked at runtime before any target Cookie is
    sent. Keeping this structural check here lets every caller share one policy.
    """
    target = urlparse(target_url)
    service = urlparse(service_url)
    return (
        target.scheme == "https"
        and bool(target.hostname)
        and service.scheme == "http"
        and bool(service.hostname)
        and _same_host_port_path(target_url, service_url)
    )


def validate_cas_service_url(target_url: str, service_url: str) -> bool:
    """Validate a service URL and return whether it requires the HTTP exception."""
    service = urlparse(service_url)
    if service.scheme == "https" and service.hostname:
        return False
    if is_verified_http_callback_service(target_url, service_url):
        return True
    raise ValueError(
        "CAS service 参数必须是 HTTPS URL；唯一例外是同主机同路径的 HTTP 回调，"
        "且运行时必须以 307 或 308 原样升级到 HTTPS"
    )


# ---------------------------------------------------------------------------
# Cookie jar (ported from the CookieJar in http-cas-login)
# ---------------------------------------------------------------------------

def _default_path(path: str) -> str:
    last = path.rfind("/")
    return "/" if last <= 0 else path[:last]


def _domain_matches(hostname: str, domain: str) -> bool:
    domain = domain.lstrip(".").lower()
    hostname = hostname.lower()
    return hostname == domain or hostname.endswith(f".{domain}")


def parse_set_cookie(value: str, request_url: str) -> Optional[Dict]:
    parts = [part.strip() for part in value.split(";")]
    name_value = parts[0]
    sep = name_value.find("=")
    if sep <= 0:
        return None
    parsed = urlparse(request_url)
    cookie = {
        "name": name_value[:sep],
        "value": name_value[sep + 1:],
        "domain": parsed.hostname,
        "path": _default_path(parsed.path),
        "expires": -1,
        "secure": False,
    }
    for attribute in parts[1:]:
        raw_name, _, raw_value = attribute.partition("=")
        key = raw_name.lower()
        if key == "domain" and raw_value:
            cookie["domain"] = raw_value.lstrip(".")
        elif key == "path" and raw_value:
            cookie["path"] = raw_value
        elif key == "expires" and raw_value:
            try:
                cookie["expires"] = int(parsedate_to_datetime(raw_value).timestamp())
            except (TypeError, ValueError, OverflowError):
                cookie["expires"] = -1
        elif key == "max-age" and raw_value:
            try:
                cookie["expires"] = int(time.time()) + int(raw_value)
            except ValueError:
                pass
        elif key == "secure":
            cookie["secure"] = True
    return cookie


def _status(response) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else getattr(response, "code", 0)
    return status or 0


def _read(response) -> str:
    reader = getattr(response, "read", None)
    if not callable(reader):
        return ""
    try:
        raw = reader()
    except (OSError, ValueError):
        return ""
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else (raw or "")


class CookieJar:
    def __init__(self, opener=None, timeout: float = 30.0):
        self.opener = opener or build_opener(_NoRedirect())
        self.timeout = timeout
        self.cookies: List[Dict] = []

    def cookie_header(self, url: str) -> str:
        parsed = urlparse(url)
        now = time.time()
        pairs = []
        for cookie in self.cookies:
            if not _domain_matches(parsed.hostname or "", cookie["domain"]):
                continue
            if not (parsed.path or "/").startswith(cookie["path"]):
                continue
            if cookie["secure"] and parsed.scheme != "https":
                continue
            if cookie["expires"] != -1 and cookie["expires"] <= now:
                continue
            pairs.append(f"{cookie['name']}={cookie['value']}")
        return "; ".join(pairs)

    def _store(self, response, request_url: str) -> None:
        getter = getattr(response.headers, "get_all", None)
        values = getter("Set-Cookie") if callable(getter) else None
        if not values:
            single = response.headers.get("Set-Cookie")
            values = [single] if single else []
        for value in values:
            cookie = parse_set_cookie(value, request_url)
            if not cookie:
                continue
            self.cookies = [
                existing for existing in self.cookies
                if not (existing["name"] == cookie["name"]
                        and existing["domain"] == cookie["domain"]
                        and existing["path"] == cookie["path"])
            ]
            self.cookies.append(cookie)

    def request(
        self,
        url: str,
        method: str = "GET",
        data=None,
        headers=None,
        send_cookies: bool = True,
        store_cookies: bool = True,
    ):
        request_headers = dict(headers or {})
        if not send_cookies:
            request_headers.pop("Cookie", None)
        cookie_header = self.cookie_header(url) if send_cookies else ""
        if cookie_header:
            request_headers["Cookie"] = cookie_header
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except HTTPError as exc:
            response = exc
        if store_cookies:
            self._store(response, url)
        return response


def cookies_for_host(cookies: List[Dict], hostname: str) -> List[Dict]:
    return [cookie for cookie in cookies if _domain_matches(hostname, cookie["domain"])]


def to_cookie_header(cookies: List[Dict]) -> str:
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)


# ---------------------------------------------------------------------------
# CAS login flow (ported from http-cas-login)
# ---------------------------------------------------------------------------

def _require_location(response, source: str) -> str:
    location = response.headers.get("Location")
    if not location:
        raise RuntimeError(f"{source} 未重定向到 CAS 登录 URL")
    return location


def _matches_http_callback(url: str, service_url: str) -> bool:
    return urlparse(url).scheme == "http" and _same_host_port_path(url, service_url)


def _is_verified_https_upgrade(http_url: str, https_url: str) -> bool:
    source = urlparse(http_url)
    target = urlparse(https_url)
    return (
        target.scheme == "https"
        and _same_host_port_path(http_url, https_url)
        and source.query == target.query
        and source.fragment == target.fragment
    )


def _follow_redirects(
    jar: CookieJar,
    response,
    url: str,
    http_callback_service: Optional[str] = None,
    awaiting_https_upgrade: bool = False,
):
    http_callback_used = awaiting_https_upgrade
    for _ in range(10):
        if awaiting_https_upgrade:
            if _status(response) not in HTTP_UPGRADE_STATUS_CODES:
                raise RuntimeError("HTTP CAS 回调必须以 307 或 308 升级到 HTTPS")
            upgraded_url = urljoin(url, _require_location(response, "HTTP CAS 回调"))
            if not _is_verified_https_upgrade(url, upgraded_url):
                raise RuntimeError("HTTP CAS 回调的 HTTPS 升级改变了主机、端口、路径或查询参数")
            url = upgraded_url
            response = jar.request(url)
            return response
        if _status(response) not in REDIRECT_STATUS_CODES:
            return response
        next_url = urljoin(url, _require_location(response, "CAS 服务"))
        if urlparse(next_url).scheme == "http":
            if (
                not http_callback_service
                or http_callback_used
                or not _matches_http_callback(next_url, http_callback_service)
            ):
                raise RuntimeError("CAS 重定向到未验证的 HTTP 回调")
            url = next_url
            response = jar.request(url, send_cookies=False, store_cookies=False)
            awaiting_https_upgrade = True
            http_callback_used = True
            continue
        if urlparse(next_url).scheme != "https":
            raise RuntimeError("CAS 重定向必须使用 HTTPS")
        url = next_url
        response = jar.request(url)
    if _status(response) in REDIRECT_STATUS_CODES:
        raise RuntimeError("CAS 重定向超过 10 次")
    return response


def _complete_cas_login(
    jar: CookieJar,
    cas_login_url: str,
    username: str,
    password: str,
    http_callback_service: Optional[str] = None,
) -> None:
    jar.request(cas_login_url)
    login = urlparse(cas_login_url)
    search = f"?{login.query}" if login.query else ""
    cas_api_url = f"{login.scheme}://{login.netloc}/cas/bg/login{search}"

    initialization = json.loads(_read(jar.request(cas_api_url, method="POST", data=b"")) or "{}")
    fields = initialization.get("data") or {}
    required = ("lt", "token", "execution", "_eventId")
    if not initialization.get("success") or not all(fields.get(key) for key in required):
        raise RuntimeError("CAS 未返回登录所需字段")

    form = urlencode({
        "lt": fields["lt"],
        "token": fields["token"],
        "execution": fields["execution"],
        "_eventId": fields["_eventId"],
        "username": username,
        "password": password,
    }).encode("utf-8")
    login_response = jar.request(
        cas_api_url,
        method="POST",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if _status(login_response) >= 400:
        raise RuntimeError(f"CAS 登录失败（HTTP {_status(login_response)}）")
    login_body = json.loads(_read(login_response) or "{}")
    nxt = (login_body.get("data") or {}).get("next")
    if not login_body.get("success") or not nxt:
        raise RuntimeError("CAS 登录未返回后续跳转 URL（账号或密码可能有误）")

    completed_url = urljoin(cas_api_url, nxt)
    starts_http_callback = bool(
        http_callback_service and _matches_http_callback(completed_url, http_callback_service)
    )
    if urlparse(completed_url).scheme == "http" and not starts_http_callback:
        raise RuntimeError("CAS 登录返回未验证的 HTTP 回调")
    response = jar.request(
        completed_url,
        send_cookies=not starts_http_callback,
        store_cookies=not starts_http_callback,
    )
    _follow_redirects(
        jar,
        response,
        completed_url,
        http_callback_service=http_callback_service,
        awaiting_https_upgrade=starts_http_callback,
    )


def _resolve_service_url(target_url: str, cas_service_url: Optional[str]) -> Optional[str]:
    if cas_service_url:
        return cas_service_url
    if is_athena(target_url):
        return athena_service_url(target_url)
    if is_compass(target_url):
        return compass_service_url(target_url)
    return None


def login(
    target_url: str,
    username: str,
    password: str,
    cas_service_url: Optional[str] = None,
    opener=None,
    timeout: float = 30.0,
) -> str:
    """Log in via CAS and return the Cookie header for the target host."""
    parsed = urlparse(target_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("target_url 必须是 HTTPS URL")
    jar = CookieJar(opener=opener, timeout=timeout)

    if is_internal_ad(target_url):
        auth_url = f"{parsed.scheme}://{parsed.netloc}/activity-ad/ac/getAuth"
        initial = jar.request(auth_url, method="POST", data=b"")
        cas_login_url = _require_location(initial, "Internal AD 授权")
        _complete_cas_login(jar, cas_login_url, username, password)
    else:
        service_url = _resolve_service_url(target_url, cas_service_url)
        if not service_url:
            raise RuntimeError(
                "该主机没有内置 CAS 服务入口，请提供 cas_service_url（可由可信 CAS 重定向或 code:700 发现）"
            )
        requires_http_upgrade = validate_cas_service_url(target_url, service_url)
        cas_login_url = cas_login_url_for_service(target_url, service_url)
        _complete_cas_login(
            jar,
            cas_login_url,
            username,
            password,
            http_callback_service=service_url if requires_http_upgrade else None,
        )
        jar.request(target_url)

    selected = cookies_for_host(jar.cookies, parsed.hostname)
    if not selected:
        raise RuntimeError(f"{parsed.hostname} 未下发任何 Cookie")
    return to_cookie_header(selected)
