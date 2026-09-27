#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "call_api.py"

SAMPLE_CURL = r"""curl 'https://test-mi.gaotu100.com/course-center/b/course/list' \
  -H 'accept: application/json' \
  -H 'b_client: OES' \
  -H 'content-type: application/json;charset=UTF-8' \
  -b 'SESSION=abc; JSESSIONID=def; uid=8554' \
  -H 'origin: https://test-mi.gaotu100.com' \
  -H 'referer: https://test-mi.gaotu100.com/ark/app-goods/CourseManagePro/list' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-fetch-site: same-origin' \
  -H 'uid: 8554' \
  --data-raw '{"pager":{"current":1,"pageSize":10,"pageNum":1},"fullFuzzyText":"1v1"}'"""


def load_module():
    spec = importlib.util.spec_from_file_location("call_api", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CallApiTest(unittest.TestCase):
    def test_call_api_script_exists(self):
        self.assertTrue(SCRIPT_PATH.is_file())

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_parse_curl_extracts_url_method_body_and_headers(self):
        call_api = load_module()

        parsed = call_api.parse_curl(SAMPLE_CURL)

        self.assertEqual("https://test-mi.gaotu100.com/course-center/b/course/list", parsed["url"])
        self.assertEqual("POST", parsed["method"])
        self.assertIn('"fullFuzzyText":"1v1"', parsed["body"])
        header_names = {name.lower() for name, _ in parsed["headers"]}
        self.assertIn("b_client", header_names)
        self.assertIn("content-type", header_names)

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_select_headers_is_minimal_by_default(self):
        call_api = load_module()
        parsed = call_api.parse_curl(SAMPLE_CURL)

        forwarded, dropped = call_api.select_headers(parsed["headers"])

        forwarded_names = {name.lower() for name in dict(forwarded)}
        dropped_names = {name.lower() for name in dropped}
        # Only content-type survives the allowlist; everything else is dropped.
        self.assertEqual({"content-type"}, forwarded_names)
        for noise in ("b_client", "accept", "uid", "origin", "referer", "sec-fetch-site", "sec-ch-ua-mobile"):
            self.assertIn(noise, dropped_names)

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_keep_header_adds_a_needed_header_back(self):
        call_api = load_module()
        parsed = call_api.parse_curl(SAMPLE_CURL)

        forwarded, _ = call_api.select_headers(parsed["headers"], keep=("b_client",))

        forwarded_names = {name.lower() for name in dict(forwarded)}
        self.assertEqual({"content-type", "b_client"}, forwarded_names)

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_side_effecting_method_refuses_to_send_without_confirmation(self):
        call_api = load_module()
        with tempfile.TemporaryDirectory() as directory:
            curl_file = Path(directory) / "req.curl"
            curl_file.write_text(
                "curl 'https://test-mi.gaotu100.com/x/delete' -X DELETE",
                encoding="utf-8",
            )
            sent = mock.Mock()
            with mock.patch.object(call_api, "obtain_cookie", sent), \
                 mock.patch.object(call_api, "send_request", sent):
                code = call_api.main(["--curl-file", str(curl_file)])

        self.assertEqual(3, code)
        sent.assert_not_called()  # no cookie fetch and no network send happened

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_is_auth_failure_detects_401_and_code_700(self):
        call_api = load_module()

        self.assertTrue(call_api.is_auth_failure(401, ""))
        self.assertTrue(call_api.is_auth_failure(200, '{"code":700,"msg":"no auth"}'))
        self.assertFalse(call_api.is_auth_failure(200, '{"code":0,"data":[]}'))
        self.assertFalse(call_api.is_auth_failure(200, "not json"))

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_should_retry_gates_side_effecting_methods(self):
        call_api = load_module()

        self.assertTrue(call_api.should_retry("GET", assume_idempotent=False, no_retry=False))
        self.assertFalse(call_api.should_retry("POST", assume_idempotent=False, no_retry=False))
        self.assertTrue(call_api.should_retry("POST", assume_idempotent=True, no_retry=False))
        self.assertFalse(call_api.should_retry("GET", assume_idempotent=True, no_retry=True))

    @unittest.skipUnless(SCRIPT_PATH.is_file(), "call_api.py has not been implemented")
    def test_send_request_sets_cookie_and_returns_body(self):
        call_api = load_module()
        captured = {}

        def fake_open(request, timeout=None):
            captured["cookie"] = request.get_header("Cookie")
            captured["method"] = request.get_method()
            captured["body"] = request.data
            return SimpleNamespace(status=200, read=lambda: b'{"code":0,"data":"ok"}')

        opener = SimpleNamespace(open=fake_open)

        status, text = call_api.send_request(
            url="https://test-mi.gaotu100.com/course-center/b/course/list",
            method="POST",
            headers=[("b_client", "OES")],
            body='{"fullFuzzyText":"1v1"}',
            cookie_header="SESSION=fresh",
            timeout=30.0,
            opener=opener,
        )

        self.assertEqual(200, status)
        self.assertIn('"data":"ok"', text)
        self.assertEqual("SESSION=fresh", captured["cookie"])
        self.assertEqual("POST", captured["method"])
        self.assertEqual(b'{"fullFuzzyText":"1v1"}', captured["body"])


if __name__ == "__main__":
    unittest.main()
