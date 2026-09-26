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
- "## Plan Registry" MUST stay at the bottom. Legacy "## Plan Registry (docs/plans)"
  headings remain valid.
- Resource pointers/links are NEVER registered here; they live in utils.md.
- Plan Registry registers ONLY repo-relative plan/spec files under the plan roots:
  docs/plans/ (superpowers <= 4.x), docs/superpowers/plans/ and
  docs/superpowers/specs/ (superpowers >= 5.0), plus any roots the registry
  declares. NEVER register CLAUDE.md, AGENTS.md, .task-state/* (MRS files),
  docs/runbooks/*, or .superpowers/sdd/* execution ledgers.
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

## Plan Registry

<!--
Strict boundary: register ONLY repo-relative files under the plan roots
docs/plans/, docs/superpowers/plans/, docs/superpowers/specs/.
If the project relocates plans or specs, declare the extra roots on one line
below this comment, e.g. "Plan roots: docs/archive/plans/".
Do NOT register CLAUDE.md, AGENTS.md, .task-state/*, docs/runbooks/*,
or .superpowers/sdd/* execution ledgers.
Status values: pending | in_progress | completed | abandoned
-->

| File | Source Skill | Date | Status |
|------|--------------|------|--------|

## Reference Index

<!--
Optional. For non-plan LOCAL reference files under version control (runbooks,
committed design docs). NOT for CLAUDE.md / AGENTS.md (auto-loaded) or MRS files.
Links and pointers (飞书文档, external pages, endpoints, local processes, ...) belong
in the utils.md Resource Registry — cite them here by ID, not by URL.
Delete this section if unused.
-->

| File | Purpose |
|------|---------|
