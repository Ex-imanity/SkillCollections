<!-- OVERWRITE THIS FILE on each update. Do NOT append new sections. Archive previous version first with: python <skill-root>/scripts/generate_snapshot.py --archive . -->
# Snapshot: 2026-07-25 21:05

## Context
Working on Phase 6: Release gate and live MCP credential validation - Goal: Enable case-lite to read native Feishu Drive Markdown files and select sections through an updated feishu-docx-blocks MCP, then publish the verified MCP release.

## Recent Progress
- Created isolated worktrees and feature branches in both repositories.
- Fast-forward merged the completed cross-agent-review work into `SkillCollections/main` before branching.
- Verified the supplied wiki URL is a wiki-wrapped native Drive Markdown file through read-only inspection and fetch.
- Established the MCP-first contract: URL resolution, raw download and parsing stay in `feishu-docx-blocks`; case-lite only orchestrates selection and artifacts.
- Used TDD for file URL resolution, wiki-file resolution, non-file rejection, Drive endpoint bytes, fence-aware headings, no-heading full-text opt-in, registry, and OAuth scope.
- Updated case-lite's routing, corpus contract, README and Feishu tool guide. Docx behavior remains separate and unchanged.
- Validated 13 targeted MCP tests, 24 case-lite tests (Python 3.13), source compilation, wheel packaging, Twine metadata, and clean wheel installation.
- Reached publication gate. Direct MCP OAuth integration needs configured app credentials; cross-agent review needs a new approved provider budget.

## Current Focus
Obtain a fresh ClaudeCode review budget, then run the read-only review before publishing feishu-docx-blocks 3.4.0.

## Blockers
- A paid ClaudeCode review requires a new per-run budget approval. The previous $2 authorization was consumed by the earlier cross-agent-review task.
- Local MCP OAuth credentials are absent in this isolated worktree, so the real file download cannot yet be exercised through `feishu-docx-blocks` itself. The provided file was fetched read-only through lark-cli and parsed successfully by the MCP parser.

## Files Modified
- (No recent changes detected)

## Next Session Should Know
- A paid ClaudeCode review requires a new per-run budget approval. The previous $2 authorization was consumed by the earlier cross-agent-review task.
- Local MCP OAuth credentials are absent in this isolated worktree, so the real file download cannot yet be exercised through `feishu-docx-blocks` itself. The provided file was fetched read-only through lark-cli and parsed successfully by the MCP parser.
- Next action: Obtain a fresh ClaudeCode review budget, then run the read-only review before publishing feishu-docx-blocks 3.4.0.
