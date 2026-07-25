# Progress

<!-- Append chronological execution log entries below this line. -->

## 2026-07-25 21:10 CST - Design evidence recorded

- Created isolated worktrees and feature branches in both repositories.
- Fast-forward merged the completed cross-agent-review work into `SkillCollections/main` before branching.
- Verified the supplied wiki URL is a wiki-wrapped native Drive Markdown file through read-only inspection and fetch.
- Established the MCP-first contract: URL resolution, raw download and parsing stay in `feishu-docx-blocks`; case-lite only orchestrates selection and artifacts.

## 2026-07-25 22:05 CST - Feature implemented and release candidate built

- Used TDD for file URL resolution, wiki-file resolution, non-file rejection, Drive endpoint bytes, fence-aware headings, no-heading full-text opt-in, registry, and OAuth scope.
- Updated case-lite's routing, corpus contract, README and Feishu tool guide. Docx behavior remains separate and unchanged.
- Validated 13 targeted MCP tests, 24 case-lite tests (Python 3.13), source compilation, wheel packaging, Twine metadata, and clean wheel installation.
- Reached publication gate. Direct MCP OAuth integration needs configured app credentials; cross-agent review needs a new approved provider budget.
