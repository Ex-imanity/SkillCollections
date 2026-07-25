# Decisions

## 2026-07-25: MCP authentication ownership

Application credentials and OAuth tokens belong in the user-level `~/.config/feishu-docx-blocks/.env`, not in either source repository. The MCP's `env` configuration remains an allowed higher-priority source for app credentials.

## 2026-07-25: Live feature acceptance evidence

The release gate requires a real Drive Markdown file to pass Wiki resolution, raw download, UTF-8 decoding, heading selection, and original-content return through the MCP. The supplied `GRvdwOlXRiQXxFkdcA1cIY3Xnbh` file met that gate after browser OAuth.

## 2026-07-25: Precise-input boundary for native Markdown

The Drive API must download a Markdown file into MCP process memory to parse headings because it has no range endpoint. This does not authorize the model to receive the body: directory mode returns only IDs, titles, levels, paths, and line ranges. Original Markdown is returned only for the user-selected IDs.

## 2026-07-25: Shared token-file process isolation

Multiple old MCP processes can overwrite the single user-level token file. Release verification must run after those processes use the released MCP version or are stopped/restarted; never rely on a token that another server can silently replace.
