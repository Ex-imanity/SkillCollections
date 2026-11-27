"""Source CLI wiring from either primary to a local fake Codex reviewer."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[2] / "skills" / "cross-agent-review"


@unittest.skipIf(os.name == "nt", "POSIX executable fixture")
class PrimaryCompatibilityTests(unittest.TestCase):
    def run_source_cli(self, primary):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "bin" / "codex"
            executable.parent.mkdir()
            executable.write_text("#!" + sys.executable + "\n" + '''import json, os, pathlib, sys
args=sys.argv[1:]
assert args[0]=='exec'
if '--help' in args:
    print('SESSION_ID --json --output-last-message --model'); sys.exit(0)
prompt=sys.stdin.read()
assert 'Review execution contract' in prompt
assert 'Review the fixture' in prompt
target=pathlib.Path(args[args.index('-C')+1])
primary=(
    'claude' if os.environ.get('CLAUDECODE')=='1'
    else 'antigravity' if os.environ.get('ANTIGRAVITY_CONVERSATION_ID')
    else 'grok'
)
(target/'observed-primary.json').write_text(json.dumps({'primary':primary}))
pathlib.Path(args[args.index('--output-last-message')+1]).write_text('APPROVE\\nFixture checked.')
print(json.dumps({'type':'thread.started','thread_id':'6af477c9-c158-4eac-9f37-ae0054718c0d'}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}))
''')
            executable.chmod(0o755)
            request = root / "request.md"
            request.write_text("Review the fixture without modifying it.")
            env = {k: v for k, v in os.environ.items() if not k.startswith(
                ("CLAUDE", "GROK", "ANTIGRAVITY", "AGY_", "ANTHROPIC_", "OPENAI_", "XAI_", "GEMINI_", "GOOGLE_"))}
            env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
            if primary == "claude":
                env.update(CLAUDECODE="1", CLAUDE_PROJECT_DIR=str(root))
            elif primary == "antigravity":
                env.update(ANTIGRAVITY_CONVERSATION_ID="16ab4f6c-9daf-4fef-975b-7a7e3197440a", AGY_SESSION_ID="agy-fixture")
            else:
                env.update(GROK_WORKSPACE_ROOT=str(root), GROK_SESSION_ID="fixture-primary")
            args = [sys.executable, "-B", "-m", "scripts.to_codex", "--request-file", str(request),
                    "--cd", str(root), "--handoff-dir", str(root / "handoff"),
                    "--marker-path", str(root / "rounds.json"), "--gate-id", "reverse-test",
                    "--artifact-key", "fixture", "--cost-log", str(root / "cost.jsonl"),
                    "--output", str(root / "review.md"), "--settings", str(root / "absent-settings"),
                    "--timeout-seconds", "3"]
            result = subprocess.run(args, cwd=SKILL, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["session_id"], "6af477c9-c158-4eac-9f37-ae0054718c0d")
            self.assertEqual(json.loads((root / "observed-primary.json").read_text())["primary"], primary)
            self.assertEqual(json.loads((root / "rounds.json").read_text())["fixture"],
                             {"attempts": 1, "successes": 1})
            self.assertIn("APPROVE", (root / "review.md").read_text())

    def run_source_agy_cli(self, primary):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "bin" / "agy"
            executable.parent.mkdir()
            executable.write_text("#!" + sys.executable + "\n" + '''import json, os, pathlib, sys
args=sys.argv[1:]
if '--help' in args:
    print('Usage of agy:')
    print('  --add-dir  Add dir')
    print('  --conversation  Resume by ID')
    print('  --dangerously-skip-permissions  Auto approve')
    print('  --disable-slash-commands  Disable slash')
    print('  --input-format  Input (text, stream-json)')
    print('  --model  Model')
    print('  --output-format  Output (text, json, stream-json)')
    sys.exit(0)
msg=json.loads(sys.stdin.readline())
prompt=msg['message']['content']
assert 'Review execution contract' in prompt
assert 'Review the fixture' in prompt
primary=(
    'claude' if os.environ.get('CLAUDECODE')=='1'
    else 'codex' if os.environ.get('CODEX_THREAD_ID')
    else 'grok'
)
(pathlib.Path.cwd()/'observed-primary.json').write_text(json.dumps({'primary':primary}))
sid='f7965130-c060-4181-abcf-4fadb1054401'
print(json.dumps({'event':'init','conversation_id':sid}), flush=True)
print(json.dumps({'event':'result','result':{'conversation_id':sid,'status':'SUCCESS','response':'APPROVE\\nFixture checked.','num_turns':1,'usage':{'input_tokens':2,'output_tokens':3}}}), flush=True)
''')
            executable.chmod(0o755)
            request = root / "request.md"
            request.write_text("Review the fixture without modifying it.")
            env = {k: v for k, v in os.environ.items() if not k.startswith(
                ("CLAUDE", "CODEX", "GROK", "ANTIGRAVITY", "AGY_", "ANTHROPIC_", "OPENAI_", "XAI_", "GEMINI_", "GOOGLE_"))}
            env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
            if primary == "claude":
                env.update(CLAUDECODE="1", CLAUDE_PROJECT_DIR=str(root))
            elif primary == "codex":
                env.update(CODEX_THREAD_ID="01a2174b-e2fa-7cc3-adc8-a9f550265f6d")
            else:
                env.update(GROK_WORKSPACE_ROOT=str(root), GROK_SESSION_ID="fixture-primary")
            args = [sys.executable, "-B", "-m", "scripts.to_agy", "--request-file", str(request),
                    "--cd", str(root), "--handoff-dir", str(root / "handoff"),
                    "--marker-path", str(root / "rounds.json"), "--gate-id", "agy-primary-test",
                    "--artifact-key", "fixture", "--cost-log", str(root / "cost.jsonl"),
                    "--output", str(root / "review.md"), "--settings", str(root / "absent-settings"),
                    "--timeout-seconds", "3"]
            result = subprocess.run(args, cwd=SKILL, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["session_id"], "f7965130-c060-4181-abcf-4fadb1054401")
            self.assertEqual(json.loads((root / "observed-primary.json").read_text())["primary"], primary)
            self.assertEqual(json.loads((root / "rounds.json").read_text())["fixture"],
                             {"attempts": 1, "successes": 1})
            self.assertIn("APPROVE", (root / "review.md").read_text())

    def test_claudecode_primary_can_launch_the_source_codex_adapter(self):
        self.run_source_cli("claude")

    def test_grok_primary_can_launch_the_source_codex_adapter(self):
        self.run_source_cli("grok")

    def test_antigravity_primary_can_launch_the_source_codex_adapter(self):
        self.run_source_cli("antigravity")

    def test_claude_codex_grok_primaries_can_launch_the_source_agy_adapter(self):
        for primary in ("claude", "codex", "grok"):
            with self.subTest(primary=primary):
                self.run_source_agy_cli(primary)


if __name__ == "__main__":
    unittest.main()
