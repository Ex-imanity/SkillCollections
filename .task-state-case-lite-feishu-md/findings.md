# Findings

<!-- Append research notes and discoveries below this line. -->

## 2026-07-25: Native Feishu Markdown evidence

- The supplied wiki URL resolves to a Drive `file` object, title `个人错题本-服务端设计.md`, canonical URL `/file/YC8Ab5NklowCmNxsRVFcyh7gnXg`.
- Read-only `lark-cli markdown +fetch --as user` downloaded 53,320 bytes and found nested H1-H4 ATX headings. It is therefore a native Markdown file, not a Docx document.
- The official Drive download endpoint is `GET /open-apis/drive/v1/files/{file_token}/download`; the verified user scope includes `drive:file:download`.
- Existing `feishu-docx-blocks` has no native file-download or Markdown-section tool. Its current `parse_document_id` is Docx-oriented and must not be extended as an implicit generic resolver.
- Existing generic `pytest Test/` is not a reliable regression gate: six legacy scripts are collected as unsupported bare async tests. The marked `Test/test_get_child_documents.py` automated suite passes when run directly.

## 2026-07-25: Implementation validation

- Added `get_markdown_file_sections` with direct `/file/` and wiki-file resolution, raw Drive download, UTF-8 decode, fence-aware ATX parsing, stable IDs, selected original content, and explicit no-heading full-content opt-in.
- Added `drive:file:download` to the automatic OAuth scopes and release documentation. Existing users must reauthorize after the application permission is enabled.
- Targeted MCP tests: 13 passed (new Markdown tool plus existing child-document regression). case-lite tests: 24 passed on Python 3.13. System Python 3.9 cannot run `setup_mcp.py` tests because it lacks `tomllib`.
- Wheel `feishu_docx_blocks-3.4.0-py3-none-any.whl` passed Twine and exposed the new tool after clean installation. PyPI currently reports 3.3.0.
- Direct MCP online validation stopped before the request because no user access token or app credential config exists in this worktree. This is not a 403 response. The supplied 53,320-byte file was read through the authenticated lark-cli and the MCP parser identified 39 sections.
