# Repository development tests

This directory is not part of an installed skill. Root tests check collection
conventions and distributable bundles; `tests/<skill>/` tests the runtime source
under `skills/<skill>/`.

From the repository root, use Python 3.11 or newer:

```bash
python tools/run_tests.py
```

The runner starts each suite in a separate Python process. Several skills use
identical test/module names and their own `scripts` package, so combining them
in one interpreter can test the wrong imported module. Bytecode generation is
disabled to avoid contaminating folders that users copy for installation.

MRS validation fixtures use isolated `.test-mrs-*` directories in the repository,
because the runtime validator rejects state stored under `/tmp/`. These
directories are cleaned up after each test and ignored by Git. CLI adapter tests
mock executable discovery and reviewer calls; installed Codex, Claude Code or Grok
programs and provider credentials are not required.

For a focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests/cross-agent-review
```

Distribution checks reject development directories and caches inside bundles,
check local Markdown links, literal asset paths and evaluation input paths, and import copied runtime
scripts in isolated processes without the source repository. They do not start
model calls, contact business services or prove agent output quality.
