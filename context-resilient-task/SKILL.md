---
name: context-resilient-task
description: Context-resilient task management with stateless recovery from artifacts. Use when starting multi-phase tasks, when task involves multiple sessions, after /clear or session interruption, or when you need to recover task state without relying on conversational memory.
---

# Context-Resilient Task

> **Context is not input, it's output.** Never rely on conversational memory. Always reconstruct task state from artifacts on disk.

## File Authority

- **`task_state.md`** — Source of truth. Always update **in-place** (edit existing fields). Never append dated sections.
- **`progress.md`** — Append-only chronological log. Never overwrite.
- **`snapshot.md`** — Latest checkpoint. **Overwrite** entire file on each update (archive previous first).
- **`decisions.md`** — Stable conclusions and decisions. Append-only. Required for long tasks (see Tier 1 below).
- On conflict between files, `task_state.md` wins.

## Minimum Recovery Set (MRS)

### Tier 0: Core Required (MUST exist)
- `task_state.md` — Current state (in-place updated, Active Todos in header)
- `plan.md` — Task plan + Plan Registry
- `snapshot.md` — Latest checkpoint (overwrite, not append)

**If missing:** STOP, run initialization wizard.

### Tier 1: Important Context (SHOULD exist)
- `findings.md` — Research and discoveries
- `progress.md` — Session execution log (append-only)
- `architecture.md` — Architecture (for system-level tasks)
- `decisions.md` — Stable conclusions/decisions (**required** when: multi-session, multi-agent, or >10 phases; otherwise optional)

**If missing:** WARN, ask user to confirm continuation.

### Tier 2: Optional Context (MAY exist)
- `blockers.md` — Current blockers
- Domain-specific artifacts

**If missing:** No action, continue normally.

Full MRS specification: [references/minimum-recovery-set.md](references/minimum-recovery-set.md)

## On-Invoke Detection

```
1. Scan for Tier 0 files
2. If status=completed → Skip recovery, prompt archival
3. If all Tier 0 present → Recovery mode
4. If any Tier 0 missing → Initialization mode
5. Check Tier 1, emit warnings if missing
6. Output "Reconstructed Task State"
7. Continue from last checkpoint
```

Task lifecycle: `active` → `paused` / `blocked` → `active` → `completed`

## Structured Output Template

At key checkpoints (recovery, phase transition, major decision, status request, error/blocker), output:

```markdown
## Reconstructed Task State
### Goal
(from artifact: task_state.md)
### What Has Been Done
- <action> (source: <filename>)
### Current Artifacts
- <filename> (last updated: <timestamp>)
### Unknown / Missing
- <info not in artifacts>
### Next Required Action
<single concrete step>
### Artifact to Be Produced
<filename> - <purpose>
```

Full template specification: [references/output-template.md](references/output-template.md)

## Anti-Hallucination Rules

1. **Source Attribution:** Every fact cites source file
2. **Explicit Unknowns:** If not in artifacts, mark "Unknown"
3. **No Inference:** Don't fill gaps with assumptions
4. **Single Next Action:** Only one concrete step at a time
5. **Output Artifact:** Every action produces/updates an artifact

## Todo Management

`task_state.md` maintains two sections as the **only** authoritative source for todos:

- **Active Todos** — Located near the **top of the file** (immediately after Status), ensuring recovery always reads them first.
- **Completed Items** — Single-line summaries only. Details belong in `progress.md`.

Rules: completing a todo = remove from Active, append to Completed. Never infer status from `progress.md`. Each todo is a single line; detailed context references external files.

Full rules: [references/artifact-standards.md](references/artifact-standards.md)

## Failure Modes

| Condition | Severity | Action |
|---|---|---|
| Missing Tier 0 file | STOP | Run initialization wizard |
| Missing Tier 1 file | WARN | Ask user to confirm continuation |
| Stale snapshot (>7 days) | WARN | Offer to regenerate |
| Conflicting artifacts | STOP | Ask user which is correct |
| Task completed | PROMPT | Offer archive / new task / reopen |

Full failure mode details: [references/recovery-workflow.md](references/recovery-workflow.md)

## Initialization Wizard

If Tier 0 missing, guide user:

1. Collect: Task Goal, Complexity (small/medium/large), Key Requirements
2. Create from templates: `task_state.md`, `plan.md`, `snapshot.md`
3. If multi-session/multi-agent/>10 phases: also create `decisions.md`
4. **Copy MRS rules to project AGENTS.md** for Codex/other agent compatibility (see [references/agents-md-snippet.md](references/agents-md-snippet.md))

## Plan Registry

`plan.md` must include a Plan Registry tracking all `docs/plans/*.md` files:

```markdown
## Plan Registry (docs/plans)
| File | Source Skill | Date | Status |
|------|-------------|------|--------|
```

**Strict boundary:** Only register files under `docs/plans/*.md`. Do NOT register CLAUDE.md, AGENTS.md, `.task-state/*`, or `docs/runbooks/*`.

Full cross-skill protocol: [references/multi-skill-integration.md](references/multi-skill-integration.md)

## File Standards

| File | Update Trigger | Method |
|------|----------------|--------|
| task_state.md | Phase transition, decision, todo change | **In-place edit**. Compress if >300 lines. |
| plan.md | Phase status change, new plan file | **In-place edit** (Registry append) |
| snapshot.md | Phase complete, blocker, major decision, session end | **Overwrite** (archive previous) |
| decisions.md | Stable conclusion reached | **Append only** |
| findings.md | After discoveries | **Append only** |
| progress.md | After each significant action | **Append only** |

**Forbidden paths:** `/.cursor/`, `/agent-tools/`, `/temp/`, `/tmp/`, `/.cache/`

Full standards: [references/artifact-standards.md](references/artifact-standards.md)

## Scripts

Run from the MRS directory. Locate scripts relative to this SKILL.md.

```bash
python <skill-root>/scripts/verify_mrs.py .          # Check MRS health
python <skill-root>/scripts/verify_mrs.py --json .    # JSON output for agents
python <skill-root>/scripts/generate_snapshot.py .    # Generate snapshot
python <skill-root>/scripts/generate_snapshot.py --archive .  # Generate + archive
```

## Codex / Multi-Agent Compatibility

When initializing MRS for a project that uses multiple agents (Claude Code, Codex, etc.):

1. Copy the content of [references/agents-md-snippet.md](references/agents-md-snippet.md) into the project's root `AGENTS.md`
2. This ensures all agents follow the same MRS update rules regardless of whether they have access to this skill

## Best Practices

**DO:**
- Update `task_state.md` in-place; keep Active Todos near the top
- Append to `progress.md` for every action
- **Overwrite** `snapshot.md` on key events (never append sections)
- Append stable conclusions to `decisions.md` (not `task_state.md`)
- Cite source files in all statements
- Register every new `docs/plans/` file in Plan Registry immediately
- Compress `task_state.md` when it exceeds 300 lines

**DON'T:**
- Rely on conversational memory
- Append dated sections to `task_state.md` (use `progress.md` / `decisions.md`)
- Leave completed todos in Active Todos list
- Infer todo status from `progress.md`
- Put non-plan files in Plan Registry
- Use forbidden temp paths
