#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "cas_login.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cas_login", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeHeaders:
    def __init__(self, data):
        self._data = {k.lower(): (v if isinstance(v, list) else [v]) for k, v in data.items()}

    def get(self, name, default=None):
        values = self._data.get(name.lower())
        return values[0] if values else default

    def get_all(self, name, default=None):
        return self._data.get(name.lower(), default)


class FakeResp:
    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self.headers = FakeHeaders(headers or {})
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")

    def read(self):
        return self._body


class ScriptedOpener:
    """Reproduces the CAS server dialog for an internal-ad login."""

    def __init__(self):
        self.calls = []

    def open(self, request, timeout=None):
        url = request.full_url
        method = request.get_method()
        data = request.data
        self.calls.append((method, url, data))
        path = urlparse(url).path
        if path == "/activity-ad/ac/getAuth":
            return FakeResp(302, {"Location": "https://test-cas.baijia.com/cas/login?service=https%3A%2F%2Ftest-internal-ad.gaotu100.com%2Fwelcome"})
        if path == "/cas/login":
            return FakeResp(200, {"Set-Cookie": "CASTGC=tgc; Domain=test-cas.baijia.com; Path=/"}, b"login")
        if path == "/cas/bg/login":
            if not data:  # first POST initializes the login fields
                return FakeResp(200, {}, '{"success":true,"data":{"lt":"L","token":"T","execution":"E","_eventId":"submit"}}')
            return FakeResp(200, {}, '{"success":true,"data":{"next":"https://test-internal-ad.gaotu100.com/activity-ad/done"}}')
        if path == "/activity-ad/done":
            return FakeResp(200, {"Set-Cookie": "SESSION=fresh; Path=/"}, b"ok")
        return FakeResp(200, {}, b"{}")


class HttpUpgradeOpener:
    """Models the one permitted CAS callback: HTTP ticket -> HTTPS 307 upgrade."""

    def __init__(
        self,
        upgrade_status=307,
        upgrade_location=None,
        https_callback_status=200,
        https_callback_location=None,
    ):
        self.calls = []
        self.upgrade_status = upgrade_status
        self.upgrade_location = upgrade_location
        self.https_callback_status = https_callback_status
        self.https_callback_location = https_callback_location

    def open(self, request, timeout=None):
        url = request.full_url
        self.calls.append((request.get_method(), url, request.get_header("Cookie")))
        parsed = urlparse(url)
        if parsed.hostname == "cas.baijia.com" and parsed.path == "/cas/login":
            return FakeResp(200, {"Set-Cookie": "CASTGC=tgc; Domain=cas.baijia.com; Path=/"}, b"login")
        if parsed.hostname == "cas.baijia.com" and parsed.path == "/cas/bg/login":
            if request.data:
                return FakeResp(200, {}, '{"success":true,"data":{"next":"https://cas.baijia.com/cas/continue"}}')
            return FakeResp(200, {}, '{"success":true,"data":{"lt":"L","token":"T","execution":"E","_eventId":"submit"}}')
        if parsed.hostname == "cas.baijia.com" and parsed.path == "/cas/continue":
            return FakeResp(302, {"Location": "http://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth?ticket=ST-1"})
        if parsed.scheme == "http" and parsed.hostname == "uanalysis.baijia.com":
            location = self.upgrade_location or "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth?ticket=ST-1"
            return FakeResp(self.upgrade_status, {"Location": location, "Set-Cookie": "SESSION=untrusted; Path=/"})
        if parsed.scheme == "https" and parsed.hostname == "uanalysis.baijia.com":
            headers = {"Set-Cookie": "SESSION=fresh; Path=/; Secure"}
            if self.https_callback_location:
                headers["Location"] = self.https_callback_location
            return FakeResp(self.https_callback_status, headers, b"ok")
        raise AssertionError(f"unexpected request: {url}")


class CasLoginConfigTest(unittest.TestCase):
    def test_host_classification(self):
        cas = load_module()
        self.assertTrue(cas.is_internal_ad("https://test-internal-ad.gaotu100.com/x"))
        self.assertTrue(cas.is_internal_ad("https://internal-ad.gaotu100.com/x"))
        self.assertFalse(cas.is_internal_ad("https://mi.gaotu100.com/x"))
        self.assertTrue(cas.is_athena("https://test-athena.baijia.com/x"))
        self.assertTrue(cas.is_compass("https://dis.baijia.com/x"))
        self.assertFalse(cas.has_builtin_service("https://test-mi.gaotu100.com/x"))

    def test_service_url_derivation(self):
        cas = load_module()
        self.assertEqual("https://k8s-chat-web.baijia.com/auth/login/cas", cas.athena_service_url("https://athena.baijia.com/x"))
        self.assertEqual("https://test-k8s-chat-web.baijia.com/auth/login/cas", cas.athena_service_url("https://test-athena.baijia.com/x"))
        self.assertEqual("https://dis.baijia.com/compass/api/main", cas.compass_service_url("https://dis.baijia.com/x"))

    def test_cas_login_url_picks_env_matched_cas_host(self):
        cas = load_module()
        prod = cas.cas_login_url_for_service("https://mi.gaotu100.com/x", "https://mi.gaotu100.com/x")
        test = cas.cas_login_url_for_service("https://test-mi.gaotu100.com/x", "https://test-mi.gaotu100.com/x")
        self.assertTrue(prod.startswith("https://cas.baijia.com/cas/login?service="))
        self.assertTrue(test.startswith("https://test-cas.baijia.com/cas/login?service="))


class CookieJarTest(unittest.TestCase):
    def test_parse_set_cookie_defaults_and_attributes(self):
        cas = load_module()
        cookie = cas.parse_set_cookie("SESSION=abc; Path=/; Secure", "https://host.example.com/a/b")
        self.assertEqual("SESSION", cookie["name"])
        self.assertEqual("abc", cookie["value"])
        self.assertEqual("host.example.com", cookie["domain"])
        self.assertEqual("/", cookie["path"])
        self.assertTrue(cookie["secure"])

    def test_cookie_header_filters_by_domain_and_path(self):
        cas = load_module()
        jar = cas.CookieJar(opener=object())
        jar.cookies = [
            {"name": "A", "value": "1", "domain": "host.example.com", "path": "/", "expires": -1, "secure": False},
            {"name": "B", "value": "2", "domain": "other.example.com", "path": "/", "expires": -1, "secure": False},
            {"name": "C", "value": "3", "domain": "host.example.com", "path": "/deep", "expires": -1, "secure": False},
        ]
        header = jar.cookie_header("https://host.example.com/shallow")
        self.assertIn("A=1", header)
        self.assertNotIn("B=2", header)  # wrong domain
        self.assertNotIn("C=3", header)  # wrong path


class CasLoginFlowTest(unittest.TestCase):
    def test_internal_ad_login_returns_only_target_host_cookies(self):
        cas = load_module()
        opener = ScriptedOpener()

        cookie = cas.login(
            "https://test-internal-ad.gaotu100.com/welcome",
            username="operator",
            password="secret",
            opener=opener,
        )

        # Only the target-host cookie is returned; the CAS-domain CASTGC is excluded.
        self.assertEqual("SESSION=fresh", cookie)
        # Credentials went in a POST body, never in a URL.
        form_posts = [data for method, url, data in opener.calls if data and b"password=" in data]
        self.assertTrue(form_posts, "expected a form POST carrying the password")
        self.assertIn(b"username=operator", form_posts[0])
        self.assertTrue(all("secret" not in url for _, url, _ in opener.calls))

    def test_unknown_host_without_service_raises(self):
        cas = load_module()
        with self.assertRaisesRegex(RuntimeError, "cas_service_url"):
            cas.login("https://test-mi.gaotu100.com/x", "operator", "secret", opener=ScriptedOpener())

    def test_verified_http_callback_upgrades_without_sending_a_cookie_to_http(self):
        cas = load_module()
        opener = HttpUpgradeOpener()

        cookie = cas.login(
            "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
            username="operator",
            password="secret",
            cas_service_url="http://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
            opener=opener,
        )

        self.assertEqual("SESSION=fresh", cookie)
        http_callback = next(call for call in opener.calls if call[1].startswith("http://uanalysis.baijia.com/"))
        https_upgrade = next(
            call for call in opener.calls
            if call[1] == "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth?ticket=ST-1"
        )
        self.assertIsNone(http_callback[2])
        self.assertNotIn("untrusted", https_upgrade[2] or "")
        self.assertNotIn("untrusted", cookie)

    def test_rejects_http_callback_when_upgrade_is_not_307_or_308(self):
        cas = load_module()
        opener = HttpUpgradeOpener(upgrade_status=302)

        with self.assertRaisesRegex(RuntimeError, "307 或 308"):
            cas.login(
                "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
                username="operator",
                password="secret",
                cas_service_url="http://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
                opener=opener,
            )

    def test_rejects_http_callback_when_upgrade_changes_the_ticket_query(self):
        cas = load_module()
        opener = HttpUpgradeOpener(
            upgrade_location="https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth?ticket=ST-2"
        )

        with self.assertRaisesRegex(RuntimeError, "查询参数"):
            cas.login(
                "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
                username="operator",
                password="secret",
                cas_service_url="http://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
                opener=opener,
            )

    def test_rejects_http_service_when_it_changes_the_target_path(self):
        cas = load_module()

        with self.assertRaisesRegex(ValueError, "CAS service 参数"):
            cas.login(
                "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
                username="operator",
                password="secret",
                cas_service_url="http://uanalysis.baijia.com/other",
                opener=HttpUpgradeOpener(),
            )

    def test_stops_after_the_verified_https_upgrade(self):
        cas = load_module()
        opener = HttpUpgradeOpener(
            https_callback_status=302,
            https_callback_location="https://other.example.com/untrusted",
        )

        cookie = cas.login(
            "https://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
            username="operator",
            password="secret",
            cas_service_url="http://uanalysis.baijia.com/uanalysis-template/api/cas/getAuth",
            opener=opener,
        )

        self.assertEqual("SESSION=fresh", cookie)
        self.assertFalse(any("other.example.com" in url for _, url, _ in opener.calls))


if __name__ == "__main__":
    unittest.main()
