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
