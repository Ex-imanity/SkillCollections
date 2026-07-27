# Progress

<!-- Append chronological execution log entries below this line. -->

## 2026-07-25 03:05 — P1 local hardening
- Created branch `codex/cross-agent-review-p1` and initialized the multi-agent MRS.
- Added P1 regression tests for caller-configurable caps, missing forward budget, and repeated failed calls in both directions.
- Observed the intended RED failures, then implemented fixed two-attempt/two-success marker counters with legacy integer-marker compatibility.
- Removed `--max-rounds` from both CLIs, required a positive forward `--max-budget-usd`, and aligned documentation.
- Verification: `python -m unittest discover -s cross-agent-review/tests -p 'test_*.py' -v` reported 5 passing tests; both scripts compiled and exposed the intended help contracts.
- Next: wait for the user-approved per-call budget, then run the prepared ClaudeCode review gate.

## 2026-07-25 03:12 — ClaudeCode gate authorized
- User approved a maximum $2 budget for the single Codex-to-ClaudeCode review call.
- Preflight reran the P1 regression suite (5/5 passed), MRS verification, request-file existence, and diff whitespace checks.
- Next: invoke the read-only adapter with the prepared request and persist its verdict under `Review/ByClaudeCode/`.

## 2026-07-25 03:16 — ClaudeCode gate failed closed
- Invoked `cross-agent-review/scripts/codex_to_claude.py` with the user-approved `--max-budget-usd 2`, fixed read-only permissions, and a 600-second timeout.
- Result: `auth_failure`, session id recorded by the adapter, detail `403 Forbidden`; no reviewer output was persisted.
- Adapter wrote `Review/ForClaudeCode/handoff-cross-agent-review-p1-20260725.md` and recorded one marker attempt with zero successful reviews.
- Per protocol, did not run auth-status commands, mutate credentials, fabricate a verdict, or retry automatically.
- Next: use the redacted handoff from an interactive ClaudeCode context.

## 2026-07-25 03:24 — Interactive review received
- Interactive ClaudeCode continued the handoff and wrote `Review/ByClaudeCode/cross-agent-review-p1.md` with `APPROVE WITH NITS`.
- The review explicitly labels itself as interactive-continuation artifact evidence, not an adapter-success envelope. The marker remains `attempts: 1, successes: 0`.
- Evaluated the write boundary: normal adapter reviews must return text only and let the primary persist verified output; interactive handoffs may write only the named review artifact when that exception is explicit.
- Open follow-up: primary verification and disposition of N1/N2; no source changes were made in this step.

## 2026-07-25 03:40 — Review findings resolved
- Verified N1 as a real pre-invocation defect: a missing forward `claude` binary could reserve an attempt before the runner raised.
- Added `claude_available()` before readiness, marker locking, and attempt reservation; a missing binary now returns `claude_unavailable` with a handoff and no marker write.
- Added N2 regression coverage for two persisted successful reviews followed by `round_cap_exceeded`, and for reverse CLI rejection of `--max-rounds`.
- Documented N3: a shared marker lock serializes cross-artifact gates and lock acquisition has no separate deadline; N4 remains an explicit lack of live provider-budget enforcement testing.
- Verification: `python3 -m unittest tests/test_review_limits.py` reported 8/8 passing tests; both documented module help entrypoints succeeded.

## 2026-07-25 04:05 — Authorized Codex-environment authentication probe
- Confirmed without a model call that `~/.claude/settings.json` has non-empty proxy fields, the configured base URL is syntactically valid, DNS-resolvable, and responds HTTP 200, and `claude` CLI version 2.1.216 launches.
- With the user's new `$2` authorization, ran one minimal direct `claude -p` request using the adapter's read-only permission/budget parameters. It returned `api_error_status: 403`, `duration_api_ms: 0`, zero input/output tokens, and `total_cost_usd: 0`.
- Conclusion: the configured endpoint is reachable but authentication/authorization for this Codex-environment CLI request remains rejected before model processing. No skill installation or retry was performed.

## 2026-07-25 04:12 — ClaudeCode main-session diagnostic handoff prepared
- Created `Review/ForClaudeCode/codex-environment-403-diagnosis.md` with the exact failing command, redacted result metadata, and a request to compare the main-session and non-interactive authentication contexts.
- User will run this diagnosis directly in ClaudeCode. No source code, credential, installation, or git changes were made for this handoff.

## 2026-07-25 10:34 — Deterministic Codex-to-Claude child credentials implemented
- Read the interactive ClaudeCode diagnosis: the byte-exact CLI invocation succeeds from its main session but fails from the Codex host because child credential resolution differs by host process.
- Confirmed this Codex host has only `HOME` among `ANTHROPIC_*`/`CLAUDE_*` configuration variables. The old adapter removed verified settings credentials and relied on the failing implicit settings lookup.
- Added a RED regression requiring `settings-env` children to receive the settings-file proxy values and a fresh empty `CLAUDE_CONFIG_DIR`; it failed on the missing proxy values.
- Implemented the remedy: create a temporary config dir around the reviewer subprocess, inject the verified settings values, reserve the attempt only after this setup succeeds, and remove the temp directory afterward.
- Verification: 9/9 local regression tests and Python compilation pass. A fresh provider gate remains pending new budget approval.

## 2026-07-25 10:48 — Post-remedy provider gate still fails at the host boundary
- With the user's `$2` authorization, ran a new-artifact Codex-to-Claude verification gate. It returned `auth_failure` / HTTP 403, with a reported cost of zero; no review output was persisted.
- The new artifact marker is `attempts: 1, successes: 0`; the original marker entry remains unchanged.
- Independently ran the adapter's settings-env builder through a real `/usr/bin/env` child: both selected settings credentials were present, the temporary config directory was passed and empty, and no HTTP proxy, Node, or SSL override variables are set in the Codex host.
- Conclusion: the adapter's argv, stdin transport, and child environment are correct. The unresolved difference is the parent host/runtime identity versus the normal terminal/ClaudeCode host.

## 2026-07-25 10:20 — ClaudeCode main-session 403 diagnosis returned
- Ran the byte-exact failing command from the interactive ClaudeCode host: it SUCCEEDS (`api_error_status=None`, result `OK`). Same binary/cwd/flags/settings.json → failure is host-process specific, not token/flags.
- Controlled experiments (Tests A–F): settings.json `env` overrides process env (B/C); env-injection alone authenticates (D); no-credential returns "Not logged in" not 403 (E); `ANTHROPIC_MODEL=...[1m]` still succeeds (F). Shell profiles export no `ANTHROPIC_*`; `~/.codex/auth.json` has only `OPENAI_API_KEY`.
- Conclusion: Codex's 403 = a WRONG credential was sent and rejected (403 ≠ "Not logged in"); under the Codex host the child `claude -p` does not apply `~/.claude/settings.json` and sends a foreign/stale token. Category = credential-resolution difference between host processes, not an invalid token or a proxy policy block.
- Wrote `Review/ByClaudeCode/codex-environment-403-diagnosis-result.md` with evidence, the one confirmatory command for Codex to run in its own host (`env | grep -iE 'ANTHROPIC|CLAUDE_CONFIG|^HOME='`), and the minimal remedy.
- Proposed remedy (not applied): in `codex_to_claude.resolve_subprocess_env` settings-env branch, set a fresh empty `CLAUDE_CONFIG_DIR` for the child AND inject the settings.json `ANTHROPIC_BASE_URL/AUTH_TOKEN` into the child env, instead of popping and relying on the child re-reading settings.json. Test D proves this shape authenticates.
- Next: Codex (primary) confirms its host env, applies the adapter remedy, then runs one fresh budget-approved gate (reset marker `attempts:1` first or spend the last attempt).

## 2026-07-25 11:14 — Provider User-Agent policy isolated without a model call
- Ran a local capture endpoint and invoked the real Claude CLI with the repaired adapter environment. The outgoing bearer-header hash exactly matches the configured token; removing `CODEX_*` variables produces the same request.
- Identified the working-context difference as Claude client identity: print mode sends `sdk-cli`, while the ClaudeCode extension host uses `claude-vscode`/Agent SDK metadata.
- Sent invalid `{}` requests to the configured provider with the same token. `sdk-cli` returned 403; `claude-vscode`, absent User-Agent, and truthful plain `claude-cli/2.1.216` returned 400 request-validation errors. These probes cannot invoke a model and incurred no model cost.
- Verified `x-api-key` does not repair `sdk-cli`, and verified locally that `ANTHROPIC_CUSTOM_HEADERS` can replace or remove the blocked User-Agent.
- Corrected the MRS root cause. No credential, global Claude setting, shared installed skill, or provider configuration was changed. Next: prefer provider allowlisting of `sdk-cli`; otherwise obtain explicit approval for a child-only truthful User-Agent compatibility gate and its per-call budget.
- Reconciled the `task_state.md` Completed Items in place so the MRS source of truth no longer presents the superseded wrong-token/host-boundary hypothesis as current.

## 2026-07-25 11:32 — Truthful CLI compatibility path completed and installed
- User authorized one real compatibility gate with a maximum `$2` budget. The adapter ran with a child-only truthful `claude-cli/2.1.216` User-Agent and returned a verified ClaudeCode `APPROVE WITH NITS` result; reported cost `$0.64111725`, wall time `136.546s`, one attempt and one success.
- Added RED tests for child identity isolation, truthful opt-in behavior, invalid identity rejection before attempt reservation, and CLI exposure. The pre-fix suite failed in the expected four places.
- Implemented strict `claude-cli/<semantic-version>` validation, removed inherited custom-header/IDE identity variables, wired `--claude-user-agent`, and documented gateway allowlisting as the preferred repair. The suite then passed 12/12.
- Synchronized the complete verified bundle to `/Users/gaotu/.cc-switch/skills/cross-agent-review`; its own Python compilation, 12/12 regression suite, and source parity check passed.
- Did not spend a second model call: the single approved live gate already validated the exact child header, and local tests validate the new option wiring.
- Final independent verification reran the installed bundle's 12 tests, both adapter compilation, candidate/install parity, MRS validation, `git diff --check`, and a tightened secret scan. An installed-CLI smoke test also rejected `claude-vscode` as `setup_failure` with no attempt marker, without invoking a model.

## 2026-07-26 — Phase 8 compatibility hardening (ClaudeCode, awaiting Codex review)
- Reviewed the installed skill for third-party portability ("will other installers be able to use it?"). Found 2×P1 + 2×P2 blockers (see findings.md 2026-07-26). Baseline suite 17/17 green before changes.
- P1-a: replaced unconditional `import fcntl` with conditional fcntl/msvcrt binding + `_lock_exclusive`/`_unlock`; both adapters now import on Windows, lock fails closed if no primitive exists.
- P1-b: `check_readiness` returns `inherited` instead of `missing`; forward gate works with official Claude auth, not just a proxy gateway. (Discovered while testing that this very session runs behind the `baijia.com` proxy — the ambient env carries the proxy vars, so the `inherited` test had to clean the environment to be deterministic.)
- P2-a: added `claude_supports_max_budget()` `--help` probe + opt-in forward-gate preflight (clear upgrade message, no attempt reserved) + doctor `max_budget_supported` field (text shows `max-budget-usd=yes`).
- P2-b: rewrote `_parse_codex_json_stream`/`_extract_*` to be drift-tolerant (verified primary → defensive fallback, exact-key only), capture verified optional token fields, and emit observed event types on `provenance_failure`.
- Consulted Codex for its real `--json` schema (per user suggestion). Its live probe was sandbox-blocked, so it source-verified `rust-v0.144.1` (this host's version) and confirmed the primary field names + two real optional usage fields; applied `cached_input_tokens`/`reasoning_output_tokens` capture and camelCase id fallbacks as a result.
- Verification: `py_compile` OK on all scripts+tests; `pytest tests/` → 29 passed (17 original + 12 new across CompatibilityTests and CodexProvenanceTests); both adapter `--help` and `runtime_capabilities` run clean; doctor reports `claude ... max-budget-usd=yes`, `codex ... supported`.
- Updated SKILL.md + README.md (credential `inherited` path, POSIX/Windows lock + Python 3.8+, `--max-budget-usd` version note, tolerant/diagnosable provenance).
- NOT committed and NOT re-synced to `/Users/gaotu/.cc-switch/skills/cross-agent-review`. Next: Codex main session reviews the working diff, then commits if acceptable.

## 2026-07-26 — Codex review round 1 resolved (ClaudeCode)
- Codex main session reviewed the Phase 8 diff and raised three valid findings (see findings.md 2026-07-26 review entry). Applied the receiving-code-review discipline; agreed with all three.
- Fix 1 (P1 provenance): rewrote extraction so ONLY source-verified event-type+field paths gate success; alias names are diagnostic-only `drift_hints`. Rewrote `_verified_session_id`/`_verified_usage`/`_collect_drift_hints`; `run_codex_review` now surfaces drift hints in the failure detail. Updated the corresponding test to assert aliases do NOT validate but ARE captured as hints.
- Fix 2 (protocol sync): updated `references/cross-agent-review-protocol.md` credential rule (added `inherited`) and guarantee-boundary provenance line (verified-only + diagnostics).
- Fix 3 (Windows lock): added `import errno`; `_lock_exclusive` retries msvcrt only on `EDEADLOCK`/`EDEADLK`, re-raises all other `OSError`; added two mock-msvcrt tests (retry-on-contention, reraise-non-contention).
- Verification: `py_compile` OK; `pytest tests/` → 31 passed (was 29); no provider calls.
- Still NOT committed. Next: Codex re-reviews the updated diff; commit if acceptable.

## 2026-07-26 — Phase 8 closure (Codex)
- Re-reviewed the resolved Phase 8 working diff and accepted it with no further blocking findings.
- Fresh verification: `python -m pytest cross-agent-review/tests/ -q` → 31 passed; `python -m py_compile scripts/*.py tests/*.py` from `cross-agent-review/` and `git diff --check` passed. No provider call was made.
- User accepted the remaining real-Windows validation gap as deferred work for a future Windows use case. The source working tree remains intentionally uncommitted, and the user will manually commit it and synchronize the installed bundle.

## 2026-07-27 — Phase 9 model-selection plan prepared (Codex)
- Verified no-network CLI evidence: local `claude -p --help` and `codex exec --help` both expose `--model`; official CLI documentation confirms the same native option.
- Created `docs/plans/2026-07-27-cross-agent-review-model-selection.md` with TDD steps for shared validation, both argv builders/gates, requested-model audit metadata, docs, and a pre-implementation review gate.
- Created `Review/ForClaudeCode/2026-07-27-cross-agent-review-model-selection-plan.md`. No source adapter was changed and no provider/model call was made. Awaiting explicit per-call budget approval to invoke the fresh plan-review gate.

## 2026-07-27 — Phase 9 ClaudeCode plan review completed (Codex)
- Ran one authorized Codex-to-ClaudeCode read-only gate under the fresh artifact key `cross-agent-review-model-selection-plan-v1`, timeout 600 seconds, max budget `$2`, and the previously verified derived local-CLI gateway compatibility identity. It returned a verified `APPROVE WITH NITS` review, session `6c28687b-8f1f-4ca4-a6cd-cb2d666f9b15`, reported cost `$1.30125925`, wall time `218.727s`, attempts=1, successes=1.
- Incorporated all material findings into the plan: single-token model option plus leading-dash validation, explicit Codex no-USD-cap documentation, optional inconclusive-safe capability preflight, 128-character limit, and precise requested-model cost-log scope.
- No adapter source was changed after review. Phase 9 is ready for an explicit implementation start.

## 2026-07-27 — Phase 9 implementation completed (Codex)
- Followed TDD: added model validator/argv/gate tests first (RED), then implemented the minimal shared validation, single-token native model arguments, pre-subprocess capability checks, and post-invocation requested-model audit metadata (GREEN).
- `--model` is optional in both adapters. When omitted, no native model argument is emitted and Claude/Codex use their local configured default model. Explicit values reject empty, leading-`-`, ASCII-control-containing, and over-128-character strings before availability, marker, or attempt work.
- Updated SKILL.md, README.md, and the authoritative protocol with default behavior, capability-preflight semantics, cost-log semantics, and the Codex no-USD-cap model-cost boundary.
- Verification: 37 tests passed, Python compilation passed, both module help commands expose `--model`, and `git diff --check` passed. No live model call occurred during implementation.

## 2026-07-27 — Phase 9 README clarity pass (Codex)
- Added concise README examples for the two intended paths: omit `--model` for the local CLI default, or append `--model <MODEL>` for an explicit reviewer model.
- Corrected the canonical protocol snippet so the optional model argument is appended only when selected, rather than appearing as a required trailing command argument.
