# Task State

**Last Updated:** 2026-07-26
**Updated By:** Codex

## Goal
Harden the cross-agent-review skill P1 safety guarantees and obtain a ClaudeCode read-only review.
(Phase 8 extension: compatibility review for third-party installers — portability blockers, not new safety features.)

## Status
completed

## Active Todos
_(none)_

## Current Phase
Closed: Phase 8 compatibility hardening for third-party installers. Codex accepted the resolved review round after local verification (2026-07-26).

## Next Action
User manually commits the accepted working-tree changes and synchronizes the locally installed `cross-agent-review` bundle. When a Windows use case exists, run a real Windows smoke/CI validation of the `msvcrt` lock path.

## Completed Items
- Added and observed five P1 regression tests fail before their corresponding implementation (2026-07-25).
- Fixed the marker contract: two started attempts and two successful reviews per artifact (2026-07-25).
- Removed public `--max-rounds` overrides and made the forward USD budget mandatory (2026-07-25).
- Aligned skill, protocol, README, and historical checklist status/budget language (2026-07-25).
- Ran one authorized $2 Codex-to-ClaudeCode gate; it failed closed with a pre-model 403 and consumed one attempt (2026-07-25).
- Received interactive ClaudeCode review verdict `APPROVE WITH NITS`; classified it as artifact evidence, not adapter success (2026-07-25).
- Added the N1 forward `claude` PATH guard before lock acquisition or attempt reservation (2026-07-25).
- Added N2 regression coverage for two persisted successes and reverse CLI cap rejection; documented N3 shared-marker lock serialization (2026-07-25).
- Verified 8/8 local regression tests and both documented module CLI help entrypoints; left N4 as an explicit runtime limitation (2026-07-25).
- Verified the configured base URL responds from the Codex environment, but an authorized direct `claude -p` probe still failed pre-model with 403 and zero cost (2026-07-25).
- Recorded the initial interactive ClaudeCode hypothesis that Codex sent a wrong token; later request capture disproved and superseded this hypothesis (2026-07-25).
- Confirmed this Codex host has no `ANTHROPIC_*` or `CLAUDE_CONFIG_DIR` exports, then implemented and unit-tested deterministic settings credential injection with an ephemeral child config directory (9/9 tests, 2026-07-25).
- Ran the authorized verification gate after that remedy; it still failed closed with a pre-model 403 and zero reported cost. Later request capture isolated the remaining failure to the provider's `sdk-cli` User-Agent policy (2026-07-25).
- Captured the real Claude request locally and proved the adapter sends the exact configured bearer token; isolated the provider rejection to the `User-Agent` suffix `sdk-cli` (`403`), while the same invalid request with a truthful plain `claude-cli/2.1.216` identity passes authentication and reaches request validation (`400`) (2026-07-25).
- Ran the user-approved truthful CLI identity gate successfully: real ClaudeCode verdict `APPROVE WITH NITS`, session `4b709883-e03d-474f-9270-8ce32f968bdd`, reported cost `$0.64111725` (2026-07-25).
- Added a strict opt-in `--claude-user-agent claude-cli/<semantic-version>` compatibility path, rejected arbitrary/IDE identities before attempt reservation, cleared inherited identity headers, and passed 12/12 regressions (2026-07-25).
- Synchronized the verified bundle to `/Users/gaotu/.cc-switch/skills/cross-agent-review` and independently passed its installed-copy compilation, regression, and source parity checks (2026-07-25).
- Replaced the raw compatibility version with an explicit local-CLI-derived identity flag; added a `PATH`-only local agent capability report and observed its RED/GREEN tests (14/14 source regressions, 2026-07-25).
- Reconciled source documentation so the two historical 403 incidents are clearly scoped, and so the original source bundle no longer claims the currently installed copy has this new revision (2026-07-25).
- Synchronized the Phase 7 source bundle to `/Users/gaotu/.cc-switch/skills/cross-agent-review`, preserving the prior installed bundle at `cross-agent-review.backup-20260725-phase7`; source/installed parity, compilation, and 14/14 regressions passed (2026-07-25).
- Phase 8 (2026-07-26): compatibility review found and fixed 2×P1 + 2×P2 portability blockers for third-party installers; regression suite grew 17→29 passing; not yet committed or synced to the installed bundle (2026-07-26).
- Phase 8 closure (2026-07-26): Codex re-reviewed the resolved diff with no further blocking findings. `pytest` passed 31 tests, `py_compile` and `git diff --check` passed, and no provider call was made. The user accepted deferral of real-Windows validation and will manually commit and synchronize the installed bundle.

## Open Questions
- RESOLVED (2026-07-26, per Codex review): only source-verified fields gate success; speculative aliases are diagnostic-only `drift_hints`. Implemented.
- DEFERRED (user decision, 2026-07-26): validate actual `msvcrt.locking` contention/error behavior on a real Windows runner when there is a Windows use case. Mock tests cover contention retry and non-contention fail-closed handling.

## Phase 8 completed items (2026-07-26, accepted)
- P1-a Windows: replaced the unconditional top-level `import fcntl` (POSIX-only, which also crashed the reverse adapter via its import) with a portable `_lock_exclusive`/`_unlock` (fcntl on POSIX, msvcrt on Windows, fail-closed if neither).
- P1-b Credential portability: `check_readiness` now returns `inherited` instead of `missing` when no proxy vars are configured, so installers on official Claude auth (subscription/OAuth/`ANTHROPIC_API_KEY`) can use the forward gate; auth still judged on the real envelope (unauth → `auth_failure`, fail closed).
- P2-a Version dependency: added `claude_supports_max_budget()` (`--help` probe); the forward gate runs an opt-in preflight (CLI on, hermetic tests off) that fails closed with a clear upgrade message before reserving an attempt; the doctor reports `max_budget_supported`.
- P2-b Codex schema fragility: `_parse_codex_json_stream` now gates success ONLY on source-verified event-type+field paths (`thread.started`→`thread_id`, `turn.completed`→`usage.{input_tokens,output_tokens}`; verified optional `cached_input_tokens`/`reasoning_output_tokens` captured). Conventional aliases are diagnostic-only `drift_hints` recorded in the `provenance_failure` detail — they never flip failure→success. (Revised 2026-07-26 per Codex review; earlier version let aliases gate success.)
- Codex review round 1 (2026-07-26): also fixed the Windows lock to retry msvcrt only on the contention errno (re-raise others) and synced the authoritative `references/cross-agent-review-protocol.md` (credential `inherited` step + verified-only provenance). Suite 29→31 passing.
- Consulted the Codex CLI (via cross-agent review, appropriately) for its `--json` schema; live probe was sandbox-blocked but Codex source-verified rust-v0.144.1 (this host's version) — primary field names confirmed correct.
- Verification: `python -m py_compile scripts/*.py tests/*.py` OK; `python -m pytest tests/` → 31 passed; both adapter `--help`, the doctor, and `git diff --check` run clean. No provider call was made during the re-review.

## Artifacts
- plan.md (created at init)
- snapshot.md (created at init)
- architecture.md (P1 marker-state design)
- cross-agent-review/tests/test_review_limits.py (P1 regression tests)
- Review/ForClaudeCode/cross-agent-review-p1.md (review request; $2 approval received)
- Review/ForClaudeCode/handoff-cross-agent-review-p1-20260725.md (redacted 403 handoff)
- .task-state/cross-agent-review/rounds.json (attempts=1, successes=0)
- Review/ByClaudeCode/cross-agent-review-p1.md (interactive continuation artifact; APPROVE WITH NITS)
- Direct Codex-environment probe result (2026-07-25; 403 before model use, no file persisted)
- Review/ForClaudeCode/codex-environment-403-diagnosis.md (main-session diagnostic handoff)
- Review/ByClaudeCode/codex-environment-403-diagnosis-result.md (main-session 403 root cause + minimal remedy)
- Review/ForClaudeCode/codex-vs-terminal-runtime-comparison.md (runtime comparison instructions)
- Local header-capture and provider invalid-body probes (2026-07-25; token values never persisted)
- Review/ForClaudeCode/codex-sdk-cli-user-agent-verification.md (authorized compatibility-gate request)
- Review/ByClaudeCode/codex-sdk-cli-user-agent-verification.md (verified adapter result; APPROVE WITH NITS)
- /Users/gaotu/.cc-switch/skills/cross-agent-review (updated installed bundle; NOT yet re-synced with Phase 8)
- Phase 8 working diff (uncommitted, 2026-07-26): cross-agent-review/scripts/codex_to_claude.py, scripts/claude_to_codex.py, scripts/runtime_capabilities.py, tests/test_review_limits.py, SKILL.md, README.md, references/cross-agent-review-protocol.md (7 files; 31/31 tests)

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
