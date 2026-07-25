# Decisions

<!--
Append-only log of stable conclusions and design decisions.

Rules:
- New entries go at the BOTTOM of the file.
- Never edit or remove past entries (except to fix typos).
- This file is the destination for "Latest Stable Conclusions" content.
  NEVER append such content to task_state.md.
- Required when: multi-session, multi-agent, or >10 phases. Optional otherwise.

Entry shape (copy below the "## Entries" marker):

  ## YYYY-MM-DD: <short title>
  - **Decision:** <what was decided>
  - **Reason:** <why>
  - **Source:** <session id, artifact reference, or user confirmation>
-->

## Entries

<!-- Append new entries below this line. -->
## 2026-07-25: Native Markdown integration boundary

- Decision: expose native Drive Markdown through a new `get_markdown_file_sections` MCP tool rather than extending `parse_document_id` or parsing files in case-lite.
- Rationale: the MCP owns Feishu authentication, Wiki resolution, Drive download and deterministic parsing. case-lite stays responsible for human selection and artifact orchestration.
- Compatibility: non-file Wiki nodes explicitly fall back to the existing Docx route; no Docx API or media behavior is overloaded for Markdown.

## 2026-07-25: Section parser scope

- Decision: support UTF-8 ATX headings outside backtick/tilde fenced code blocks, with one-based inclusive line ranges.
- Rationale: this matches the provided real Drive Markdown and avoids false sections from code samples while keeping selected content byte-for-byte equivalent apart from a trailing newline.
