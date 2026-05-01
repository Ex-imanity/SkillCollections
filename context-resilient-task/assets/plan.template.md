<!--
plan.md template — machine-readable. The body contains Python str.format
placeholders; field names are documented as <NAME> below.
init_mrs.py fills them.

Field reference:
  timestamp  Last update timestamp
  goal       One-sentence task goal (mirrors task_state.md)
  phases     Pre-rendered phase blocks. Each block must follow this shape:

               ## Phase N: <phase name>
               **Status:** pending | in_progress | complete | blocked
               **Description:** <what this phase accomplishes>
               **Deliverables:**
               - <deliverable 1>
               - <deliverable 2>

Structural rules:
- "## Plan Registry (docs/plans)" MUST stay at the bottom.
- Plan Registry registers ONLY files under docs/plans/*.md. NEVER register
  CLAUDE.md, AGENTS.md, .task-state/* (MRS files), or docs/runbooks/*.
- Reference Index is optional; delete the section if unused.
- A phase MUST have one of: pending, in_progress, complete, blocked.
- Only one phase should be in_progress at a time.

Anything above END_TEMPLATE_DOCS is stripped at render time.
-->
<!--END_TEMPLATE_DOCS-->
# Plan

**Last Updated:** {timestamp}
**Goal:** {goal}

{phases}

## Plan Registry (docs/plans)

<!--
Strict boundary: register ONLY docs/plans/*.md files.
Do NOT register CLAUDE.md, AGENTS.md, .task-state/*, or docs/runbooks/*.
Status values: pending | in_progress | completed | abandoned
-->

| File | Source Skill | Date | Status |
|------|--------------|------|--------|

## Reference Index

<!--
Optional. For non-plan reference files (runbooks, external design docs).
NOT for CLAUDE.md / AGENTS.md (auto-loaded) or MRS files. Delete this section if unused.
-->

| File | Purpose |
|------|---------|
