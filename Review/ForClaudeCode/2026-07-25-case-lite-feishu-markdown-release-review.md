# Read-Only Review Request: Native Feishu Markdown Support

## Role and Boundary

You are the independent reviewer. Review only; do not edit files, run write commands, publish packages, alter authentication, or modify task-state artifacts. Return evidence-cited findings and a verdict in Chinese.

Codex remains the implementation and closure owner.

## Objective

Review the release candidate that lets `case-lite` consume native Feishu Drive `.md` files through the `feishu-docx-blocks` MCP while retaining user-controlled, precise-input chapter selection.

## Repositories and Revisions

1. MCP implementation: `/Users/gaotu/.config/superpowers/worktrees/FeishuMCP/case-lite-feishu-md`
   - Base: `master`
   - Review head: `d18a5aa`
   - Full feature baseline commit: `78daa91`
2. Skill and MRS: `/Users/gaotu/.config/superpowers/worktrees/SkillCollections/case-lite-feishu-md`
   - Base: `main`
   - Review head: `04a1649`
   - Feature commits: `2fcaccc`, `04bfd0f`, `04a1649`

Review the combined changes against the named base branches, not unrelated working-tree state.

## Required Behavior

- `/file/TOKEN` and Wiki URLs whose final node is `obj_type=file` resolve to a Drive file token.
- The MCP downloads Markdown read-only with `drive:file:download`, decodes UTF-8, and detects ATX headings outside fenced code blocks.
- Directory mode protects precise input: by default it returns only section ID/title/level/path/line range, with neither source body nor preview. A preview is opt-in only.
- `case-lite` must show the chapter list and wait for explicit user selection. Only then may the selected original Markdown be returned and written to the corpus.
- Existing Docx/Wiki behavior must remain isolated from native Markdown handling.
- OAuth handling must reject API `99991668` as invalid and recover token material from the user-level token manager when `dotenv` was not preloaded.

## Evidence to Inspect

- MCP code: `src/tools/document/get_markdown_file_sections.py`, `src/feishu_client.py`, `src/mcp_server.py`, `src/token_manager.py`, `src/auto_auth.py`, `src/tools/__init__.py`, `Test/test_markdown_file_sections.py`.
- Skill contract: `case-lite/SKILL.md`, `case-lite/references/feishu-tools-guide.md`, `case-lite/tests/`.
- Execution plan and live-validation record: `docs/plans/2026-07-25-case-lite-feishu-drive-markdown.md`, `.task-state-case-lite-feishu-md/`.

## Verification Already Performed by Primary

- MCP regression: `uv run pytest Test/test_markdown_file_sections.py Test/test_get_child_documents.py -q` -> 17 passed.
- case-lite contract tests: `python3.13 -m unittest discover -s case-lite/tests` -> 24 passed.
- Supplied live Wiki URL resolved to native file `个人错题本-服务端设计.md`; after MCP restart, directory mode returned 38 metadata-only sections and selected section `1` returned original Markdown (35,595 characters).
- `uv build` produced `feishu-docx-blocks` 3.4.0 sdist/wheel; `twine check` passed; a clean Python 3.13 venv installed the wheel and registered `get_markdown_file_sections`.

## Known Limitation

The Drive API returns a complete file, so the MCP must hold the raw Markdown in its own process to parse headings. The claimed precise-input boundary is model-facing: directory output must not expose non-selected body content.

## Questions

1. Does the implementation enforce the metadata-only first step and selected-content-only second step without an accidental body/preview leak?
2. Are URL routing, heading ranges, parent-child selection de-duplication, and Docx fallback correct enough for release?
3. Are the OAuth/token changes correct, including their behavior when environment variables and user config differ?
4. Are documentation and tests consistent with the implementation? Identify missing release-blocking tests or compatibility risks.
5. Is the 3.4.0 candidate safe to publish, or should it be `REQUEST CHANGES`? Cite paths and line numbers for every finding.

## Expected Result

Return `APPROVE`, `APPROVE WITH NITS`, `REQUEST CHANGES`, or `BLOCKED`. Order findings by severity P0-P3, state test limitations, and recommend the next action. Do not call Codex or another reviewer.
