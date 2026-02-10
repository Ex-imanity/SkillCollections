# Context-Resilient Task Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a context-resilient task management skill that enables stateless recovery from artifacts, replacing planning-with-files with enhanced MRS validation, anti-hallucination mechanisms, and automatic session recovery.

**Architecture:** Fork planning-with-files and add three-tier MRS system (Tier 0: task_state.md/plan.md/snapshot.md required; Tier 1: findings.md/progress.md/architecture.md with warnings; Tier 2: optional). Implement automatic artifact detection, degraded failure modes, and structured output templates at key checkpoints.

**Tech Stack:** Python 3.11+, Markdown templates, Claude Code skill system

---

## Task 1: Reference Documentation - MRS Standard

**Files:**
- Create: `~/.claude/skills/context-resilient-task/references/minimum-recovery-set.md`

**Step 1: Write MRS reference documentation**

```markdown
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
```

**Step 2: Commit**

```bash
git add references/minimum-recovery-set.md
git commit -m "docs: add MRS standard reference"
```

---

## Task 2: Reference Documentation - Output Template

**Files:**
- Create: `~/.claude/skills/context-resilient-task/references/output-template.md`

**Step 1: Write output template reference**

```markdown
# Structured Output Template

This template MUST be used at key checkpoints to prevent hallucination and context drift.

## When to Use

**Always use at:**
1. Task recovery (entering from new session)
2. Phase transitions (A→B, B→C, etc.)
3. Major decision points
4. User requests for status update
5. Error/blocker encountered

**Optional for:**
- Routine progress updates
- Simple clarifications
- Tool execution results

## Template Structure

```markdown
## Reconstructed Task State

### Goal
(from artifact: <filename>)
<one-sentence goal>

### What Has Been Done
- <action> (source: <filename>, line X)
- <action> (source: progress.md, 2026-02-10 14:30)

### Current Artifacts
- task_state.md (last updated: 2026-02-10 14:45)
- plan.md (last updated: 2026-02-10 09:00)
- snapshot.md (last updated: 2026-02-10 14:45)
- findings.md (last updated: 2026-02-10 12:30)
- progress.md (last updated: 2026-02-10 14:40)

### Unknown / Missing
- <information not in artifacts>
- <ambiguous requirement needing clarification>

### Next Required Action
<single, concrete, low-risk next step>

### Artifact to Be Produced
<filename> - <purpose>
```

## Anti-Hallucination Rules

1. **Source Attribution:** Every fact MUST cite source file
2. **Explicit Unknowns:** If not in artifacts, mark as "Unknown"
3. **No Inference:** Do not fill gaps with "reasonable assumptions"
4. **Single Next Action:** Only one concrete next step
5. **Output Artifact:** Every action must produce/update an artifact

## Example

```markdown
## Reconstructed Task State

### Goal
(from artifact: task_state.md:3)
Implement user authentication module with JWT tokens

### What Has Been Done
- Created user model with password hashing (source: progress.md, 2026-02-10 10:30)
- Implemented /register endpoint (source: plan.md, Phase 1 marked complete)
- Added unit tests for registration (source: findings.md, "Tests passing" note)

### Current Artifacts
- task_state.md (last updated: 2026-02-10 14:00)
- plan.md (last updated: 2026-02-10 09:00)
- snapshot.md (last updated: 2026-02-10 14:00)
- findings.md (last updated: 2026-02-10 12:00)
- progress.md (last updated: 2026-02-10 13:45)
- architecture.md (last updated: 2026-02-10 09:30)

### Unknown / Missing
- Token expiration policy (not specified in artifacts)
- Refresh token strategy (mentioned in plan.md:45 but no decision recorded)

### Next Required Action
Create decisions.md to document token policy before implementing /login endpoint

### Artifact to Be Produced
decisions.md - Document JWT token expiration and refresh strategy
```
```

**Step 2: Commit**

```bash
git add references/output-template.md
git commit -m "docs: add structured output template"
```

---

## Task 3: Reference Documentation - Recovery Workflow

**Files:**
- Create: `~/.claude/skills/context-resilient-task/references/recovery-workflow.md`

**Step 1: Write recovery workflow documentation**

```markdown
# Recovery Workflow

Detailed steps for reconstructing task state from artifacts when entering a fresh session.

## Automatic Detection

On skill invocation:

```python
def detect_recovery_mode():
    tier0 = ["task_state.md", "plan.md", "snapshot.md"]
    missing = [f for f in tier0 if not exists(f)]

    if not missing:
        return "RECOVERY"
    else:
        return "INITIALIZATION"
```

## Recovery Mode Steps

### Step 1: Load Core Artifacts (Tier 0)

```bash
# Read in priority order
cat task_state.md
cat plan.md
cat snapshot.md
```

Parse to extract:
- **Goal:** Main objective
- **Current Phase:** Where we are in plan
- **Last Action:** What was done last
- **Next Action:** What should happen next

### Step 2: Load Context Artifacts (Tier 1)

```bash
# Check and load if present
[ -f findings.md ] && cat findings.md
[ -f progress.md ] && cat progress.md
[ -f architecture.md ] && cat architecture.md
```

If missing, emit warning:
```
⚠️  WARNING: Missing Tier 1 artifact: findings.md
This may reduce context quality. Continue anyway? (y/n)
```

### Step 3: Validate Consistency

Check for conflicts:
- Does task_state.md match plan.md current phase?
- Is snapshot.md timestamp recent (<24h)?
- Are there open questions in findings.md?

### Step 4: Output Reconstructed State

Use the structured template:

```markdown
## Reconstructed Task State

### Goal
(from artifact: task_state.md:3)
<goal extracted from task_state.md>

### What Has Been Done
<extract from progress.md and plan.md completed phases>

### Current Artifacts
<list all detected files with timestamps>

### Unknown / Missing
<identify gaps, ambiguities, or outdated info>

### Next Required Action
(from artifact: task_state.md:25)
<next action from task_state.md>

### Artifact to Be Produced
<expected output artifact>
```

### Step 5: Confirm and Continue

Ask user:
```
Recovered task state from artifacts. Does this look correct?
- Goal: <goal>
- Last completed: <last action>
- Next action: <next action>

Reply 'yes' to continue, or describe what's wrong.
```

## Initialization Mode Steps

If Tier 0 artifacts missing:

### Step 1: Explain Missing Files

```
Cannot recover task state. Missing required files:
- task_state.md (REQUIRED)
- plan.md (REQUIRED)
- snapshot.md (REQUIRED)

Would you like to initialize a new task? (y/n)
```

### Step 2: Run Initialization Wizard

```markdown
I'll help create the required files. Please provide:

1. **Task Goal** (one sentence):
   >

2. **Estimated Complexity** (small/medium/large):
   >

3. **Key Requirements** (3-5 bullet points):
   > -
   > -
   > -
```

### Step 3: Generate Initial Artifacts

Create from templates:
- `task_state.md` ← `assets/task_state.template.md`
- `plan.md` ← Generate phases from requirements
- `snapshot.md` ← `assets/snapshot.template.md`

### Step 4: Enter Recovery Mode

Once Tier 0 created, switch to recovery mode and continue.

## Edge Cases

### Corrupted Artifacts

If artifacts exist but are malformed:
```
⚠️  ERROR: task_state.md exists but is malformed
Cannot parse required fields: goal, current_phase

Options:
1. Regenerate task_state.md (will lose existing data)
2. Manually fix task_state.md and retry
3. Cancel and investigate

Choose option (1-3):
```

### Stale Snapshot

If snapshot.md is >7 days old:
```
⚠️  WARNING: snapshot.md is 9 days old (last updated 2026-02-01)
Task context may be outdated.

Options:
1. Generate fresh snapshot from current state
2. Continue with stale snapshot
3. Review and update manually

Choose option (1-3):
```

### Conflicting Information

If plan.md says Phase 2 complete but task_state.md says Phase 1:
```
⚠️  CONFLICT DETECTED:
- plan.md: Phase 2 complete (line 45)
- task_state.md: current_phase = "Phase 1" (line 8)

Cannot safely proceed. Please resolve conflict:
1. Which is correct?
2. Should I update task_state.md to match plan.md?
```
```

**Step 2: Commit**

```bash
git add references/recovery-workflow.md
git commit -m "docs: add recovery workflow guide"
```

---

## Task 4: Reference Documentation - Artifact Standards

**Files:**
- Create: `~/.claude/skills/context-resilient-task/references/artifact-standards.md`

**Step 1: Write artifact standards**

```markdown
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
```

**Step 2: Commit**

```bash
git add references/artifact-standards.md
git commit -m "docs: add artifact standards reference"
```

---

## Task 5: Python Script - MRS Verification

**Files:**
- Create: `~/.claude/skills/context-resilient-task/scripts/verify_mrs.py`

**Step 1: Write MRS verification script**

```python
#!/usr/bin/env python3
"""
Verify Minimum Recovery Set (MRS) completeness and consistency.

Usage:
    python verify_mrs.py [directory]

Exit codes:
    0: All Tier 0 files present and valid
    1: Missing Tier 0 files (recovery impossible)
    2: Tier 1 files missing (recovery degraded)
    3: Validation errors (files malformed)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import re

# MRS Tiers
TIER_0 = ["task_state.md", "plan.md", "snapshot.md"]
TIER_1 = ["findings.md", "progress.md", "architecture.md"]
TIER_2 = ["decisions.md", "blockers.md"]

FORBIDDEN_SUBSTRINGS = ["/.cursor/", "/agent-tools/", "/temp/", "/tmp/", "/.cache/"]


def check_file_exists(directory: Path, filename: str) -> bool:
    """Check if file exists in directory."""
    return (directory / filename).exists()


def validate_task_state(filepath: Path) -> tuple[bool, str]:
    """Validate task_state.md structure."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Required sections
        required = ["# Task State", "## Goal", "## Current Phase", "## Next Action"]
        missing = [sec for sec in required if sec not in content]

        if missing:
            return False, f"Missing sections: {', '.join(missing)}"

        # Check for timestamp
        if "**Last Updated:**" not in content:
            return False, "Missing Last Updated timestamp"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_plan(filepath: Path) -> tuple[bool, str]:
    """Validate plan.md structure."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Should have at least one phase
        if not re.search(r"##?\s+Phase\s+\d+", content):
            return False, "No phases found"

        # Check for phase statuses
        valid_statuses = ["pending", "in_progress", "complete", "blocked"]
        has_status = any(status in content.lower() for status in valid_statuses)

        if not has_status:
            return False, "No phase statuses found"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_snapshot(filepath: Path) -> tuple[bool, str]:
    """Validate snapshot.md structure and recency."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Extract timestamp from header
        match = re.search(r"# Snapshot:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", content)
        if not match:
            return False, "Missing or invalid timestamp in header"

        timestamp_str = match.group(1)
        snapshot_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
        age = datetime.now() - snapshot_time

        # Warn if >7 days old
        if age > timedelta(days=7):
            return False, f"Snapshot is {age.days} days old (stale)"

        # Check required sections
        required = ["## Context", "## Next Session Should Know"]
        missing = [sec for sec in required if sec not in content]

        if missing:
            return False, f"Missing sections: {', '.join(missing)}"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading file: {e}"


def check_forbidden_paths(directory: Path) -> list[str]:
    """Check for artifacts in forbidden paths."""
    violations = []

    for item in directory.rglob("*.md"):
        path_str = str(item)
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden in path_str:
                violations.append(f"{item}: contains forbidden substring '{forbidden}'")

    return violations


def verify_mrs(directory: Path) -> dict:
    """Verify MRS completeness and validity."""
    results = {
        "tier0": {"present": [], "missing": [], "invalid": []},
        "tier1": {"present": [], "missing": []},
        "tier2": {"present": [], "missing": []},
        "forbidden_paths": [],
        "exit_code": 0,
    }

    # Check Tier 0 (required)
    for filename in TIER_0:
        filepath = directory / filename
        if not filepath.exists():
            results["tier0"]["missing"].append(filename)
            results["exit_code"] = 1
        else:
            # Validate structure
            if filename == "task_state.md":
                valid, msg = validate_task_state(filepath)
            elif filename == "plan.md":
                valid, msg = validate_plan(filepath)
            elif filename == "snapshot.md":
                valid, msg = validate_snapshot(filepath)
            else:
                valid, msg = True, "Valid"

            if valid:
                results["tier0"]["present"].append(filename)
            else:
                results["tier0"]["invalid"].append(f"{filename}: {msg}")
                results["exit_code"] = 3

    # Check Tier 1 (warnings)
    for filename in TIER_1:
        if check_file_exists(directory, filename):
            results["tier1"]["present"].append(filename)
        else:
            results["tier1"]["missing"].append(filename)
            if results["exit_code"] == 0:
                results["exit_code"] = 2

    # Check Tier 2 (informational)
    for filename in TIER_2:
        if check_file_exists(directory, filename):
            results["tier2"]["present"].append(filename)
        else:
            results["tier2"]["missing"].append(filename)

    # Check forbidden paths
    results["forbidden_paths"] = check_forbidden_paths(directory)
    if results["forbidden_paths"] and results["exit_code"] == 0:
        results["exit_code"] = 3

    return results


def print_results(results: dict):
    """Print verification results."""
    print("=" * 60)
    print("MRS VERIFICATION REPORT")
    print("=" * 60)

    # Tier 0
    print("\n📋 TIER 0 (REQUIRED):")
    if results["tier0"]["present"]:
        print("  ✅ Present:", ", ".join(results["tier0"]["present"]))
    if results["tier0"]["missing"]:
        print("  ❌ MISSING:", ", ".join(results["tier0"]["missing"]))
    if results["tier0"]["invalid"]:
        print("  ⚠️  INVALID:")
        for msg in results["tier0"]["invalid"]:
            print(f"     - {msg}")

    # Tier 1
    print("\n📚 TIER 1 (IMPORTANT):")
    if results["tier1"]["present"]:
        print("  ✅ Present:", ", ".join(results["tier1"]["present"]))
    if results["tier1"]["missing"]:
        print("  ⚠️  Missing:", ", ".join(results["tier1"]["missing"]))

    # Tier 2
    print("\n📝 TIER 2 (OPTIONAL):")
    if results["tier2"]["present"]:
        print("  ✅ Present:", ", ".join(results["tier2"]["present"]))
    if results["tier2"]["missing"]:
        print("  ℹ️  Not present:", ", ".join(results["tier2"]["missing"]))

    # Forbidden paths
    if results["forbidden_paths"]:
        print("\n🚫 FORBIDDEN PATH VIOLATIONS:")
        for violation in results["forbidden_paths"]:
            print(f"  - {violation}")

    # Summary
    print("\n" + "=" * 60)
    exit_code = results["exit_code"]

    if exit_code == 0:
        print("✅ MRS VALID - Recovery possible")
    elif exit_code == 1:
        print("❌ MRS INCOMPLETE - Recovery impossible (missing Tier 0)")
    elif exit_code == 2:
        print("⚠️  MRS DEGRADED - Recovery possible with warnings (missing Tier 1)")
    elif exit_code == 3:
        print("❌ MRS INVALID - Validation errors detected")

    print("=" * 60)


def main():
    """Main entry point."""
    # Get directory from args or use current
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Verifying MRS in: {directory}\n")

    results = verify_mrs(directory)
    print_results(results)

    sys.exit(results["exit_code"])


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable**

```bash
chmod +x scripts/verify_mrs.py
```

**Step 3: Test the script**

Run in a directory without MRS:
```bash
cd /tmp/test-empty
python ~/.claude/skills/context-resilient-task/scripts/verify_mrs.py .
```

Expected output:
```
MRS VERIFICATION REPORT
❌ MISSING: task_state.md, plan.md, snapshot.md
Exit code: 1
```

**Step 4: Commit**

```bash
git add scripts/verify_mrs.py
git commit -m "feat: add MRS verification script"
```

---

## Task 6: Python Script - Snapshot Generator

**Files:**
- Create: `~/.claude/skills/context-resilient-task/scripts/generate_snapshot.py`

**Step 1: Write snapshot generator script**

```python
#!/usr/bin/env python3
"""
Generate a timestamped snapshot of current task state.

Usage:
    python generate_snapshot.py [--archive]

Options:
    --archive    Save to snapshots/ directory with timestamp, keep snapshot.md updated
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import argparse


SNAPSHOT_TEMPLATE = """# Snapshot: {timestamp}

## Context
{context}

## Recent Progress
{progress}

## Current Focus
{current_focus}

## Blockers
{blockers}

## Files Modified
{files_modified}

## Next Session Should Know
{next_session_notes}
"""


def extract_section(content: str, section_header: str) -> str:
    """Extract content under a specific markdown header."""
    lines = content.split("\n")
    in_section = False
    section_content = []

    for line in lines:
        if line.startswith("#"):
            if section_header in line:
                in_section = True
                continue
            elif in_section:
                # Hit next section, stop
                break
        elif in_section:
            section_content.append(line)

    return "\n".join(section_content).strip() or "(No content)"


def read_task_state(directory: Path) -> dict:
    """Read task_state.md and extract key information."""
    task_state_path = directory / "task_state.md"

    if not task_state_path.exists():
        return {
            "goal": "(task_state.md not found)",
            "current_phase": "(unknown)",
            "next_action": "(unknown)",
        }

    content = task_state_path.read_text(encoding="utf-8")

    return {
        "goal": extract_section(content, "## Goal"),
        "current_phase": extract_section(content, "## Current Phase"),
        "next_action": extract_section(content, "## Next Action"),
        "open_questions": extract_section(content, "## Open Questions"),
    }


def read_progress(directory: Path, last_n_lines: int = 10) -> str:
    """Read recent progress entries."""
    progress_path = directory / "progress.md"

    if not progress_path.exists():
        return "(progress.md not found)"

    content = progress_path.read_text(encoding="utf-8")
    lines = [l for l in content.split("\n") if l.strip()]
    recent = lines[-last_n_lines:] if len(lines) > last_n_lines else lines

    return "\n".join(recent) or "(No recent progress)"


def list_recent_files(directory: Path, hours: int = 24) -> list[str]:
    """List files modified in last N hours."""
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(hours=hours)
    recent_files = []

    # Look for common code directories
    search_dirs = ["src", "tests", "lib", "app", "backend", "frontend"]

    for search_dir in search_dirs:
        dir_path = directory / search_dir
        if not dir_path.exists():
            continue

        for item in dir_path.rglob("*"):
            if item.is_file():
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime > cutoff:
                    recent_files.append(str(item.relative_to(directory)))

    return recent_files[:20]  # Limit to 20 files


def generate_snapshot(directory: Path) -> str:
    """Generate snapshot content from current state."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Read task state
    state = read_task_state(directory)

    # Read recent progress
    recent_progress = read_progress(directory)

    # List recent files
    files = list_recent_files(directory)
    files_str = "\n".join(f"- {f}" for f in files) if files else "(No recent changes detected)"

    # Build context
    context = f"Working on {state['current_phase']} - Goal: {state['goal']}"

    # Build snapshot
    snapshot = SNAPSHOT_TEMPLATE.format(
        timestamp=timestamp,
        context=context,
        progress=recent_progress,
        current_focus=state["next_action"],
        blockers=state.get("open_questions", "(None)"),
        files_modified=files_str,
        next_session_notes="(To be filled by user or AI)",
    )

    return snapshot


def save_snapshot(directory: Path, content: str, archive: bool = False):
    """Save snapshot to file."""
    # Always update snapshot.md
    snapshot_path = directory / "snapshot.md"
    snapshot_path.write_text(content, encoding="utf-8")
    print(f"✅ Updated: {snapshot_path}")

    # Optionally archive
    if archive:
        snapshots_dir = directory / "snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        archive_path = snapshots_dir / f"snapshot_{timestamp}.md"
        archive_path.write_text(content, encoding="utf-8")
        print(f"✅ Archived: {archive_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate task snapshot")
    parser.add_argument("--archive", action="store_true", help="Archive snapshot to snapshots/ directory")
    parser.add_argument("directory", nargs="?", default=".", help="Project directory (default: current)")

    args = parser.parse_args()
    directory = Path(args.directory).resolve()

    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Generating snapshot for: {directory}\n")

    # Generate snapshot
    snapshot = generate_snapshot(directory)

    # Save
    save_snapshot(directory, snapshot, archive=args.archive)

    print("\n✅ Snapshot generated successfully")
    print("\nPreview:")
    print("=" * 60)
    print(snapshot[:500] + "..." if len(snapshot) > 500 else snapshot)
    print("=" * 60)


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable**

```bash
chmod +x scripts/generate_snapshot.py
```

**Step 3: Test the script**

Run in current directory:
```bash
python scripts/generate_snapshot.py .
```

Expected: Creates `snapshot.md` with current state

**Step 4: Commit**

```bash
git add scripts/generate_snapshot.py
git commit -m "feat: add snapshot generator script"
```

---

## Task 7: Asset Templates - task_state.md

**Files:**
- Create: `~/.claude/skills/context-resilient-task/assets/task_state.template.md`

**Step 1: Write task_state template**

```markdown
# Task State

**Last Updated:** {timestamp}
**Updated By:** {user}

## Goal
{one_sentence_goal}

## Current Phase
Phase {N}: {phase_name}

## Status
{pending|in_progress|complete|blocked}

## Last Completed Action
- {action_1}
- {action_2}

## Next Action
{concrete_next_step}

## Open Questions
- {question_1}
- {question_2}

## Artifacts
- plan.md (updated {timestamp})
- findings.md (updated {timestamp})
- progress.md (updated {timestamp})

## Notes
{additional_context}
```

**Step 2: Commit**

```bash
git add assets/task_state.template.md
git commit -m "feat: add task_state template"
```

---

## Task 8: Asset Templates - snapshot.md

**Files:**
- Create: `~/.claude/skills/context-resilient-task/assets/snapshot.template.md`

**Step 1: Write snapshot template**

```markdown
# Snapshot: {timestamp}

## Context
{brief_context_paragraph}

## Recent Progress
- {progress_item_1}
- {progress_item_2}
- {progress_item_3}

## Current Focus
{what_are_we_working_on_now}

## Blockers
- {blocker_1}
- {blocker_2}

## Files Modified
- {file_1}
- {file_2}
- {file_3}

## Next Session Should Know
- {important_fact_1}
- {important_fact_2}
- {important_decision_made}
```

**Step 2: Commit**

```bash
git add assets/snapshot.template.md
git commit -m "feat: add snapshot template"
```

---

## Task 9: Main SKILL.md - Frontmatter and Core Content

**Files:**
- Modify: `~/.claude/skills/context-resilient-task/SKILL.md`

**Step 1: Write SKILL.md frontmatter and main content**

```markdown
---
name: context-resilient-task
version: "1.0.0"
description: Context-resilient task management with stateless recovery from artifacts. Use when starting multi-phase tasks, when task involves multiple sessions, after /clear or session interruption, or when you need to recover task state without relying on conversational memory. Implements three-tier MRS (Minimum Recovery Set), automatic artifact detection, anti-hallucination structured outputs, and degraded failure modes. Replaces planning-with-files with enhanced recovery capabilities.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
hooks:
  PreToolUse:
    - matcher: "Write|Edit|Bash"
      hooks:
        - type: command
          command: "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_mrs.py . 2>/dev/null || echo '[context-resilient-task] MRS verification skipped'"
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "echo '[context-resilient-task] Artifact updated. Consider updating task_state.md if this completes a phase.'"
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
```

**Step 2: Delete example files**

```bash
rm scripts/example.py
rm references/api_reference.md
rm assets/example_asset.txt
```

**Step 3: Commit**

```bash
git add SKILL.md
git rm scripts/example.py references/api_reference.md assets/example_asset.txt
git commit -m "feat: complete SKILL.md with MRS and recovery workflow"
```

---

## Task 10: Package and Test

**Files:**
- Package: `~/.claude/skills/context-resilient-task/` → `context-resilient-task.skill`

**Step 1: Run validator**

```bash
cd ~/.claude/skills
python skill-creator/scripts/validate_skill.py context-resilient-task
```

Expected output:
```
✅ All validation checks passed
```

**Step 2: Package skill**

```bash
python skill-creator/scripts/package_skill.py context-resilient-task
```

Expected output:
```
✅ Packaged: context-resilient-task.skill
```

**Step 3: Test skill in isolated directory**

```bash
mkdir /tmp/test-recovery
cd /tmp/test-recovery

# Test 1: Initialization mode (no MRS)
echo "Should trigger initialization wizard"
# Invoke skill, expect init wizard

# Test 2: Create minimal MRS
cat > task_state.md <<EOF
# Task State
**Last Updated:** 2026-02-10 15:00:00

## Goal
Test recovery functionality

## Current Phase
Phase 1: Setup

## Next Action
Test recovery mode
EOF

cat > plan.md <<EOF
# Task Plan

## Phase 1: Setup
Status: in_progress

## Phase 2: Test
Status: pending
EOF

cat > snapshot.md <<EOF
# Snapshot: 2026-02-10 15:00

## Context
Testing MRS recovery

## Next Session Should Know
This is a test
EOF

# Test 3: Recovery mode
echo "Should trigger recovery mode and output Reconstructed Task State"
# Invoke skill, expect recovery mode

# Test 4: MRS verification
python ~/.claude/skills/context-resilient-task/scripts/verify_mrs.py .
# Expected: exit code 2 (Tier 1 missing)

# Test 5: Snapshot generation
python ~/.claude/skills/context-resilient-task/scripts/generate_snapshot.py .
# Expected: Creates/updates snapshot.md
```

**Step 4: Verify outputs**

Expected recovery mode output:
```markdown
## Reconstructed Task State

### Goal
(from artifact: task_state.md:5)
Test recovery functionality

### What Has Been Done
(from artifact: plan.md)
- Phase 1: Setup (in_progress)

### Current Artifacts
- task_state.md (last updated: 2026-02-10 15:00:00)
- plan.md (present)
- snapshot.md (last updated: 2026-02-10 15:00)

### Unknown / Missing
- findings.md (Tier 1 missing)
- progress.md (Tier 1 missing)

### Next Required Action
(from artifact: task_state.md:14)
Test recovery mode

### Artifact to Be Produced
findings.md - Record test results
```

**Step 5: Commit**

```bash
git add .
git commit -m "test: verify skill packaging and recovery modes"
```

---

## Completion Checklist

- [ ] All reference docs created (MRS, output-template, recovery-workflow, artifact-standards)
- [ ] Scripts implemented (verify_mrs.py, generate_snapshot.py)
- [ ] Templates created (task_state, snapshot)
- [ ] SKILL.md complete with frontmatter and content
- [ ] Skill validates successfully
- [ ] Skill packages successfully
- [ ] Recovery mode tested
- [ ] Initialization mode tested
- [ ] MRS verification tested
- [ ] Snapshot generation tested

---

## Next Steps After Implementation

1. **User acceptance testing** - Try skill on real complex task
2. **Refinement** - Adjust based on real usage feedback
3. **Documentation** - Update based on learnings
4. **Distribution** - Share .skill file with users
5. **Replacement** - Gradually replace planning-with-files usage

## Notes for Executor

- This skill replaces `planning-with-files`, but maintains compatibility with its core artifacts (findings.md, progress.md)
- The MRS system adds `task_state.md` and `snapshot.md` as new requirements
- All scripts use Python 3.11+ standard library (no external dependencies)
- Templates use simple string substitution (can be enhanced with Jinja2 later)
- Validation logic is intentionally strict for Tier 0, permissive for Tier 1/2
