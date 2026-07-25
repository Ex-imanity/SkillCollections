# Task State

**Last Updated:** 2026-07-25 23:05:00
**Updated By:** Codex

## Goal
Enable case-lite to read native Feishu Drive Markdown files and select sections through an updated feishu-docx-blocks MCP, then publish the verified MCP release.

## Status
active

## Active Todos
- [ ] PyPI publication (added: 2026-07-25, source: plan Phase 8)

## Current Phase
Phase 8: PyPI publication

## Next Action
Publish the verified `feishu-docx-blocks` 3.4.0 release to PyPI, then install it and run the final case-lite selection workflow.

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

## Open Questions
- The verified browser OAuth credentials and tokens are stored only in the user-level MCP configuration, never in either Git worktree.
- Existing MCP processes were restarted and a fresh user-level token was verified in a new process. Release installation must still replace legacy server instances with the published version.

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
