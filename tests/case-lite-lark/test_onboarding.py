"""Exercise onboarding and reads through real entry points and a fake CLI executable."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "case-lite-lark" / "scripts"
FAKE = r'''
import json, os, pathlib, sys, time
args = sys.argv[1:]
root = pathlib.Path(os.environ['FAKE_LARK_STATE'])
with (root/'calls.jsonl').open('a') as f:
    f.write(json.dumps(args)+'\n')
profile = args[args.index('--profile')+1] if '--profile' in args else 'platform'
if '--profile' in args:
    i=args.index('--profile'); del args[i:i+2]
profiles_path = root/'profiles.json'
profiles = json.loads(profiles_path.read_text()) if profiles_path.exists() else {}
def fail(subtype, message):
    print(json.dumps({'ok':False,'error':{'type':'config','subtype':subtype,'message':message,'hint':'run lark-cli config init --new'}}),file=sys.stderr)
    sys.exit(1)
if args[:2] == ['profile','list']:
    pause=root/'pause-list'
    if pause.exists():
        pause.unlink(); (root/'list-started').touch()
        deadline=time.monotonic()+10
        while not (root/'release-list').exists() and time.monotonic()<deadline:time.sleep(.02)
    if (root/'broken').exists(): fail('failed_precondition','broken config')
    print(json.dumps([{'name':name,'appId':app['appId'],'brand':app.get('brand','feishu'),'active':i==0} for i,(name,app) in enumerate(profiles.items())]))
elif args[:2] == ['config','show']:
    if (root/'broken').exists(): fail('invalid_config','broken config')
    if profile not in profiles:
        fail('not_configured','profile not found')
    print(json.dumps({'workspace':'local','profileSource':'flag','appId':profiles[profile]['appId'],'appSecret':'****','profile':profile,'brand':profiles[profile].get('brand','feishu'),'lang':'','dpopMode':'preferred','users':'(no logged-in users)'}))
elif args[:2] == ['config','init']:
    assert '--new' not in args and '--app-secret-stdin' in args
    assert '--name' in args
    name=args[args.index('--name')+1]
    secret=sys.stdin.readline().strip()
    assert secret == 'synthetic-team-secret'
    profiles[name]={'appId':args[args.index('--app-id')+1],'users':[]}
    profiles_path.write_text(json.dumps(profiles))
    if (root/'probe-fails').exists(): fail('access_denied','probe failed after save')
    print(json.dumps({'appId':profiles[name]['appId'],'appSecret':'****','brand':'feishu'}))
elif args[:2] == ['auth','status']:
    print(json.dumps({'appId':profiles.get(profile,{}).get('appId',''),'brand':'feishu','credentialSource':'local','defaultAs':'auto','identity':'bot','identities':{'bot':{'status':'ready','available':True},'user':{'status':'missing','available':False}},'note':'User identity is missing'}))
elif args[:2] == ['auth','login']:
    if '--device-code' in args:
        print(json.dumps({'success':True,'profile':profile}))
    else:
        assert '--no-wait' in args and '--json' in args
        print(json.dumps({'verification_url':'https://example.invalid/authorize','device_code':'synthetic-device-code','profile':profile}))
elif args[:2] == ['auth','qrcode']:
    pathlib.Path(args[args.index('--output')+1]).write_bytes(b'fake-png')
    print(json.dumps({'path':args[args.index('--output')+1],'profile':profile}))
elif args[:2] == ['api','GET']:
    if (root/'unconfigured').exists():fail('not_configured','no app configured')
    assert '--as' in args and args[args.index('--as')+1]=='user'
    data={'items':[],'has_more':False} if args[2].endswith('/blocks') else {'document':{'document_id':'doc','title':'test','revision_id':1}}
    print(json.dumps({'ok':True,'identity':'user','data':data,'profile':profile}))
elif args == ['--version']:
    print('lark-cli version 1.0.98')
elif '--help' in args:
    print('--params --node-token --page-token --file-token --output --output-type')
else:
    fail('invalid_argument','unexpected argv')
'''


class OnboardingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        binary = self.root / "bin/lark-cli"
        binary.parent.mkdir()
        binary.write_text(f"#!{sys.executable}\n" + FAKE)
        binary.chmod(0o755)
        self.settings = self.root / "account/runtime.json"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("CASE_LITE_LARK_", "LARKSUITE_CLI_"))}
        self.env.update(PATH=str(binary.parent) + os.pathsep + self.env.get("PATH", ""),
                        CASE_LITE_LARK_SETTINGS=str(self.settings), FAKE_LARK_STATE=str(self.root),
                        LARKSUITE_CLI_CONFIG_DIR=str(self.root / "cli-config"))
        self.team = self.root / "team-app.json"
        self.team.write_text(json.dumps({"app_id": "cli_synthetic123", "app_secret": "synthetic-team-secret", "brand": "feishu"}))

    def run_script(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def setup_local(self):
        return self.run_script("setup_lark.py", "local", "--config-file", str(self.team))

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def profiles(self, data):
        (self.root / "profiles.json").write_text(json.dumps(data))

    def test_local_imports_existing_app_once_and_preserves_other_users(self):
        self.profiles({"personal": {"appId": "cli_personal", "users": ["alice"]}})
        result = self.setup_local()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)["data"]
        self.assertEqual(data["state"], "initialized")
        profiles = json.loads((self.root / "profiles.json").read_text())
        self.assertEqual(profiles["personal"]["users"], ["alice"])
        self.assertEqual(profiles["case-lite-team"]["appId"], "cli_synthetic123")
        self.assertNotIn("synthetic-team-secret", result.stdout + result.stderr + self.settings.read_text())
        self.assertTrue(all("--new" not in call for call in self.calls()))
        profiles["case-lite-team"]["users"] = ["bob"]
        self.profiles(profiles)
        again = self.setup_local()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(json.loads(again.stdout)["data"]["state"], "reused")
        self.assertEqual(json.loads((self.root / "profiles.json").read_text())["case-lite-team"]["users"], ["bob"])
        self.assertEqual(sum("init" in call for call in self.calls()), 1)

    def test_different_app_in_same_profile_is_not_overwritten(self):
        self.profiles({"case-lite-team": {"appId": "cli_other", "users": ["alice"]}})
        before = (self.root / "profiles.json").read_bytes()
        result = self.setup_local()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.root / "profiles.json").read_bytes(), before)
        self.assertFalse(self.settings.exists())
        self.assertTrue(all("init" not in call for call in self.calls()))

    def test_invalid_existing_config_does_not_trigger_initialization(self):
        (self.root / "broken").touch()
        result = self.setup_local()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.settings.exists())
        self.assertTrue(all("init" not in call for call in self.calls()))

    def test_existing_app_under_another_name_is_reused_without_rewriting_secret(self):
        self.profiles({"existing-team": {"appId": "cli_synthetic123", "users": ["alice"]}})
        before = (self.root / "profiles.json").read_bytes()
        result = self.setup_local()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["data"]["profile"], "existing-team")
        self.assertEqual((self.root / "profiles.json").read_bytes(), before)
        self.assertTrue(all("init" not in call for call in self.calls()))

    def test_reused_dotted_or_localized_profile_remains_usable_for_status(self):
        for name in ["team.prod", "团队应用"]:
            with self.subTest(profile=name):
                self.profiles({name: {"appId": "cli_synthetic123", "users": ["alice"]}})
                result = self.setup_local()
                self.assertEqual(result.returncode, 0, result.stderr)
                status = self.run_script("setup_lark.py", "status")
                self.assertEqual(status.returncode, 0, status.stderr)
                self.assertEqual(self.calls()[-1][:2], ["--profile", name])

    def test_probe_failure_after_save_does_not_claim_success_or_retry(self):
        (self.root / "probe-fails").touch()
        result = self.setup_local()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.settings.exists())
        self.assertTrue((self.root / "profiles.json").exists())
        self.assertEqual(sum("init" in call for call in self.calls()), 1)

    def test_platform_default_and_explicit_override_preserve_bound_context(self):
        for override in [False, True]:
            with self.subTest(override=override):
                if override:
                    self.settings.parent.mkdir(parents=True, exist_ok=True)
                    self.settings.write_text('{"mode":"local","profile":"case-lite-team"}')
                    self.env["CASE_LITE_LARK_MODE"] = "platform"
                self.env["LARKSUITE_CLI_PROFILE"] = "platform-bound"
                result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(all("--profile" not in call and "init" not in call for call in self.calls()))

    def test_platform_configuration_error_only_reports_recovery(self):
        self.env["CASE_LITE_LARK_MODE"] = "platform"
        (self.root / "unconfigured").touch()
        result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
        self.assertEqual(result.returncode, 1)
        error = json.loads(result.stderr)["error"]
        self.assertEqual(error["subtype"], "not_configured")
        self.assertEqual(error.get("case_lite_mode"), "platform")
        self.assertIn("平台", error.get("case_lite_hint", ""))
        self.assertNotIn("--new", error.get("hint", ""))
        self.assertTrue(all("init" not in call and "login" not in call for call in self.calls()))

    def test_platform_credential_provider_takes_precedence_over_saved_local_settings(self):
        self.settings.parent.mkdir()
        self.settings.write_text('{"mode":"local","profile":"case-lite-team"}')
        self.env["LARKSUITE_CLI_AUTH_PROXY"] = "http://127.0.0.1:16384"
        result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all("--profile" not in call for call in self.calls()))

    def test_explicit_platform_mode_refuses_local_import(self):
        self.env["CASE_LITE_LARK_MODE"] = "platform"
        result = self.setup_local()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.settings.exists())

    def test_invalid_brand_is_a_structured_error_before_any_cli_call(self):
        for brand in [[], {}]:
            with self.subTest(brand=brand):
                self.team.write_text(json.dumps({"app_id": "cli_synthetic123", "app_secret": "synthetic-team-secret", "brand": brand}))
                result = self.setup_local()
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(json.loads(result.stderr)["ok"])
                self.assertEqual(self.calls(), [])

    def test_concurrent_imports_cannot_overwrite_same_profile(self):
        (self.root / "pause-list").touch()
        first = subprocess.Popen([sys.executable, "-B", str(SCRIPTS / "setup_lark.py"), "local", "--config-file", str(self.team)],
                                 cwd=self.root, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: first.kill() if first.poll() is None else None)
        deadline = time.monotonic() + 5
        while not (self.root / "list-started").exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue((self.root / "list-started").exists())
        other = self.root / "other-team.json"
        other.write_text(json.dumps({"app_id": "cli_other", "app_secret": "synthetic-team-secret", "brand": "feishu"}))
        second = self.run_script("setup_lark.py", "local", "--config-file", str(other))
        (self.root / "release-list").touch()
        stdout, stderr = first.communicate(timeout=10)
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertEqual(first.returncode, 0, stderr)
        profiles = json.loads((self.root / "profiles.json").read_text())
        self.assertEqual(profiles["case-lite-team"]["appId"], "cli_synthetic123")
        self.assertEqual(sum("init" in call for call in self.calls()), 1)

    def test_local_reads_and_auth_resume_all_use_saved_profile(self):
        self.assertEqual(self.setup_local().returncode, 0)
        result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        start = self.run_script("setup_lark.py", "login", "--domain", "docs", "--domain", "drive")
        self.assertEqual(start.returncode, 0, start.stderr)
        self.assertEqual(json.loads(start.stdout)["device_code"], "synthetic-device-code")
        resume = self.run_script("setup_lark.py", "login", "--device-code", "synthetic-device-code")
        self.assertEqual(resume.returncode, 0, resume.stderr)
        status = self.run_script("setup_lark.py", "status", "--verify")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertFalse(json.loads(status.stdout)["identities"]["user"]["available"])
        qr = self.run_script("setup_lark.py", "qrcode", "https://example.invalid/authorize", "--output", "auth.png")
        self.assertEqual(qr.returncode, 0, qr.stderr)
        self.assertTrue((self.root / "auth.png").is_file())
        reads_and_auth = [call for call in self.calls() if "api" in call or "auth" in call]
        self.assertTrue(reads_and_auth)
        self.assertTrue(all(call[:2] == ["--profile", "case-lite-team"] for call in reads_and_auth))

    def test_login_requires_scopes_and_does_not_silently_request_all(self):
        result = self.run_script("setup_lark.py", "login")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_invalid_settings_do_not_fall_back_to_platform_identity(self):
        self.settings.parent.mkdir()
        self.settings.write_text('{"mode":"local","profile":""}')
        result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_explicit_local_mode_requires_prior_onboarding(self):
        self.env["CASE_LITE_LARK_MODE"] = "local"
        result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])

    def test_doctor_reports_selected_runtime_without_auth_calls(self):
        self.assertEqual(self.setup_local().returncode, 0)
        result = self.run_script("feishu_docs.py", "doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)["data"]
        self.assertEqual(data["mode"], "local")
        self.assertEqual(data["profile"], "case-lite-team")
        self.assertFalse(data["auth_verified"])
        self.assertTrue(all("auth" not in call for call in self.calls()))

    def test_first_use_doctor_requests_runtime_choice_without_auth_or_config_calls(self):
        result = self.run_script("feishu_docs.py", "doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)["data"]
        self.assertEqual(data["mode"], "auto")
        self.assertTrue(data["needs_mode_choice"])
        self.assertFalse(data["auth_verified"])
        self.assertTrue(all("--help" in call or call == ["--version"] for call in self.calls()))
        self.assertFalse(self.settings.exists())

    def test_first_use_config_error_offers_both_local_and_platform_paths(self):
        (self.root / "unconfigured").touch()
        result = self.run_script("feishu_docs.py", "outline", "https://example.feishu.cn/docx/doc", "--output", "outline.json")
        self.assertEqual(result.returncode, 1)
        error = json.loads(result.stderr)["error"]
        self.assertEqual(error["case_lite_mode"], "auto")
        self.assertTrue(error["needs_mode_choice"])
        self.assertIn("本地", error["hint"])
        self.assertIn("平台", error["hint"])
        self.assertIn("确认", error["hint"])
        self.assertNotIn("--new", error["hint"])
        self.assertTrue(all("init" not in call and "login" not in call for call in self.calls()))

    def test_first_use_login_does_not_authorize_an_unknown_app_context(self):
        result = self.run_script("setup_lark.py", "login", "--domain", "docs")
        self.assertEqual(result.returncode, 1)
        self.assertIn("确认", json.loads(result.stderr)["error"]["message"])
        self.assertEqual(self.calls(), [])

    def test_first_use_missing_cli_still_gives_both_runtime_choices(self):
        (self.root / "bin/lark-cli").unlink()
        self.env["PATH"] = str(self.root / "bin")
        result = self.run_script("feishu_docs.py", "doctor")
        self.assertEqual(result.returncode, 1)
        error = json.loads(result.stderr)["error"]
        self.assertTrue(error.get("needs_mode_choice"))
        self.assertIn("本地", error["message"])
        self.assertIn("平台", error["message"])


if __name__ == "__main__":
    unittest.main()
