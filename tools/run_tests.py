"""Run repository and per-skill tests without sharing import state."""

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info < (3, 11):
        print("Repository development checks require Python 3.11 or newer, matching CI.", file=sys.stderr)
        return 2
    test_root = REPO_ROOT / "tests"
    suites = [test_root] + sorted(
        path for path in test_root.iterdir()
        if path.is_dir() and any(path.glob("test_*.py"))
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    failed = []
    for suite in suites:
        print(f"\nRunning {suite.relative_to(REPO_ROOT)}", flush=True)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(suite)],
            cwd=REPO_ROOT, env=env,
        )
        if result.returncode:
            failed.append(str(suite.relative_to(REPO_ROOT)))
    if failed:
        print("Failed suites: " + ", ".join(failed), file=sys.stderr)
        return 1
    print(f"\nAll {len(suites)} suites passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
