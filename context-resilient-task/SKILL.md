---
name: context-resilient-task
description: Context-resilient task management with stateless recovery from artifacts. Use when starting multi-phase tasks, when task involves multiple sessions, after /clear or session interruption, or when you need to recover task state without relying on conversational memory. Implements three-tier MRS (Minimum Recovery Set), automatic artifact detection, anti-hallucination structured outputs, and degraded failure modes. Replaces planning-with-files with enhanced recovery capabilities.
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

## Quick Start

**On first invocation or session start:**

1. **Check for existing artifacts** (automatic)
2. **If MRS detected** → Enter recovery mode
3. **If MRS missing** → Initialize new task
4. **Output reconstructed state** using structured template
5. **Continue work**

## Minimum Recovery Set (MRS)

Three-tier system ensures reliable recovery:

### Tier 0: Core Required (MUST exist)
- `task_state.md` - Current state snapshot
- `plan.md` - Complete task plan
- `snapshot.md` - Timestamped checkpoint

**If missing:** STOP, run initialization wizard

### Tier 1: Important Context (SHOULD exist)
- `findings.md` - Research and discoveries
- `progress.md` - Session execution log
- `architecture.md` - Architecture (for system-level tasks)

**If missing:** WARN, ask user to confirm continuation

### Tier 2: Optional Context (MAY exist)
- `decisions.md` - Design decision records
- `blockers.md` - Current blockers
- Domain-specific artifacts

**If missing:** No action, continue normally

See [references/minimum-recovery-set.md](references/minimum-recovery-set.md) for complete MRS specification.

## Automatic Recovery

When skill starts, it automatically:

```python
1. Scan current directory for Tier 0 files
2. If all present → Recovery mode
3. If any missing → Initialization mode
4. Check Tier 1, emit warnings if missing
5. Load and validate artifact consistency
6. Output "Reconstructed Task State"
7. Continue from last checkpoint
```

No user action required. Just invoke the skill.

## Structured Output Template

At key checkpoints, MUST output this structure:

```markdown
## Reconstructed Task State

### Goal
(from artifact: task_state.md:3)
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
✅ task_state.md (from template)
✅ plan.md (generated from requirements)
✅ snapshot.md (initial checkpoint)

Ready to begin!
```

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
9. Update artifacts after each phase
10. Generate snapshot at checkpoints
```

### Recovery After Interruption

```
1. New session opens
2. Navigate to project directory
3. Invoke skill
4. MRS detected automatically
5. Recovery mode activates
6. State reconstructed from files
7. Work continues seamlessly
```

### Cross-Session, Cross-IDE

```
1. Work in Cursor, create artifacts
2. Close Cursor
3. Open VS Code
4. Navigate to same directory
5. Invoke skill
6. Recovery mode activates
7. Full context restored
```

## Scripts

**Verify MRS:**
```bash
python scripts/verify_mrs.py .
```

Checks:
- Tier 0/1/2 file presence
- Artifact structure validity
- Snapshot recency
- Forbidden paths

**Generate Snapshot:**
```bash
python scripts/generate_snapshot.py .
python scripts/generate_snapshot.py --archive .
```

Creates:
- `snapshot.md` (current)
- `snapshots/snapshot_YYYYMMDD_HHMM.md` (archived)

## File Standards

**Required structure:** See [references/artifact-standards.md](references/artifact-standards.md)

**Update frequency:**
- `task_state.md` → After every phase transition
- `plan.md` → When scope changes
- `snapshot.md` → Every 2-4 hours or before ending session
- `findings.md` → Immediately after discoveries
- `progress.md` → After each significant action

**Forbidden paths:**
- `/.cursor/` (ephemeral)
- `/agent-tools/` (temporary)
- `/temp/`, `/tmp/` (not persistent)
- `/.cache/` (volatile)

## Recovery Workflow

Complete recovery process: [references/recovery-workflow.md](references/recovery-workflow.md)

Key steps:
1. Load Tier 0 artifacts
2. Validate consistency
3. Check Tier 1 (warn if missing)
4. Output reconstructed state
5. Confirm with user
6. Continue work

## Comparison to planning-with-files

| Feature | planning-with-files | context-resilient-task |
|---------|---------------------|------------------------|
| Artifact tracking | task_plan.md, findings.md, progress.md | + MRS tiers, task_state.md, snapshot.md |
| Recovery | Manual re-read | Automatic detection & reconstruction |
| Validation | None | verify_mrs.py script |
| Snapshot | None | Timestamped checkpoints |
| Failure modes | Unspecified | Degraded recovery (Tier 0 stop, Tier 1 warn) |
| Output structure | Free-form | Fixed template at key checkpoints |
| Anti-hallucination | Implicit | Explicit rules + source attribution |

## Best Practices

**DO:**
✅ Update task_state.md after every phase
✅ Generate snapshots every 2-4 hours
✅ Use structured template at checkpoints
✅ Cite source files in all statements
✅ Mark unknowns explicitly

**DON'T:**
❌ Rely on conversational memory
❌ Guess information not in artifacts
❌ Use forbidden temp paths
❌ Skip MRS verification
❌ Rename files mid-task

## Extending for Domain-Specific Tasks

For specialized workflows, add Tier 2 artifacts:

**Backend development:**
- `api_design.md`
- `database_schema.md`
- `deployment.md`

**Frontend development:**
- `components.md`
- `state_management.md`
- `routing.md`

**Data pipeline:**
- `data_flow.md`
- `transformations.md`
- `validation_rules.md`

Tier 2 files are optional but enhance context quality.
