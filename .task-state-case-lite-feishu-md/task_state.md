# Task State

**Last Updated:** 2026-07-25 22:05:00
**Updated By:** Codex

## Goal
Enable case-lite to read native Feishu Drive Markdown files and select sections through an updated feishu-docx-blocks MCP, then publish the verified MCP release.

## Status
active

## Active Todos
- [ ] Native Drive Markdown file token and wiki URL resolution (added: 2026-07-25, source: plan Phase 1)
- [ ] read-only download (added: 2026-07-25, source: plan Phase 2)
- [ ] Markdown heading section parsing (added: 2026-07-25, source: plan Phase 3)
- [ ] case-lite routing and artifacts (added: 2026-07-25, source: plan Phase 4)
- [ ] existing wiki/docx regression (added: 2026-07-25, source: plan Phase 5)
- [ ] real provided file validation (added: 2026-07-25, source: plan Phase 6)
- [ ] ClaudeCode read-only review (added: 2026-07-25, source: plan Phase 7)
- [ ] PyPI publication (added: 2026-07-25, source: plan Phase 8)

## Current Phase
Phase 6: Release gate and live MCP credential validation

## Next Action
Obtain a fresh ClaudeCode review budget, then run the read-only review before publishing feishu-docx-blocks 3.4.0.

## Completed Items
- Native Drive Markdown file token and wiki URL resolution
- Read-only download
- Markdown heading section parsing
- case-lite routing and artifacts
- Existing wiki/docx regression

## Open Questions
- A paid ClaudeCode review requires a new per-run budget approval. The previous $2 authorization was consumed by the earlier cross-agent-review task.
- Local MCP OAuth credentials are absent in this isolated worktree, so the real file download cannot yet be exercised through `feishu-docx-blocks` itself. The provided file was fetched read-only through lark-cli and parsed successfully by the MCP parser.

## Artifacts
- plan.md (created at init)
- snapshot.md (created at init)
- docs/plans/2026-07-25-case-lite-feishu-drive-markdown.md (design and execution plan)
- architecture.md (cross-repository ownership and data flow)
- FeishuMCP commit: `78daa91` on `codex/case-lite-feishu-md`
- SkillCollections commit: `121861e` on `codex/case-lite-feishu-md`

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
