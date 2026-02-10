# Minimum Recovery Set (MRS)

The MRS defines the minimum artifacts required to recover task context without relying on conversational memory.

## Three-Tier Architecture

### Tier 0: Core Required (MUST exist)
- `task_state.md` - Current task state snapshot
- `plan.md` - Complete task plan with phases
- `snapshot.md` - Latest timestamped snapshot

**Failure Mode:** Missing any Tier 0 file → STOP, run initialization wizard

### Tier 1: Important Context (SHOULD exist)
- `findings.md` - Research and discoveries
- `progress.md` - Session execution log
- `architecture.md` - System architecture (for architectural tasks)

**Failure Mode:** Missing Tier 1 → WARNING, ask user to confirm continuation

### Tier 2: Optional Context (MAY exist)
- `decisions.md` - Design decision records
- `blockers.md` - Current blockers
- Domain-specific artifacts

**Failure Mode:** Missing Tier 2 → No action, continue normally

## Detection Logic

When skill starts:
1. Check current directory for Tier 0 files
2. If all Tier 0 present → Enter recovery mode
3. If any Tier 0 missing → Enter initialization mode
4. Check Tier 1, warn if missing
5. Tier 2 is purely informational

## Recovery vs Initialization

**Recovery Mode:**
- Read all available MRS files
- Reconstruct task state
- Output "Reconstructed Task State" section
- Continue work

**Initialization Mode:**
- Offer to create missing Tier 0 files
- Use templates from assets/
- Guide user through setup
- Once complete, enter recovery mode
