<!--
snapshot.md template — machine-readable. The body contains Python
str.format placeholders; field names are documented as <NAME> below.
generate_snapshot.py fills them.

Field reference:
  timestamp         e.g. "2026-05-01 14:30"
  context           One-paragraph summary of what we're working on
  recent_progress   Bullet list, e.g. "- Implemented /register endpoint"
  current_focus     One-line description of the immediate next focus
  blockers          Bullet list of blockers, or "- (None)"
  files_modified    Bullet list of recently modified source files
  next_session_notes Bullet list of facts a future session MUST know

Anything above END_TEMPLATE_DOCS is stripped at render time.
-->
<!--END_TEMPLATE_DOCS-->
<!-- OVERWRITE THIS FILE on each update. Do NOT append new sections. Archive previous version first with: python <skill-root>/scripts/generate_snapshot.py --archive . -->
# Snapshot: {timestamp}

## Context
{context}

## Recent Progress
{recent_progress}

## Current Focus
{current_focus}

## Blockers
{blockers}

## Files Modified
{files_modified}

## Next Session Should Know
{next_session_notes}
