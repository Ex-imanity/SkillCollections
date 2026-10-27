# Development evaluations

`evals/<skill>/` contains prompts, synthetic fixtures, expected answers, validation
records and evaluation-only tooling. These files stay in the source repository;
do not copy them into an agent's installed skills directory.

For `evals.json`, `files` entries are relative to the directory containing that
manifest. For example, `evals/repository-code-style/evals.json` refers to
`fixtures/scenarios.md` within its own evaluation directory. Expected
answers and prior outputs are for scoring, not inputs for an independent run.

Synthetic files, intentionally flawed proposals and disposable Git histories
are evaluation inputs. They are never evidence of real business-repository
conventions, author preferences or production behavior. Use them only for an
explicit development evaluation with the corresponding scenario instructions.

The unit/packaging checks run from the repository root with
`python tools/run_tests.py`; they do not execute model-backed evaluations.
The cross-agent trigger gauge and source-review guide are under
`evals/cross-agent-review/`. Real provider calls require separate authorization,
finite timeout and cost limits. Moving these tools does not authorize running them.

Business-derived evaluation inputs and detailed results may remain local until
redacted. The latest repository-code-style cases use its ignored `.local/`
directory; the public manifest contains only shareable cases and must not depend
on that local directory. Do not force-add private evaluation files to Git.
