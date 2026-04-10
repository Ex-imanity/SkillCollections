# Artifact Standards

File naming, structure, and path conventions to ensure reliable recovery.

## Naming Conventions

### Required Files (Tier 0)

**task_state.md**
- Single source of truth for current state
- MUST be updated **in-place** (edit existing fields) after every phase transition
- MUST include timestamp of last update
- MUST include `Active Todos` section **near the top** (immediately after Status)
- MUST include `Completed Items` section (single-line summaries only)
- If file exceeds 300 lines: compress by summarizing completed phases into a single line, moving detail to `progress.md`
- NEVER append new dated sections; all history belongs in `progress.md` or `decisions.md`

**plan.md**
- Complete task plan with all phases
- Phase status: `pending`, `in_progress`, `complete`, `blocked`
- MUST NOT be renamed (no `plan_v2.md` or `plan_final.md`)
- MUST include Plan Registry section (see Plan Registry below)

**snapshot.md**
- Timestamped snapshot of current state
- **OVERWRITE** entire file on each update; do NOT append new sections
- Archive previous version before overwriting (use `generate_snapshot.py --archive`)
- Filename format: `snapshot.md` (always current) OR `snapshot_YYYYMMDD_HHMM.md` (archived)

### Context Files (Tier 1)

**findings.md**
- Research, discoveries, learnings
- Append-only (preserve history)

**progress.md**
- Session execution log
- Chronological entries with timestamps
- Append-only; NEVER overwrite or rewrite existing entries
- On conflict with task_state.md, task_state.md is authoritative

**architecture.md**
- System architecture and design
- For architectural/system-level tasks only

**decisions.md**
- Stable conclusions, design decisions, scope changes
- Append-only (new entries at bottom)
- **Required** when: multi-session, multi-agent, or >10 phases
- Optional for small/single-session tasks
- This is where "Latest Stable Conclusions" belong — NOT in task_state.md

### Optional Files (Tier 2)

**blockers.md**
- Current blockers and open questions

**Domain-specific:**
- `api_design.md`, `database_schema.md`, `deployment.md`, etc.

## Forbidden Paths

NEVER use these as artifact dependencies:

```python
FORBIDDEN_SUBSTRINGS = [
    "/.cursor/",
    "/agent-tools/",
    "/temp/",
    "/tmp/",
    "/.cache/",
]
```

## File Structure Standards

### task_state.md Format

```markdown
# Task State

**Last Updated:** 2026-02-10 14:45:00
**Updated By:** Claude (session abc123)

## Goal
<one-sentence goal>

## Status
in_progress

## Active Todos
- [ ] Implement auth module (added: 2026-02-10, source: plan Phase 2)
- [ ] Write unit tests (added: 2026-02-10, source: user request)

## Current Phase
Phase 2: Implementation

## Next Action
Implement user authentication module

## Completed Items
- [x] Design database schema (completed: 2026-02-10)
- [x] Set up project structure (completed: 2026-02-09)

## Open Questions
- Token expiration policy (need decision)

## Artifacts
- plan.md (updated 2026-02-10 09:00)
- findings.md (updated 2026-02-10 12:30)
- progress.md (updated 2026-02-10 14:40)

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
```

**Key structural rules:**
- `Active Todos` MUST appear before `Current Phase` (within the first ~30 lines)
- Each todo is a **single line**. Detailed context references plan files or decisions.md, not inline sub-lists.
- `Completed Items` uses **single-line summaries**. Detailed verification belongs in `progress.md`.

### snapshot.md Format

```markdown
<!-- OVERWRITE THIS FILE on each update. Do NOT append. Archive previous first. -->
# Snapshot: 2026-02-10 14:45

## Context
Working on Phase 2 (Implementation) of user authentication system.

## Recent Progress
- Completed user model with password hashing
- Implemented /register endpoint

## Current Focus
About to start /login endpoint implementation

## Blockers
- Need decision on token expiration (30min vs 24h)

## Files Modified
- src/models/user.py (created)
- src/routes/auth.py (created)

## Next Session Should Know
- All tests are passing
- /register works, ready for /login
- Token policy needs decision before proceeding
```

### decisions.md Format

```markdown
# Decisions

Append-only log of stable conclusions and design decisions.

## 2026-02-10: Token expiration policy
- Decision: Use 24h access tokens with 7-day refresh tokens
- Reason: Balance between security and UX for internal tool
- Source: User confirmation in session abc123

## 2026-02-11: Database choice
- Decision: PostgreSQL over MongoDB
- Reason: Strong schema enforcement needed for audit trail
- Source: Architecture review in findings.md
```

## Todo Management

`task_state.md` MUST contain exactly two todo sections. These are the **only** authoritative source for pending and completed work.

```markdown
## Active Todos
- [ ] <single-line description> (added: YYYY-MM-DD, source: plan Phase N / user request)

## Completed Items
- [x] <single-line summary> (completed: YYYY-MM-DD)
```

**Rules:**
- Completing a todo = **remove from Active Todos** + **append to Completed Items**. Never mark in-place with `[x]` inside Active Todos.
- When reporting todo status: read **Active Todos only** for what is pending. Read **Completed Items only** for what is done. Never infer from `progress.md`.
- Both sections must be present even when empty.
- Each todo entry is a **single line**. If context is needed, reference an external file: `(see decisions.md 2026-02-10)` or `(see docs/plans/2026-02-10-impl.md Phase 3)`.
- `Active Todos` MUST be positioned near the **top** of `task_state.md` (immediately after `## Status`), so recovery always reads it first.

## Plan Registry

`plan.md` MUST include a Plan Registry at the bottom:

```markdown
## Plan Registry (docs/plans)
| File | Source Skill | Date | Status |
|------|-------------|------|--------|
| 2026-02-13-migration-implementation.md | writing-plans | 2026-02-13 | completed |
```

**Strict boundary — only register `docs/plans/*.md` files.** Do NOT register:
- `CLAUDE.md` / `AGENTS.md` (agent auto-loads these)
- `.task-state/*` (MRS files themselves)
- `docs/runbooks/*` (operational guides, not plans)

If other reference files need tracking, use a separate **Reference Index** section in `plan.md`.

## Update Frequency

| File | Update Trigger | Method |
|------|----------------|--------|
| task_state.md | Phase transition, major decision, blocker, todo change | **In-place edit** |
| plan.md | Phase status change, new docs/plans file created | **In-place edit** (Plan Registry append) |
| snapshot.md | Phase complete, blocker encountered, major decision, session ending | **Overwrite** (archive previous with `--archive`) |
| decisions.md | Stable conclusion reached, scope change, design decision | **Append only** |
| findings.md | Immediately after any discovery | **Append only** |
| progress.md | After each significant action | **Append only** |

## Validation Rules

### Required Fields

**task_state.md:**
- `Last Updated` timestamp
- `Status` field: `active | paused | blocked | completed`
- `Goal` section (non-empty)
- `Active Todos` section (may be empty list, must be in top ~30 lines)
- `Current Phase` (must match plan.md)
- `Next Action` (concrete, actionable)
- `Completed Items` section (may be empty list)

**plan.md:**
- At least one phase defined
- Each phase has status: `pending|in_progress|complete|blocked`
- `Plan Registry` section (entries only from `docs/plans/`)

**snapshot.md:**
- Timestamp in header
- Single `## Context` section (not multiple — that indicates improper appending)
- `## Next Session Should Know` section

### Consistency Checks

```python
def validate_consistency():
    # Check 1: task_state phase matches plan
    state_phase = parse_task_state()["current_phase"]
    plan_phase = get_current_phase_from_plan()
    assert state_phase == plan_phase, "Phase mismatch"

    # Check 2: snapshot is recent (WARNING, not error)
    snapshot_age = now() - parse_snapshot_timestamp()
    if snapshot_age > 7 days:
        warn("Snapshot stale")

    # Check 3: no forbidden paths
    for artifact in list_artifacts():
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden not in artifact

    # Check 4: Active Todos in top 50 lines
    active_todos_line = find_section_line("## Active Todos")
    if active_todos_line > 50:
        warn("Active Todos too far from top")

    # Check 5: snapshot not appended
    context_count = count_occurrences("## Context", snapshot)
    if context_count > 1:
        warn("Snapshot appears appended, not overwritten")
```

## Example Artifact Tree

```
project-root/
├── .task-state/
│   ├── task_state.md          # Current state (Tier 0)
│   ├── plan.md                # Task plan + Registry (Tier 0)
│   ├── snapshot.md            # Latest snapshot (Tier 0)
│   ├── findings.md            # Research log (Tier 1)
│   ├── progress.md            # Session log (Tier 1)
│   ├── architecture.md        # Architecture (Tier 1)
│   ├── decisions.md           # Stable decisions (Tier 1, conditional)
│   ├── blockers.md            # Current blockers (Tier 2)
│   └── snapshots/             # Archived snapshots
│       ├── snapshot_20260210_0900.md
│       └── snapshot_20260210_1445.md
├── docs/plans/                # Plan files (registered in Plan Registry)
├── CLAUDE.md                  # Project constraints (NOT in Registry)
└── AGENTS.md                  # Agent guidelines (NOT in Registry)
```
