---
name: context-resilient-task
description: Context-resilient task management with stateless recovery from artifacts. Use when starting multi-phase tasks, when task involves multiple sessions, after /clear or session interruption, or when you need to recover task state without relying on conversational memory. Implements three-tier MRS (Minimum Recovery Set), on-invoke artifact detection, anti-hallucination structured outputs, and degraded failure modes. Replaces planning-with-files with enhanced recovery capabilities.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Context-Resilient Task

Context-resilient task management that enables stateless recovery from artifacts, replacing conversational memory with durable files.

## Core Principle

> **Context is not input, it's output.**

Never rely on conversational memory. Always reconstruct task state from artifacts on disk.

### File Authority

- **`task_state.md`** — Source of truth for current state. Always update **in-place** (edit existing fields). Never append dated sections; that is `progress.md`'s job.
- **`progress.md`** — Append-only chronological log. Never overwrite; only append.
- On conflict between the two, `task_state.md` wins.

## Quick Start

**On invocation:**

1. Check for existing artifacts (on invocation)
2. If MRS detected → Enter recovery mode
3. If MRS missing → Initialize new task
4. Output reconstructed state using structured template
5. Continue work

## Minimum Recovery Set (MRS)

### Tier 0: Core Required (MUST exist)
- `task_state.md` - Current state (in-place updated, never appended)
- `plan.md` - Task plan + Plan Registry of all docs/plans files
- `snapshot.md` - Latest checkpoint

**If missing:** STOP, run initialization wizard

### Tier 1: Important Context (SHOULD exist)
- `findings.md` - Research and discoveries
- `progress.md` - Session execution log (append-only)
- `architecture.md` - Architecture (for system-level tasks)

**If missing:** WARN, ask user to confirm continuation

### Tier 2: Optional Context (MAY exist)
- `decisions.md` - Design decision records
- `blockers.md` - Current blockers
- Domain-specific artifacts

**If missing:** No action, continue normally

See [references/minimum-recovery-set.md](references/minimum-recovery-set.md) for complete MRS specification.

## On-Invoke Detection

On every invocation, run this detection flow:

```
1. Scan MRS directory for Tier 0 files
2. If status=completed in task_state.md → Skip recovery, prompt archival
3. If all Tier 0 present → Recovery mode
4. If any Tier 0 missing → Initialization mode
5. Check Tier 1, emit warnings if missing
6. Validate artifact consistency
7. Output "Reconstructed Task State"
8. Continue from last checkpoint
```

**Task lifecycle (status field in task_state.md):**
- `active` — Work in progress
- `paused` — Temporarily halted, resumable
- `blocked` — Cannot proceed without external resolution
- `completed` — Done; skip recovery on next invocation, prompt to archive MRS

## Structured Output Template

At key checkpoints, MUST output this structure:

```markdown
## Reconstructed Task State

### Goal
(from artifact: task_state.md:Goal)
<goal statement>

### What Has Been Done
- <action> (source: progress.md, timestamp)
- <action> (source: plan.md, Phase N complete)

### Current Artifacts
- task_state.md (last updated: timestamp)
- plan.md (last updated: timestamp)
- snapshot.md (last updated: timestamp)

### Unknown / Missing
- <info not in artifacts>

### Next Required Action
<single concrete step>

### Artifact to Be Produced
<filename> - <purpose>
```

**When to use:**
- Task recovery (always)
- Phase transitions (always)
- Major decisions (always)
- User requests status (always)
- Errors/blockers (always)

See [references/output-template.md](references/output-template.md) for complete specification.

## Anti-Hallucination Rules

1. **Source Attribution:** Every fact cites source file
2. **Explicit Unknowns:** If not in artifacts, mark "Unknown"
3. **No Inference:** Don't fill gaps with assumptions
4. **Single Next Action:** Only one concrete step at a time
5. **Output Artifact:** Every action produces/updates an artifact

## Todo Management

Todos must have a single canonical location to prevent "forgotten completion" failures.

**In `task_state.md`, maintain two explicit sections:**

```markdown
## Active Todos
- [ ] <item> (added: date, source: plan/user)
- [ ] <item>

## Completed Items
- [x] <item> (completed: date)
- [x] <item>
```

**Rules:**
- When completing a todo: **remove from Active Todos**, **append to Completed Items**. Never leave completed items in Active Todos with a checkmark.
- When asked about todo status: read **only Active Todos** for pending items; read **only Completed Items** for done items.
- Never infer completion status from progress.md; always read task_state.md as authoritative.
- If `task_state.md` grows beyond 300 lines: compress by summarizing completed phases into a one-line entry and moving detail to `progress.md`.

## Failure Modes (Degraded Recovery)

**Missing Tier 0 (STOP):**
```
❌ Cannot recover: missing task_state.md

Options:
1. Initialize new task
2. Manually create missing files
3. Cancel

Choose option (1-3):
```

**Missing Tier 1 (WARN):**
```
⚠️  WARNING: Missing findings.md
Recovery quality may be reduced.

Continue anyway? (y/n)
```

**Stale snapshot (WARN):**
```
⚠️  snapshot.md is 9 days old
Task context may be outdated.

Options:
1. Generate fresh snapshot
2. Continue with stale snapshot
3. Review manually
```

**Conflicting artifacts (STOP):**
```
⚠️  CONFLICT: plan.md says Phase 2, task_state.md says Phase 1

Cannot safely proceed. Which is correct?
```

**Task already completed (PROMPT):**
```
ℹ️  task_state.md status=completed

This task is marked done. Options:
1. Archive MRS to .task-state/archive/
2. Start new task (reinitialize)
3. Reopen task (set status=active)
```

## Initialization Wizard

If Tier 0 missing, guide user through setup:

```markdown
I'll help create the required files. Please provide:

1. **Task Goal** (one sentence):
   >

2. **Estimated Complexity** (small/medium/large):
   >

3. **Key Requirements** (3-5 bullet points):
   > -
   > -

Creating:
✅ task_state.md (from template with status=active)
✅ plan.md (with Plan Registry section)
✅ snapshot.md (initial checkpoint)

Ready to begin!
```

**`plan.md` minimum structure:**

```markdown
## Plan: <task name>

### Phase 1: <name> [status: pending|in_progress|complete|blocked]
- Step 1.1: ...
- Step 1.2: ...

### Phase 2: <name> [status: pending]
...

## Plan Registry (docs/plans)
| File | Source Skill | Date | Status |
|------|-------------|------|--------|
| <filename> | writing-plans | YYYY-MM-DD | pending|in_progress|completed |
```

The Plan Registry tracks every file produced by `writing-plans`/`brainstorming` under `docs/plans/`. See [references/multi-skill-integration.md](references/multi-skill-integration.md) for the full handoff protocol.

## Workflow

### Standard Task Flow

```
1. Skill invoked
2. Check for MRS → Found
3. Load Tier 0 artifacts
4. Validate consistency
5. Load Tier 1 artifacts (warn if missing)
6. Output "Reconstructed Task State"
7. Confirm with user
8. Continue from Next Action
9. Update task_state.md in-place after each phase
10. Append to progress.md after each action
11. Generate snapshot on key events (see File Standards)
```

### Recovery After Interruption

```
1. New session opens
2. Invoke skill
3. MRS detected on invocation
4. Recovery mode activates
5. State reconstructed from task_state.md (source of truth)
6. Active Todos read from task_state.md##Active Todos
7. Work continues seamlessly
```

## Scripts

Both scripts live in this skill's `scripts/` directory. Run them from the MRS directory with `.` as the target argument. Locate the scripts relative to where this SKILL.md was loaded from.

**Verify MRS** — checks Tier 0/1/2 presence, consistency, forbidden paths:
```bash
python <skill-root>/scripts/verify_mrs.py .
```

**Generate Snapshot** — creates/archives `snapshot.md`:
```bash
python <skill-root>/scripts/generate_snapshot.py .
python <skill-root>/scripts/generate_snapshot.py --archive .
```

## File Standards

**Required structure:** See [references/artifact-standards.md](references/artifact-standards.md)

**Update rules:**
- `task_state.md` → In-place edit after every phase transition or status change. Compress if >300 lines.
- `plan.md` → Update Plan Registry when new docs/plans file is created; update phase status in-place.
- `snapshot.md` → Generate on **events**: phase complete, blocker encountered, major decision made, session ending.
- `findings.md` → Append immediately after discoveries.
- `progress.md` → Append after each significant action (never overwrite).

**Forbidden paths:**
- `/.cursor/` (ephemeral)
- `/agent-tools/` (temporary)
- `/temp/`, `/tmp/` (not persistent)
- `/.cache/` (volatile)

## Cross-Skill Integration

When `writing-plans` or `brainstorming` produces a new file in `docs/plans/`:

1. Add the file to `plan.md` → Plan Registry with `status: pending`
2. Update `task_state.md` → Current Phase to reference it
3. Generate a snapshot (event trigger)

Full protocol: [references/multi-skill-integration.md](references/multi-skill-integration.md)

**Recommended workflow with other skills:**

```
brainstorming → docs/plans/YYYY-MM-DD-design.md
writing-plans → docs/plans/YYYY-MM-DD-implementation.md
  ↓ Register in plan.md Plan Registry
context-resilient-task (init) → MRS created
  ↓ Execution
[writing-plans produces another plan]
  ↓ Register in Plan Registry + snapshot
context-resilient-task (recover) → State reconstructed
finishing-a-development-branch → Merge/PR/cleanup
  ↓ Set status=completed, archive MRS
```

## Best Practices

**DO:**
✅ Update `task_state.md` in-place (edit existing fields, never append dated blocks)
✅ Append to `progress.md` for every action
✅ Generate snapshots on key events (phase complete, blocker, major decision)
✅ Cite source files in all statements
✅ Mark unknowns explicitly
✅ Register every new docs/plans file in Plan Registry immediately
✅ Compress `task_state.md` when it exceeds 300 lines

**DON'T:**
❌ Rely on conversational memory
❌ Append new dated sections to `task_state.md` (use `progress.md` instead)
❌ Leave completed todos in Active Todos list
❌ Infer todo status from `progress.md`; always read `task_state.md`
❌ Use forbidden temp paths
❌ Skip MRS verification
❌ Rename files mid-task
