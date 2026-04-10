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

Read the contents of these files in priority order:
1. `task_state.md`
2. `plan.md`
3. `snapshot.md`

Parse to extract:
- **Goal:** Main objective
- **Active Todos:** Pending work items (from top of task_state.md)
- **Current Phase:** Where we are in plan
- **Last Action:** What was done last
- **Next Action:** What should happen next

### Step 2: Load Context Artifacts (Tier 1)

Read the following files if present:
- `findings.md`
- `progress.md`
- `architecture.md`
- `decisions.md`

If missing, emit warning:
```
WARNING: Missing Tier 1 artifact: findings.md
This may reduce context quality. Continue anyway? (y/n)
```

### Step 3: Validate Consistency

Check for conflicts:
- Does task_state.md match plan.md current phase?
- Is snapshot.md timestamp recent (<7 days)? (WARNING if stale, not error)
- Does snapshot.md have a single `## Context` section? (Multiple = improper appending)
- Are there open questions in findings.md?

### Step 4: Output Reconstructed State

Use the structured template:

```markdown
## Reconstructed Task State

### Goal
(from artifact: task_state.md)
<goal extracted from task_state.md>

### What Has Been Done
<extract from progress.md and plan.md completed phases>

### Current Artifacts
<list all detected files with timestamps>

### Unknown / Missing
<identify gaps, ambiguities, or outdated info>

### Next Required Action
(from artifact: task_state.md)
<next action from task_state.md>

### Artifact to Be Produced
<expected output artifact>
```

### Step 5: Confirm and Continue

Ask user:
```
Recovered task state from artifacts. Does this look correct?
- Goal: <goal>
- Active Todos: <count> items
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
- `task_state.md` from `assets/task_state.template.md`
- `plan.md` — Generate phases from requirements
- `snapshot.md` from `assets/snapshot.template.md`
- `decisions.md` — Create if multi-session, multi-agent, or >10 phases expected

### Step 4: Copy MRS Rules to AGENTS.md

If the project uses multiple agents (Codex, etc.), copy `references/agents-md-snippet.md` content into the project's `AGENTS.md`.

### Step 5: Enter Recovery Mode

Once Tier 0 created, switch to recovery mode and continue.

## Edge Cases

### Corrupted Artifacts

If artifacts exist but are malformed:
```
ERROR: task_state.md exists but is malformed
Cannot parse required fields: goal, status, active_todos

Options:
1. Regenerate task_state.md (will lose existing data)
2. Manually fix task_state.md and retry
3. Cancel and investigate

Choose option (1-3):
```

### Stale Snapshot

If snapshot.md is >7 days old (this is a WARNING, not an error):
```
WARNING: snapshot.md is 9 days old (last updated 2026-02-01)
Task context may be outdated.

Options:
1. Generate fresh snapshot from current state
2. Continue with stale snapshot
3. Review and update manually

Choose option (1-3):
```

### Snapshot Improperly Appended

If snapshot.md contains multiple `## Context` sections:
```
WARNING: snapshot.md appears to have been appended rather than overwritten.
It contains 5 "## Context" sections instead of 1.

Options:
1. Regenerate snapshot (keeps only latest state)
2. Archive current and generate fresh
3. Continue with current (not recommended)
```

### Conflicting Information

If plan.md says Phase 2 complete but task_state.md says Phase 1:
```
CONFLICT DETECTED:
- plan.md: Phase 2 complete (line 45)
- task_state.md: current_phase = "Phase 1" (line 12)

Cannot safely proceed. Please resolve conflict:
1. Which is correct?
2. Should I update task_state.md to match plan.md?
```

### Task Already Completed

If task_state.md shows status=completed:
```
task_state.md status=completed

This task is marked done. Options:
1. Archive MRS to .task-state/archive/
2. Start new task (reinitialize)
3. Reopen task (set status=active)
```
