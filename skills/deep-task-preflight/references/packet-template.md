# Preflight Packet Template

Use the full form for Full mode. Medium mode may merge “Why/for whom” into the outcome and
fold constraints into scope, but it must retain criterion IDs, unknowns, the gate, and the
validation matrix.

```markdown
## Preflight Packet
### Intended outcome
<one observable sentence describing what the user will be able to do or decide>

### Why, audience, and scope
- User/problem and audience:
- In scope:
- Out of scope:
- Source priority:

### Acceptance criteria
| ID | Observable result | Check/evidence |
|---|---|---|
| AC-1 | ... | ... |

### Constraints and unknowns
- Constraint:
- Blocking unknown:
- Non-blocking assumption:

### Change surface and references
- Files, systems, artifacts, or commands:
- Input/state/output boundaries:
- Reference implementation or baseline compared:
- Compatibility, rollback, or ownership boundary:

### Risks and alternatives
- Risk:
- Alternative and reason not chosen:

### Validation matrix
| ID | Validation action | Expected evidence | Status |
|---|---|---|---|
| AC-1 | ... | ... | pending |

### Gate
`READY` / `NEEDS INPUT` / `BLOCKED`
<one-sentence reason>
```

The outcome must describe the user's result, not the agent's activity. “Add three slides”
describes work; “help the audience understand the problem, motivation, evidence, and result
within three slides” describes an outcome.
