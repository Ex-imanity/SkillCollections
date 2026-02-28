# Multi-Skill Integration Guide

How `context-resilient-task` coordinates with other skills that produce plan files.

## The Plan Registry Problem

In long-running projects, `writing-plans` and `brainstorming` produce multiple plan files over time:

```
docs/plans/
├── 2026-02-13-migration-design.md          ← brainstorming
├── 2026-02-13-migration-implementation.md  ← writing-plans
├── 2026-02-17-feature-x-design.md          ← brainstorming
├── 2026-02-17-feature-x-implementation.md  ← writing-plans
└── ...
```

Without a registry, these become "orphan plan files" — the MRS has no record of them, and recovery sessions miss their context entirely.

## Plan Registry Format

Every `plan.md` MUST include a Plan Registry section at the bottom:

```markdown
## Plan Registry (docs/plans)

| File | Source Skill | Date | Status | MRS Note |
|------|-------------|------|--------|----------|
| 2026-02-13-migration-implementation.md | writing-plans | 2026-02-13 | completed | Phases 1-3 in plan.md main body |
| 2026-02-17-feature-x-design.md | brainstorming | 2026-02-17 | completed | Reference only, no execution phases |
| 2026-02-17-feature-x-implementation.md | writing-plans | 2026-02-17 | in_progress | Current execution target |
| 2026-02-24-ui-portal-implementation.md | writing-plans | 2026-02-24 | pending | Not yet started |
```

**Status values:**
- `pending` — File exists but execution not started
- `in_progress` — Currently being executed (only one file should have this at a time)
- `completed` — All phases in this file have been executed and verified
- `abandoned` — Superseded or no longer relevant

## Cross-Skill Handoff Protocol

When any other skill produces a new file in `docs/plans/`:

### Agent MUST immediately:

1. **Register the file** — Add a row to `plan.md` Plan Registry with `status: pending`
2. **Update task_state.md** — Set `Current Phase` to reference the new file if it becomes the active plan
3. **Generate a snapshot** — This is a key event trigger

### When starting execution of a registered plan:

1. Change its status in Plan Registry from `pending` → `in_progress`
2. Update `task_state.md` → Current Phase to point to it
3. If a previous plan was `in_progress`, set it to `completed` first

### When execution of a plan file is complete:

1. Change status in Plan Registry from `in_progress` → `completed`
2. Update `task_state.md` with summary of what was accomplished
3. Generate a snapshot

## Recommended Directory Structure

```
project/
  ├── docs/plans/              # All design + implementation docs
  │   ├── YYYY-MM-DD-design.md        ← from brainstorming
  │   ├── YYYY-MM-DD-implementation.md ← from writing-plans
  │   └── ...
  │
  ├── .task-state/             # MRS (context-resilient-task)
  │   ├── task_state.md        # Source of truth (in-place updated)
  │   ├── plan.md              # Active plan + Plan Registry
  │   ├── snapshot.md          # Latest checkpoint
  │   ├── findings.md          # Discoveries (append-only)
  │   ├── progress.md          # Session log (append-only)
  │   ├── decisions.md         # ADRs (Tier 2)
  │   ├── blockers.md          # Blockers (Tier 2)
  │   └── archive/             # Completed MRS snapshots
  │
  └── src/                     # Code being developed
```

**Key role separation:**
- `docs/plans/` files — Immutable after creation; read-only reference during execution
- `plan.md` — Living registry that tracks status of all docs/plans files + current active plan
- `task_state.md` — Real-time execution state; in-place updated only

## Initialization from Existing Plans

When the MRS is being created after plan files already exist:

```bash
# Step 1: Create MRS directory
mkdir .task-state

# Step 2: Initialize from the most recent implementation plan
# Copy it as plan.md baseline, then add Plan Registry
cp docs/plans/YYYY-MM-DD-implementation.md .task-state/plan.md

# Step 3: Append Plan Registry to plan.md listing all docs/plans files
# (Claude should scan docs/plans/ and build the registry table)

# Step 4: Create task_state.md from template
cp <skill-root>/assets/task_state.template.md .task-state/task_state.md
```

## Skill Compatibility Matrix

| Skill | Relationship | Notes |
|-------|-------------|-------|
| brainstorming | ✅ Complements | Design phase → register output in Plan Registry |
| writing-plans | ✅ Complements | Plan output → register in Plan Registry, set status=pending |
| using-git-worktrees | ✅ Compatible | Place MRS in worktree root |
| executing-plans | ⚠️ Overlaps | Both manage execution; choose one or nest |
| subagent-driven-development | ✅ Compatible | Subagents reference MRS context |
| finishing-a-development-branch | ✅ Complements | On merge: set task_state.md status=completed, archive MRS |

## Task Completion and Archival

When all work is done:

1. Set `task_state.md` → `status: completed`
2. Verify all Plan Registry entries are `completed` or `abandoned`
3. Generate final snapshot with `--archive` flag
4. Optionally move `.task-state/` to `.task-state/archive/YYYY-MM-DD/`

On next invocation, the skill detects `status=completed` and prompts archival instead of resuming.
