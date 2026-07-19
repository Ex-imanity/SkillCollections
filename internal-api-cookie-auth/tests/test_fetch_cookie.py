#!/usr/bin/env python3
import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from unittest import mock


SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "fetch_cookie.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_cookie", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FetchCookieTest(unittest.TestCase):
    def test_fetch_cookie_script_exists(self):
        self.assertTrue(SCRIPT_PATH.is_file())

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "fetch_cookie.py has not been implemented")
    def test_fetches_cookie_without_passing_password_as_a_command_argument(self):
        fetch_cookie = load_module()
        runner = mock.Mock(
            return_value=SimpleNamespace(
                returncode=0,
                stdout='{"cookieHeader": "SESSION=fresh; ROLE=operator"}',
                stderr="",
            )
        )

        cookie = fetch_cookie.fetch_cookie(
            url="https://internal-ad.gaotu100.com/welcome",
            username="operator",
            password="secret",
            password_env="SITE_PASSWORD",
            cookie_tool_dir="/opt/baijia-cookie",
            timeout=30.0,
            runner=runner,
        )

        self.assertEqual("SESSION=fresh; ROLE=operator", cookie)
        command = runner.call_args.args[0]
        environment = runner.call_args.kwargs["env"]
        self.assertNotIn("secret", command)
        self.assertEqual("secret", environment["SITE_PASSWORD"])
        self.assertEqual("/opt/baijia-cookie", runner.call_args.kwargs["cwd"])

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "fetch_cookie.py has not been implemented")
    def test_writes_cookie_to_a_mode_0600_file(self):
        fetch_cookie = load_module()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cookie.txt"

            fetch_cookie.write_cookie_file(output, "SESSION=fresh")

            self.assertEqual("SESSION=fresh", output.read_text(encoding="utf-8"))
            self.assertEqual(0o600, stat.S_IMODE(os.stat(output).st_mode))

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "fetch_cookie.py has not been implemented")
    def test_allows_an_unknown_https_target_to_be_probed(self):
        fetch_cookie = load_module()

        self.assertEqual("https://service.example.com/api/status", fetch_cookie.validate_target_url("https://service.example.com/api/status"))

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "fetch_cookie.py has not been implemented")
    def test_discovers_service_url_from_a_trusted_cas_redirect(self):
        fetch_cookie = load_module()
        target = "https://service.example.com/api/status"
        service_url = "https://service.example.com/auth/login/cas"
        redirect = (
            "https://cas.baijia.com/cas/login?service="
            "https%3A%2F%2Fservice.example.com%2Fauth%2Flogin%2Fcas"
        )
        opener = SimpleNamespace(open=mock.Mock(side_effect=HTTPError(target, 302, "Found", {"Location": redirect}, None)))

        discovered = fetch_cookie.discover_cas_service(target, timeout=30.0, opener=opener)

        self.assertEqual(service_url, discovered)

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "fetch_cookie.py has not been implemented")
    def test_rejects_a_redirect_to_an_untrusted_login_host(self):
        fetch_cookie = load_module()
        target = "https://service.example.com/api/status"
        redirect = "https://login.example.com/cas/login?service=https%3A%2F%2Fservice.example.com%2Fauth%2Flogin%2Fcas"
        opener = SimpleNamespace(open=mock.Mock(side_effect=HTTPError(target, 302, "Found", {"Location": redirect}, None)))

        with self.assertRaisesRegex(ValueError, "可信 CAS"):
            fetch_cookie.discover_cas_service(target, timeout=30.0, opener=opener)

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "fetch_cookie.py has not been implemented")
    def test_passes_discovered_service_url_to_the_cookie_tool(self):
        fetch_cookie = load_module()
        runner = mock.Mock(
            return_value=SimpleNamespace(
                returncode=0,
                stdout='{"cookieHeader": "SESSION=fresh"}',
                stderr="",
            )
        )

        fetch_cookie.fetch_cookie(
            url="https://service.example.com/api/status",
            username="operator",
            password="secret",
            password_env="SITE_PASSWORD",
            cookie_tool_dir="/opt/baijia-cookie",
            timeout=30.0,
            cas_service_url="https://service.example.com/auth/login/cas",
            runner=runner,
        )

        self.assertEqual(
            ["--cas-service-url", "https://service.example.com/auth/login/cas"],
            runner.call_args.args[0][-2:],
        )


if __name__ == "__main__":
    unittest.main()
