---
name: deep-task-preflight
version: 1.2.1
description: >-
  Use before work when the goal, scope, completion criteria, or evidence boundary is unclear;
  when a previous attempt was rejected for missing context or incomplete verification; when
  the user explicitly asks for a plan, acceptance criteria, comparison with existing
  implementation, or a deeper preflight; or when a user-facing, cross-system, irreversible,
  or multi-phase deliverable needs alignment before editing. Build a compact evidence-based
  preflight, stop only for blocking questions, and verify the final result against the
  acceptance matrix. Do not trigger for routine one-line edits, direct factual answers, or
  standalone verification requests unless the user also asks for planning or alignment.
---

# Deep Task Preflight

## Purpose

Turn “think more deeply” into a reviewable workflow: align the intended outcome, boundaries,
evidence, decisions, and completion checks before changing files or external state. Depth
comes from coverage and falsifiable checks. Never request or reveal hidden chain-of-thought;
record concise conclusions, sources, assumptions, alternatives, and decisions.

This skill supplies the alignment gate. Read only the relevant adapter in
`references/adapters/` for domain-specific verification. Follow repository instructions and
domain skills in addition to this workflow.

## Choose a mode

- **Lightweight**: one clear, reversible change with an obvious check. State the outcome,
  one acceptance check, the scope boundary, and the next action.
- **Medium**: a few files or one subsystem, with a known goal but non-trivial compatibility
  or validation. Use the compressed packet template; keep criterion IDs, unknowns, the gate,
  and the validation matrix.
- **Full**: unclear or previously disputed work, cross-repository/system changes, audience-
  facing deliverables, irreversible or data-affecting work, or tasks that need multiple
  sessions/agents. Use the full packet and relevant adapters.

Do not promote a task to Full merely because it has several steps. Promote it when a wrong
interpretation would change scope, behavior, evidence, or completion.

## Baseline and reference-first rule

Before planning edits, read applicable `AGENTS.md`, `README`, local skill instructions,
branch/worktree state, and the closest existing implementation or artifact. When an existing
client, server path, parser, renderer, schema, workflow, or template is named or plausibly
relevant, compare it on the same representative input before designing a replacement. Record
the reference path/revision, input and output shapes, transformation rules, and intentional
differences. If no reference exists, say so. A similar-looking file is not evidence of
equivalent behavior.

## Preflight packet

Use the full or compressed template in [packet-template.md](references/packet-template.md).
Full and Medium packets must retain observable outcome, scope boundary, criterion IDs,
unknowns, the gate, and a validation matrix. Full mode additionally records audience, source
priority, change surface, references, risks, and alternatives.

The outcome must describe the user's result, not the agent's activity. “Add three slides”
describes work; “help the audience understand the problem, motivation, evidence, and result
within three slides” describes an outcome.

## Challenge checks before editing

In Medium and Full modes, read [challenge-checks.md](references/challenge-checks.md) and
apply its nine checks: stranger, traceability, boundary, evidence, negative space, failure
path, rework, reference parity, and end to end. Record failures in the packet and revise it
before editing; do not compensate with a longer task list.

## Ambiguity, stopping, and re-gating

Classify each uncertainty:

- **Blocking**: different answers change the goal, scope, public behavior, ownership,
  safety boundary, or acceptance result. Set `NEEDS INPUT`, ask at most three questions in
  one batch, and do not mutate the workspace.
- **Non-blocking**: state the assumption and proceed using local conventions or stronger
  evidence.
- **Testable unknown**: perform the cheapest read-only inspection or validation that can
  resolve it.

`NEEDS INPUT` exits when the user answers the questions; then rebuild the affected packet
sections and re-run the gate. If the user does not answer, leave the workspace unchanged and
report exactly what is waiting. `BLOCKED` requires a concrete missing dependency, access
failure, contradictory source, or unsafe boundary plus an exit condition; do not claim partial
completion as done. Re-run the preflight gate whenever new evidence changes the goal, an
acceptance criterion, the change surface, a referenced contract, or the risk boundary.

If implementation is authorized and the gate is `READY`, show the packet and continue without
ceremonial approval. If the task expands beyond the packet, pause at the next safe boundary,
update the packet, and gate again.

## Execution and universal verification ladder

Keep every change tied to an acceptance ID and inspect the diff/artifact after each meaningful
phase. For every changed path, use this input → transform → output loop:

1. **Automated check**: run the cheapest meaningful lint, unit test, schema check, render
   check, or deterministic comparison.
2. **Boundary check**: inspect the actual request, state, artifact, or payload at each changed
   interface; verify identifiers, counts, ordering, grouping, empty values, references, and
   freshness. Do not assume the first observed item is complete when the contract permits
   multiple outputs.
3. **Consumer read-back**: read through the same path that consumes the write or artifact
   (page, report, cache, downstream service, export, or device) and confirm the observable
   state changed. A success response or HTTP 200 is not completion evidence.
4. **Acceptance closure**: revisit every acceptance row, attach exact commands/results and
   evidence paths, label partial or unverified criteria, and state remaining risks.

Do not report “done” because files were created or tests merely started. For cross-session or
multi-agent work, persist the packet and decisions with `context-resilient-task` when a
`.task-state` exists or local conventions require durable recovery.

## Route to an adapter

Read only the relevant bundled reference before execution. The adapter describes
representative inputs, boundary checks, consumer read-back, failure cases, and evidence
to retain. If no adapter fits, use the universal verification ladder and state the
task-specific boundary checks in the preflight packet.

| Task shape | Reference |
|---|---|
| Code, refactor, compatibility, tests | [code-changes.md](references/adapters/code-changes.md) |
| Documents, presentations, reports | [documents.md](references/adapters/documents.md) |
| UI and interactive state | [ui-interactive.md](references/adapters/ui-interactive.md) |
| Data extraction, batch, media, LLM/report pipelines | [data-pipelines.md](references/adapters/data-pipelines.md) |
| Debugging and incident analysis | [debugging.md](references/adapters/debugging.md) |
| API/schema/migration/deploy/security/performance work | [contracts-and-operations.md](references/adapters/contracts-and-operations.md) |

Use `repository-code-style` for local implementation conventions, `context-resilient-task`
for durable recovery, and `cross-agent-review` only when an independent reviewer is requested
or the risk justifies it. These skills complement the gate; they do not replace it.

## Lightweight response

Render in the user's language:

```text
Outcome: <observable result>
Acceptance: <one concrete check>
Scope: <one sentence including the main non-goal if useful>
Next: <immediate action>
```
