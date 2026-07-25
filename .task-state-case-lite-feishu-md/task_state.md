# Task State

**Last Updated:** 2026-07-25 23:30:00
**Updated By:** Codex

## Goal
Enable case-lite to read native Feishu Drive Markdown files and select sections through an updated feishu-docx-blocks MCP, then publish the verified MCP release.

## Status
completed

## Active Todos
None.

## Current Phase
Completed

## Next Action
Task complete. Restart running MCP clients to load the merged local source, then use `case-lite` with a native Feishu Markdown URL.

## Completed Items
- Native Drive Markdown file token and wiki URL resolution
- Read-only download
- Markdown heading section parsing
- case-lite routing and artifacts
- Existing wiki/docx regression
- Real provided file validation through the MCP: browser OAuth, Wiki resolution, Drive download, UTF-8 decoding, and selected original Markdown retrieval
- Token persistence hardening: cached refresh-token lookup, opaque-token default expiry, and `99991668` invalid-token handling
- Precision hardening: native Markdown directory mode exposes no preview or content by default; only an explicit user request may request a preview, and selected sections alone return original Markdown
- Release artifact validation: `feishu-docx-blocks` 3.4.0 sdist and wheel passed Twine metadata checks and a clean virtual-environment installation verified the new MCP tool registration
- ClaudeCode read-only review: `APPROVE WITH NITS`, actual cost `$1.56871475`; all P3 documentation/test findings were applied and the final MCP regression suite has 19 passing tests
- PyPI publication: `feishu-docx-blocks` 3.4.0 published successfully after credential renewal
- Public release validation: a clean PyPI installation of 3.4.0 completed the real metadata-only directory and selected-original-Markdown flow against the supplied Feishu file
- Installed case-lite synchronization: the source skill and `~/.cc-switch/skills/case-lite` are identical apart from cache directories; installed contract suite has 24 passing tests

## Open Questions
None.

## Artifacts
- plan.md (created at init)
- snapshot.md (created at init)
- docs/plans/2026-07-25-case-lite-feishu-drive-markdown.md (design and execution plan)
- architecture.md (cross-repository ownership and data flow)
- FeishuMCP commit: `78daa91` on `codex/case-lite-feishu-md`
- SkillCollections commit: `2fcaccc` on `codex/case-lite-feishu-md`
- `progress.md` (live OAuth and real-file validation record)
- `decisions.md` (MCP credential ownership and validation conclusions)
- `Review/ByClaudeCode/2026-07-25-case-lite-feishu-markdown-release-review.md` (approved read-only review)
- `.task-state-case-lite-feishu-md/cross-agent-review-cost.jsonl` (provider cost provenance)

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
