# Plan

**Last Updated:** 2026-07-25 12:34:00
**Goal:** Harden the cross-agent-review skill P1 safety guarantees and obtain a ClaudeCode read-only review.

## Phase 1: test the fixed-cap contract
**Status:** completed
**Description:** Add isolated Python regression tests that demonstrate a caller cannot raise either the attempt or success cap and that a failed started call consumes an attempt.
**Deliverables:**
- `cross-agent-review/tests/test_review_limits.py`

## Phase 2: implement the marker contract
**Status:** completed
**Description:** Use fixed constants and structured marker entries so both adapters reserve an attempt before invoking a reviewer and commit success only after verified persistence.
**Deliverables:**
- Updated bundled adapter scripts

## Phase 3: documentation alignment
**Status:** completed
**Description:** Align the skill, protocol, and README with the actual fixed cap, user approval, and provider-specific budget boundaries; remove stale release-state claims.
**Deliverables:**
- Updated `SKILL.md`, protocol, and README

## Phase 4: ClaudeCode review gate
**Status:** completed
**Description:** The authorized adapter gate failed closed with a 403, then an interactive ClaudeCode handoff returned `APPROVE WITH NITS`. The resulting file is accepted as artifact evidence only, not an adapter-success envelope or a committed review round.
**Deliverables:**
- `Review/ForClaudeCode/handoff-cross-agent-review-p1-20260725.md`
- `Review/ByClaudeCode/cross-agent-review-p1.md` (interactive verdict)

## Phase 5: Address accepted review findings
**Status:** completed
**Description:** Verify the interactive ClaudeCode N1-N4 findings, implement N1, add N2 regressions, document N3, and retain N4 as an explicit runtime limitation.
**Deliverables:**
- Forward CLI availability guard
- Expanded eight-test local regression suite
- Shared-marker serialization documentation

## Phase 6: Resolve provider client-identity compatibility
**Status:** completed
**Description:** The credential path is deterministic and the transmitted bearer token matches settings. A user-approved truthful `claude-cli/<version>` child identity completed a real review gate; the adapter now exposes that path as a strict opt-in while keeping gateway allowlisting of the official `sdk-cli` identity as the preferred governance fix.
**Deliverables:**
- Deterministic forward child credential environment
- Regression test for injected settings credentials and temporary config cleanup
- One budget-approved provider gate (completed: returned pre-model 403)
- Local request-header capture proving the transmitted credential and client identity
- No-model provider A/B proving `sdk-cli` -> 403 and plain `claude-cli/2.1.216` -> request-validation 400
- Successful fresh budget-approved compatibility gate (`$0.64111725`, `APPROVE WITH NITS`)
- Strict opt-in `--claude-user-agent` implementation, regressions, docs, and installed-bundle synchronization

## Phase 7: Local CLI discovery and truthful identity derivation
**Status:** completed
**Description:** Replace caller-supplied Claude version claims with local CLI discovery, provide a no-network capability report, and align the source and installed documentation with the resolved gateway behavior.
**Deliverables:**
- Capability discovery tool and tests (completed in source)
- Derived gateway compatibility identity with no raw version input (completed in source)
- Reconciled source/installed documentation and parity verification (completed: both copies compile and pass 14/14 tests)

## Phase 8: Third-party installer compatibility hardening
**Status:** completed
**Description:** Remove portability blockers in the cross-agent-review bundle while preserving fail-closed review guarantees.
**Deliverables:**
- Portable POSIX/Windows marker-lock import and fail-closed handling
- Inherited official-Claude authentication path
- Claude CLI `--max-budget-usd` capability preflight and doctor output
- Source-verified Codex provenance with diagnostic-only drift hints
- Synced authoritative protocol and 31 passing local regressions
- Explicitly deferred real-Windows smoke validation, accepted by user for a future Windows use case

## Phase 9: Controlled reviewer-model selection
**Status:** completed
**Description:** Add an optional, common `--model` adapter argument that maps to the local Claude/Codex CLI model selector without exposing arbitrary configuration or weakening the review safety envelope.
**Deliverables:**
- Reviewed implementation plan at `docs/plans/2026-07-27-cross-agent-review-model-selection.md`
- Fresh ClaudeCode read-only compatibility review before implementation (completed: `APPROVE WITH NITS`; findings incorporated)
- TDD-backed model validation, argv construction, requested-model audit data, and docs (completed: 37 local tests pass)

## Plan Registry (docs/plans)

<!--
Strict boundary: register ONLY docs/plans/*.md files.
Do NOT register CLAUDE.md, AGENTS.md, .task-state/*, or docs/runbooks/*.
Status values: pending | in_progress | completed | abandoned
-->

| File | Source Skill | Date | Status |
|------|--------------|------|--------|
| docs/plans/2026-07-27-cross-agent-review-model-selection.md | writing-plans | 2026-07-27 | completed |

## Reference Index

<!--
Optional. For non-plan reference files (runbooks, external design docs).
NOT for CLAUDE.md / AGENTS.md (auto-loaded) or MRS files. Delete this section if unused.
-->

| File | Purpose |
|------|---------|
