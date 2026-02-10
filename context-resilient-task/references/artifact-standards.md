# Artifact Standards

File naming, structure, and path conventions to ensure reliable recovery.

## Naming Conventions

### Required Files (Tier 0)

**task_state.md**
- Single source of truth for current state
- MUST be updated after every phase transition
- MUST include timestamp of last update

**plan.md**
- Complete task plan with all phases
- Phase status: `pending`, `in_progress`, `complete`, `blocked`
- MUST NOT be renamed (no `plan_v2.md` or `plan_final.md`)

**snapshot.md**
- Timestamped snapshot of current state
- Created/updated at key checkpoints
- Filename format: `snapshot.md` (always current) OR `snapshot_YYYYMMDD_HHMM.md` (archived)

### Context Files (Tier 1)

**findings.md**
- Research, discoveries, learnings
- Append-only (preserve history)

**progress.md**
- Session execution log
- Chronological entries with timestamps

**architecture.md**
- System architecture and design
- For architectural/system-level tasks only

### Optional Files (Tier 2)

**decisions.md**
- Design decision records (ADR format)

**blockers.md**
- Current blockers and open questions

**Domain-specific:**
- `api_design.md`
- `database_schema.md`
- `deployment.md`
- etc.

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

These paths are ephemeral and will not survive session boundaries.

## File Structure Standards

### task_state.md Format

```markdown
# Task State

**Last Updated:** 2026-02-10 14:45:00
**Updated By:** Claude (session abc123)

## Goal
<one-sentence goal>

## Current Phase
Phase 2: Implementation

## Status
in_progress

## Last Completed Action
- Completed Phase 1: Planning
- Created initial architecture.md
- Set up project structure

## Next Action
Implement user authentication module

## Open Questions
- Token expiration policy (need decision)
- Database choice (PostgreSQL vs MongoDB)

## Artifacts
- plan.md (updated 2026-02-10 09:00)
- findings.md (updated 2026-02-10 12:30)
- progress.md (updated 2026-02-10 14:40)
- architecture.md (updated 2026-02-10 10:15)
```

### snapshot.md Format

```markdown
# Snapshot: 2026-02-10 14:45

## Context
Working on Phase 2 (Implementation) of user authentication system.

## Recent Progress
- Completed user model with password hashing
- Implemented /register endpoint
- Added unit tests (all passing)

## Current Focus
About to start /login endpoint implementation

## Blockers
- Need decision on token expiration (30min vs 24h)
- Waiting for clarification on refresh token strategy

## Files Modified
- src/models/user.py (created)
- src/routes/auth.py (created)
- tests/test_auth.py (created)

## Next Session Should Know
- All tests are passing
- /register works, ready for /login
- Token policy needs decision before proceeding
```

## Update Frequency

| File | Update Trigger |
|------|----------------|
| task_state.md | After every phase transition, major decision, or blocker |
| plan.md | When phases change, new phases added, or scope adjusted |
| snapshot.md | Every 2-4 hours of active work, or before ending session |
| findings.md | Immediately after any discovery or research |
| progress.md | After each significant action (file created, test passed, etc.) |

## Validation Rules

### Required Fields

**task_state.md:**
- `Last Updated` timestamp (ISO 8601)
- `Goal` section (non-empty)
- `Current Phase` (must match plan.md)
- `Next Action` (concrete, actionable)

**plan.md:**
- At least one phase defined
- Each phase has status: `pending|in_progress|complete|blocked`
- Phases numbered/ordered

**snapshot.md:**
- Timestamp in filename or header
- `Context` section
- `Next Session Should Know` section

### Consistency Checks

```python
def validate_consistency():
    # Check 1: task_state phase matches plan
    state_phase = parse_task_state()["current_phase"]
    plan_phase = get_current_phase_from_plan()
    assert state_phase == plan_phase, "Phase mismatch"

    # Check 2: snapshot is recent
    snapshot_age = now() - parse_snapshot_timestamp()
    assert snapshot_age < 7 days, "Snapshot stale"

    # Check 3: no forbidden paths
    for artifact in list_artifacts():
        for forbidden in FORBIDDEN_SUBSTRINGS:
            assert forbidden not in artifact, f"Forbidden path: {artifact}"
```

## Recovery-Friendly Practices

### DO:
✅ Use consistent filenames (`task_state.md`, not `state.md`)
✅ Include timestamps in updates
✅ Make task_state.md self-contained
✅ Link between artifacts explicitly
✅ Archive old snapshots rather than deleting

### DON'T:
❌ Rename files mid-task (`plan_v2.md`)
❌ Use temp directories for important files
❌ Rely on file order or implicit structure
❌ Store state in conversation memory
❌ Use relative references without context

## Example Artifact Tree

```
project-root/
├── task_state.md          # Current state (Tier 0)
├── plan.md                # Task plan (Tier 0)
├── snapshot.md            # Latest snapshot (Tier 0)
├── findings.md            # Research log (Tier 1)
├── progress.md            # Session log (Tier 1)
├── architecture.md        # Architecture (Tier 1)
├── decisions.md           # ADRs (Tier 2)
├── blockers.md            # Current blockers (Tier 2)
└── snapshots/             # Archived snapshots
    ├── snapshot_20260210_0900.md
    ├── snapshot_20260210_1200.md
    └── snapshot_20260210_1445.md
```
