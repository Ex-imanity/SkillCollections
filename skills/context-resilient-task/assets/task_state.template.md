<!--
task_state.md template — machine-readable. The body contains Python
str.format placeholders. Field names are documented as <NAME> below.
init_mrs.py fills them.

Field reference:
  timestamp        Last update timestamp, e.g. "2026-05-01 14:30:00"
  agent            Who updated, e.g. "user (init)" or "Claude (session abc123)"
  goal             One-sentence task goal
  status           Must be one of: active, paused, blocked, completed
  active_todos     Bullet list, one line per todo. Example line:
                     - [ ] Implement auth module (added: 2026-05-01, source: plan Phase 2)
                   Use "_(none)_" if empty.
  current_phase    e.g. "Phase 2: Implementation" — must match plan.md
  next_action      Single concrete next step (one line)
  completed_items  Bullet list, one line per completed item. Example line:
                     - [x] Designed database schema (completed: 2026-05-01)
                   Use "_(none)_" if empty.
  open_questions   Bullet list. Use "_(none)_" if empty.
  artifacts        Bullet list of MRS files with timestamps.

Structural rules:
- "## Active Todos" MUST stay near the top (immediately after Status). Recovery reads it first.
- Each todo is a single line. Detailed context references external files, not inline sub-lists.
- Update fields IN-PLACE. Never append dated sections to this file.
- Compress when total exceeds 300 lines (move detail to progress.md).

Anything above END_TEMPLATE_DOCS is stripped at render time.
-->
<!--END_TEMPLATE_DOCS-->
# Task State

**Last Updated:** {timestamp}
**Updated By:** {agent}

## Goal
{goal}

## Status
{status}

## Active Todos
{active_todos}

## Current Phase
{current_phase}

## Next Action
{next_action}

## Completed Items
{completed_items}

## Open Questions
{open_questions}

## Artifacts
{artifacts}

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
