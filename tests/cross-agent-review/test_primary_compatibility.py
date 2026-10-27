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
primary='claude' if os.environ.get('CLAUDECODE')=='1' else 'grok'
(target/'observed-primary.json').write_text(json.dumps({'primary':primary}))
pathlib.Path(args[args.index('--output-last-message')+1]).write_text('APPROVE\\nFixture checked.')
print(json.dumps({'type':'thread.started','thread_id':'6af477c9-c158-4eac-9f37-ae0054718c0d'}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}))
''')
            executable.chmod(0o755)
            request = root / "request.md"
            request.write_text("Review the fixture without modifying it.")
            env = {k: v for k, v in os.environ.items() if not k.startswith(
                ("CLAUDE", "GROK", "ANTHROPIC_", "OPENAI_", "XAI_"))}
            env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
            if primary == "claude":
                env.update(CLAUDECODE="1", CLAUDE_PROJECT_DIR=str(root))
            else:
                env.update(GROK_WORKSPACE_ROOT=str(root), GROK_SESSION_ID="fixture-primary")
            args = [sys.executable, "-m", "scripts.to_codex", "--request-file", str(request),
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

    def test_claudecode_primary_can_launch_the_source_codex_adapter(self):
        self.run_source_cli("claude")

    def test_grok_primary_can_launch_the_source_codex_adapter(self):
        self.run_source_cli("grok")


if __name__ == "__main__":
    unittest.main()
