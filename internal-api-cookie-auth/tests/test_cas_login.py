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


if __name__ == "__main__":
    unittest.main()
