# Progress Log

## 2026-07-25

- Completed browser OAuth for `feishu-docx-blocks` using the application configuration already present in the local Claude MCP setup. Stored credentials and tokens only in `~/.config/feishu-docx-blocks/.env`.
- Verified the supplied Wiki URL resolves to `个人错题本-服务端设计.md`, a native Drive `file`; the MCP downloaded it as UTF-8 Markdown and returned a requested original section (35,595 characters).
- Added regression coverage for cached refresh-token lookup, opaque token expiry fallback, and API error `99991668` as an invalid access token. Targeted MCP tests: 16 passed.
- Tightened the native Markdown directory call to return only headings and line ranges by default. The caller must pass `preview_chars` explicitly to obtain any preview; after selection it receives only the selected original Markdown. Targeted MCP tests: 17 passed.
- Found four existing MCP server processes from Cursor, Claude Code, and Codex sharing the same user-level token file. A later process rewrote the freshly authorized long token with a stale invalid one, so persistent OAuth validation is blocked until those processes are restarted or isolated.
