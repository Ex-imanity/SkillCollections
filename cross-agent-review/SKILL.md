---
name: cross-agent-review
description: >-
  Use when one local AI agent (Codex or ClaudeCode) should have the OTHER local
  agent perform a read-only review of a plan or code and return an
  evidence-cited verdict, while the primary keeps continuity and the fix
  responsibility. Triggers on cross-agent review, "让另一个 agent review",
  Codex/ClaudeCode 互审, plan-and-code review handoff between local CLI agents.
  Do NOT trigger for single-agent self-review or normal code review.
---

# Cross-Agent Review

Status: source bundle. Historical trigger and adapter evidence is recorded as
provenance. The 2026-07-25 bundle passed its regression suite and a real
Codex->ClaudeCode gate; each later installed version still needs its own checks
before being called end-to-end validated. The supported runtime adapters depend
only on the local `claude` and `codex` CLIs.

This skill is a **thin trigger wrapper**. The authoritative protocol and the
invocation mechanics live in the bundled reference docs and scripts — do not
re-fork the steps here (the durable knowledge must stay agent-agnostic, because
Codex cannot see Claude skills).

Paths below are relative to this skill directory (`<skill-dir>`); run scripts
from that directory so `scripts/` resolves as a Python package.

## Authoritative sources (read these; do not summarize away)

- Protocol: `references/cross-agent-review-protocol.md`
- Base checklist: `references/codex-primary-claudecode-review-loop.md`
- ClaudeCode→Codex optional plugin mapping: `references/claude-to-codex-mapping.md`
- Codex→ClaudeCode adapter: `scripts/codex_to_claude.py`
- ClaudeCode→Codex adapter (direct, no plugin dependency): `scripts/claude_to_codex.py`
- Local CLI capability doctor: `scripts/runtime_capabilities.py`
- Real-skill trigger gauge (eval tooling): `scripts/measure_claude_skill_trigger.py`

## Invocation

Read the base checklist, protocol, and then the host-specific adapter. From
this skill directory:

```bash
cd <skill-dir>
python -m scripts.codex_to_claude --help    # Codex primary -> ClaudeCode reviewer (claude -p)
python -m scripts.claude_to_codex --help     # ClaudeCode primary -> Codex reviewer (codex exec --sandbox read-only)
python -m scripts.runtime_capabilities --json # local CLI discovery; no review/model call
```

Run one gate with an explicit request file, artifact key, readable directories,
output path, timeout, and explicit user approval. Codex-primary gates must also
pass `--max-budget-usd <user-approved-usd>`; ClaudeCode-primary gates have no
provider-supported USD cap, so obtain explicit approval and rely on the fixed
attempt cap plus timeout. The direct `claude_to_codex` adapter has no plugin
dependency; the official Codex plugin is an optional fallback only.

Some third-party Anthropic-compatible gateways reject Claude Code's default
`sdk-cli` identity with a pre-model 403. Prefer asking the gateway operator to
allow the official identity. Only after the user explicitly approves the
compatibility workaround, pass `--gateway-compat-cli-identity`. The adapter
locally resolves `claude`, obtains its semantic version through `--version`,
uses that same resolved binary for the review, and applies only the derived
plain `claude-cli/<version>` header to the child process. It never accepts a
caller-supplied identity, `claude-vscode`, or arbitrary headers; an unavailable
or unparsable local version fails before a review attempt is reserved.

The capability doctor probes an explicit catalog of known local agent CLI names
with a minimal `PATH`-only `--version` subprocess. It reports whether a found
CLI has a supported review route; detected-but-unsupported CLIs are diagnostic
only and are never selected automatically. It neither forwards credentials nor
starts a review or model request.

## Non-negotiable guards (from the protocol)

- Readiness = a real result envelope, never `claude auth status` / auth-status commands.
- Credentials = verify the settings.json env block, then run the child with a fresh temporary `CLAUDE_CONFIG_DIR` and explicitly inject those verified values; fall back to explicit inject when only env vars supply the proxy keys; otherwise fall back to `inherited` and let the local `claude` use its own existing auth (subscription/OAuth login or ambient `ANTHROPIC_API_KEY`) — no proxy gateway is required. Auth is judged on the real result envelope, so an unauthenticated CLI fails closed as `auth_failure`. Never log the token or mutate auth.
- Client identity = discard inherited custom-header/IDE identity variables. Keep Claude Code's default identity unless the user explicitly approves the derived local-CLI gateway workaround.
- One primary/continuity owner; reviewer is read-only (`--permission-mode plan` for claude, hardcoded `--sandbox read-only` for codex; fixed `Read,Grep,Glob`; no caller override).
- Fresh session per gate. Re-review uses a second fresh gate with prior findings and new evidence explicit in the request; resume/session controls are not exposed.
- Concurrency-safe fixed cap: at most two started calls and at most two
  successful reviews per artifact. A started call reserves an attempt before
  the reviewer subprocess begins, including calls that later fail; damaged
  counters fail closed.
- Fail to a redacted durable handoff on any non-success; no recursive mutual review; plugin review gate off by default.
- Round counters for multiple artifacts share a single marker file. The exclusive lock covers the entire review call, so gates for different artifacts using that marker serialize; a waiting gate has no separate acquisition deadline and normally waits behind the current call's configured timeout (600 seconds by default) plus local I/O. `<marker-path>.lock` remains after normal completion as a harmless flock coordination sentinel, not review state; put both files in an ignored task-state location and do not delete the lock while a gate may hold it. If the marker JSON itself is damaged, preserve it for diagnosis then delete only that marker file; the adapter recreates it on the next readiness-qualified attempt.
- After an attempt is durably reserved and immediately before the reviewer subprocess begins, both adapters emit one redacted `review_started` JSON record to stderr. It is an active-gate signal, not a success result; the final structured result remains on stdout.
- Reverse (codex) success requires a real session/thread id + a real non-negative token pair. Extraction is tolerant of minor codex schema drift (primary probed names first, then conventional fallbacks), but still fails closed when either piece is missing; a `provenance_failure` records the observed event types so a schema change is diagnosable rather than silent. Log provider-reported `total_cost_usd` + wall time; missing USD is JSON `null`, never a fabricated `0`.
- Persist only verified non-empty reviewer output; never treat an empty/invalid envelope as a review. Redact known endpoint/token values and secret patterns before writing any artifact.

## Requirements & notes

- Requires the local `claude` and `codex` CLIs on PATH; no official Codex plugin dependency (it is only an optional fallback). The forward gate uses `claude -p --max-budget-usd ...`, so it needs a `claude` build new enough to support that flag; an older CLI fails closed with a handoff rather than running.
- Python 3.8+ stdlib only. Cross-platform: POSIX uses `fcntl` for the marker lock, Windows uses `msvcrt`; a platform with neither fails closed instead of skipping serialization.
- Self-contained runtime: the adapters, protocol, and checklist needed to run
  a gate are bundled here. Historical evidence paths remain optional provenance.
- Continuity: the protocol requires durable primary-owned continuity. Marker and cost-log paths are caller-selected filesystem paths, so any MRS/task-state mechanism (e.g. `context-resilient-task`) can satisfy that contract; this skill does not hard-depend on it.
- Provenance: historical extraction/validation evidence lives in the play-book
  repo. This bundle ships its current regression tests under `tests/`; those
  historical records are not a substitute for running the bundled checks.
