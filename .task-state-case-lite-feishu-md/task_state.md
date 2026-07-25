# Task State

**Last Updated:** 2026-07-25 22:35:00
**Updated By:** Codex

## Goal
Enable case-lite to read native Feishu Drive Markdown files and select sections through an updated feishu-docx-blocks MCP, then publish the verified MCP release.

## Status
active

## Active Todos
- [ ] ClaudeCode read-only review (added: 2026-07-25, source: plan Phase 7)
- [ ] PyPI publication (added: 2026-07-25, source: plan Phase 8)

## Current Phase
Phase 7: ClaudeCode read-only review gate

## Next Action
Obtain a fresh ClaudeCode review budget, then run the read-only review before publishing `feishu-docx-blocks` 3.4.0.

## Completed Items
- Native Drive Markdown file token and wiki URL resolution
- Read-only download
- Markdown heading section parsing
- case-lite routing and artifacts
- Existing wiki/docx regression
- Real provided file validation through the MCP: browser OAuth, Wiki resolution, Drive download, UTF-8 decoding, and selected original Markdown retrieval
- Token persistence hardening: cached refresh-token lookup, opaque-token default expiry, and `99991668` invalid-token handling
- Precision hardening: native Markdown directory mode exposes no preview or content by default; only an explicit user request may request a preview, and selected sections alone return original Markdown

## Open Questions
- A paid ClaudeCode review requires a new per-run budget approval. The previous $2 authorization was consumed by the earlier cross-agent-review task.
- The verified browser OAuth credentials and tokens are stored only in the user-level MCP configuration, never in either Git worktree.
- Four existing old `run_server.py` MCP processes share the same user-level token file and can overwrite a newly authorized token. Do not publish or claim persistent OAuth validation until those processes are restarted against the released version or otherwise isolated.

## Artifacts
- plan.md (created at init)
- snapshot.md (created at init)
- docs/plans/2026-07-25-case-lite-feishu-drive-markdown.md (design and execution plan)
- architecture.md (cross-repository ownership and data flow)
- FeishuMCP commit: `78daa91` on `codex/case-lite-feishu-md`
- SkillCollections commit: `2fcaccc` on `codex/case-lite-feishu-md`
- `progress.md` (live OAuth and real-file validation record)
- `decisions.md` (MCP credential ownership and validation conclusions)

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
