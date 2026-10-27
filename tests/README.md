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

For a focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests/cross-agent-review
```

Distribution checks reject development directories and caches inside bundles,
check local Markdown links, literal asset paths and evaluation input paths, and import copied runtime
scripts in isolated processes without the source repository. They do not start
model calls, contact business services or prove agent output quality.
