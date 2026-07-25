# Plan

**Last Updated:** 2026-07-25 22:35:00
**Goal:** Enable case-lite to read native Feishu Drive Markdown files and select sections through an updated feishu-docx-blocks MCP, then publish the verified MCP release.

## Phase 1: Design and implementation contract
**Status:** completed
**Description:** Define a native Drive Markdown path without changing existing Docx behavior. The MCP owns URL resolution, file download, parsing and selected-content retrieval; case-lite owns HITL routing and artifacts.
**Deliverables:**
- Architecture and code-level execution plan
- Verified real input classification: the supplied wiki node resolves to a Drive file

## Phase 2: read-only download
**Status:** completed
**Description:** Add a Feishu client method for the official Drive file download endpoint and test the raw-byte response handling.
**Deliverables:**
- TODO

## Phase 3: Markdown heading section parsing
**Status:** completed
**Description:** Add a fenced-code-aware ATX heading parser with stable section IDs, paths, line ranges, previews, and selected original content.
**Deliverables:**
- TODO

## Phase 4: case-lite routing and artifacts
**Status:** completed
**Description:** Route native file URLs through the new MCP tool while preserving the existing wiki/docx child-discovery and block/media workflow.
**Deliverables:**
- TODO

## Phase 5: existing wiki/docx regression
**Status:** completed
**Description:** Run targeted automated MCP and case-lite contract tests, including the existing child-document suite.
**Deliverables:**
- TODO

## Phase 6: real provided file validation
**Status:** completed
**Description:** Browser OAuth was completed with `drive:file:download`. After MCP restart, a fresh MCP process resolved the supplied Wiki URL to its native Drive file, returned 38 metadata-only sections, and returned original Markdown only for the selected section.
**Deliverables:**
- TODO

## Phase 7: ClaudeCode read-only review
**Status:** completed
**Description:** ClaudeCode completed a bounded $2 read-only gate with verdict `APPROVE WITH NITS` and reported cost $1.56871475. All P3 contract/documentation and test findings were applied.
**Deliverables:**
- TODO

## Phase 8: PyPI publication
**Status:** completed
**Description:** `feishu-docx-blocks` 3.4.0 was published to PyPI. A clean public-PyPI installation completed the supplied real file's metadata-only directory and selected original Markdown retrieval path.
**Deliverables:**
- TODO

## Plan Registry (docs/plans)

<!--
Strict boundary: register ONLY docs/plans/*.md files.
Do NOT register CLAUDE.md, AGENTS.md, .task-state/*, or docs/runbooks/*.
Status values: pending | in_progress | completed | abandoned
-->

| File | Source Skill | Date | Status |
|------|--------------|------|--------|
| docs/plans/2026-07-25-case-lite-feishu-drive-markdown.md | writing-plans | 2026-07-25 | completed |

## Reference Index

<!--
Optional. For non-plan reference files (runbooks, external design docs).
NOT for CLAUDE.md / AGENTS.md (auto-loaded) or MRS files. Delete this section if unused.
-->

| File | Purpose |
|------|---------|
