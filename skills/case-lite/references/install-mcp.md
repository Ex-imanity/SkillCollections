# case-lite MCP 安装与依赖向导

本文件只在首次使用或依赖缺失时读取。普通 case-lite 用例生成流程不需要加载本文件。

## 原则

- 面向 Claude Code 和 Codex 提供自动配置；其他 Agent 只给出手动提示。
- 默认配置全局 MCP，但写入前必须征求用户同意。
- 配置文件写入必须先备份、原子写入（临时文件 + 替换），再 merge；不要覆盖用户已有 MCP。
- 已有 `feishu-docx-blocks` 默认保留，不静默覆盖；不是 `feishu-docx-blocks@latest` 时询问用户是否升级，确认后才用 `--replace-feishu` 替换。
- Claude Code 配置路径不确定时（新旧路径同时存在）不要盲写，先让用户确认生效路径。
- 不要在 skill、README、测试、日志中写入默认 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`。
- 默认凭证请用户到内部文档自行获取：
  `https://gaotuedu.feishu.cn/wiki/CNBZwz8rwiew8dkXHt1cRIAAn8g#share-DrNhdQPiToYWMXxyC6nciHlknJh`
- 飞书授权维持 `feishu-docx-blocks` 自身逻辑；首次或过期时由 MCP 拉起浏览器让用户授权。

## 推荐 Agent 流程

1. 先执行轻量检查：
   ```bash
   python case-lite/scripts/setup_mcp.py --agent claude-code
   python case-lite/scripts/setup_mcp.py --agent codex
   ```
2. 展示诊断报告，说明缺失项和即将写入的全局配置路径。
3. 向用户确认是否自动配置全局 MCP。
4. 用户确认后，要求用户通过环境变量或交互输入提供凭证：
   ```bash
   export FEISHU_APP_ID="..."
   export FEISHU_APP_SECRET="..."
   python case-lite/scripts/setup_mcp.py --agent codex --fix
   ```
5. 写入完成后提醒用户重启 Agent / MCP 会话。

## Claude Code

全局配置路径存在新旧差异：

- 新版 cc-switch 默认：`~/.claude/.claude.json`
- 旧版或覆盖配置：`~/.claude.json`

脚本的路径判断规则：只有单个路径存在时直接采用；两个路径都不存在时默认 `~/.claude/.claude.json`；**两个路径同时存在时视为“不确定”**——因为无法仅凭文件存在判断旧版 cc-switch 是否覆盖了生效路径。此时脚本会在报告中列出候选路径并要求确认，`--fix --yes` 会直接拒绝，交互模式让用户选择，或用 `--config <路径>` 显式指定。详情参考 cc-switch PR：https://github.com/farion1231/cc-switch/pull/3431

如果用户明确要求项目级配置，则不要使用本脚本的默认全局写入，改为让用户手动编辑项目根目录 `.mcp.json`。

也可以用 Claude Code 官方 CLI 代替手工写文件（对大文件更安全，避免并发覆盖 `~/.claude.json` 中的其它状态）：

```bash
claude mcp add-json feishu-docx-blocks -s user \
  '{"command":"uvx","args":["feishu-docx-blocks@latest"],"type":"stdio","env":{"FEISHU_APP_ID":"'"$FEISHU_APP_ID"'","FEISHU_APP_SECRET":"'"$FEISHU_APP_SECRET"'"}}'
```

无论手工还是脚本写入，Claude Code 写入前都应退出 Claude Code，避免运行中并发写回覆盖修改。

目标配置片段：

```json
{
  "mcpServers": {
    "feishu-docx-blocks": {
      "command": "uvx",
      "args": ["feishu-docx-blocks@latest"],
      "type": "stdio",
      "env": {
        "FEISHU_APP_ID": "<用户提供>",
        "FEISHU_APP_SECRET": "<用户提供>"
      }
    },
    "Banshan": {
      "type": "streamable-http",
      "url": "https://tech.baijia.com/mcp-server/banshan/mcp"
    }
  }
}
```

## Codex

默认全局配置路径：`~/.codex/config.toml`。

目标配置片段：

```toml
[mcp_servers.feishu-docx-blocks]
command = "uvx"
args = ["feishu-docx-blocks@latest"]

[mcp_servers.feishu-docx-blocks.env]
FEISHU_APP_ID = "<用户提供>"
FEISHU_APP_SECRET = "<用户提供>"

[mcp_servers.banshan]
url = "https://tech.baijia.com/mcp-server/banshan/mcp"
```

也可以手动使用 Codex CLI：

```bash
codex mcp add feishu-docx-blocks \
  --env FEISHU_APP_ID="$FEISHU_APP_ID" \
  --env FEISHU_APP_SECRET="$FEISHU_APP_SECRET" \
  -- uvx feishu-docx-blocks@latest
```

## 诊断项

`setup_mcp.py` 会检查：

- `feishu-docx-blocks` 是否已配置
- 是否使用 `feishu-docx-blocks@latest`
- Banshan MCP 是否配置为固定 URL
- 是否提供 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`

它不会检查飞书 OAuth 授权状态；授权由 `feishu-docx-blocks` 在首次调用或 token 过期时处理。

**连通性限制**：诊断的 `OK` 只表示“已配置”，不代表 MCP 已连通。要确认 Banshan / feishu 真正可用，写入并重启会话后由 Agent 实际调用一次对应工具（如 `testCaseDetail` / `parse_document_id`）来验证。

## Review Checklist

- 没有明文默认 `FEISHU_APP_SECRET`（仓库为公开仓库，凭证只在内部文档）
- 写全局配置前有用户确认
- 写文件前创建备份，并原子写入；含 secret 的文件权限收敛为 0o600
- JSON/TOML merge 保留已有配置；已有 `feishu-docx-blocks` 默认不覆盖（需 `--replace-feishu`）
- Claude Code 路径不确定时不静默写入，要求用户确认生效路径
- 诊断凭证优先读环境变量，其次读现有配置，避免对已配置用户误报
- 普通 case-lite 流程只做轻量检查，不强制加载完整安装流程
