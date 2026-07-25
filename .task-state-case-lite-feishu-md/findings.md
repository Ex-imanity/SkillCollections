# Findings

## 2026-07-25

- The supplied Wiki URL resolves to the native Drive file `YC8Ab5NklowCmNxsRVFcyh7gnXg`, titled `个人错题本-服务端设计.md`.
- `drive:file:download` returns `text/markdown; charset=utf-8` for the supplied file.
- Feishu API error `99991668` means the token is invalid for authorization and must not be treated as a valid token.
- Four existing MCP processes from Cursor, Claude Code, and Codex use the original project server and share `~/.config/feishu-docx-blocks/.env`; the file was modified after successful browser OAuth, replacing the valid long token with an invalid short one.
- Following MCP restart, the saved OAuth credentials remained valid in a new process and the live metadata-only directory plus selected-content retrieval contract succeeded.
