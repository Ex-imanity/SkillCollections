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

Status: validated. Self-contained bundle. Two direct CLI adapters (no plugin
dependency), pressure A/B, and a real-skill auto-trigger measurement of
**9/10 positive / 10/10 negative (0 false positives)** all passed. Depends only
on the local `claude` and `codex` CLIs.

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
- Real-skill trigger gauge (eval tooling): `scripts/measure_claude_skill_trigger.py`

## Invocation

Read the protocol and the host-specific adapter first. From this skill directory:

```bash
cd <skill-dir>
python -m scripts.codex_to_claude --help    # Codex primary -> ClaudeCode reviewer (claude -p)
python -m scripts.claude_to_codex --help     # ClaudeCode primary -> Codex reviewer (codex exec --sandbox read-only)
```

Run one gate with an explicit request file, artifact key, readable directories,
output path, timeout, and a user-approved per-call budget. From a
ClaudeCode-primary turn use the direct `claude_to_codex` adapter (wraps
`codex exec --sandbox read-only`, no plugin dependency); the official Codex
plugin is an optional fallback only, documented in the mapping reference.

## Non-negotiable guards (from the protocol)

- Readiness = a real result envelope, never `claude auth status` / auth-status commands.
- Credentials = verify settings.json env block, then fall back to explicit inject; never log the token; never mutate auth.
- One primary/continuity owner; reviewer is read-only (`--permission-mode plan` for claude, hardcoded `--sandbox read-only` for codex; fixed `Read,Grep,Glob`; no caller override).
- Fresh session per gate. Re-review uses a second fresh gate with prior findings and new evidence explicit in the request; resume/session controls are not exposed.
- Concurrency-safe hard round cap (marker lock from check through commit); commit only after a verified successful review, so failed/blocked calls consume no round; damaged counters fail closed.
- Fail to a redacted durable handoff on any non-success; no recursive mutual review; plugin review gate off by default.
- Round counters for multiple artifacts share a single marker file. If damaged, preserve it for diagnosis then delete it manually; the adapter recreates it on the next readiness-qualified attempt.
- Reverse (codex) success requires real `thread.started.thread_id` + `turn.completed.usage`; otherwise fail closed. Log provider-reported `total_cost_usd` + wall time; missing USD is JSON `null`, never a fabricated `0`.
- Persist only verified non-empty reviewer output; never treat an empty/invalid envelope as a review. Redact known endpoint/token values and secret patterns before writing any artifact.

## Requirements & notes

- Requires the local `claude` and `codex` CLIs on PATH; no official Codex plugin dependency (it is only an optional fallback).
- Self-contained: the adapters, protocol, and checklist are bundled here; nothing points back to an external repo.
- Continuity: the protocol requires durable primary-owned continuity. Marker and cost-log paths are caller-selected filesystem paths, so any MRS/task-state mechanism (e.g. `context-resilient-task`) can satisfy that contract; this skill does not hard-depend on it.
- Provenance: extraction/validation evidence for this skill lives in the play-book repo (retrospectives, adapter tests `124 passed`, and the trigger measurement run-5/5b/5c). This bundle is the installable artifact.
