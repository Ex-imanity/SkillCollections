# GAPM MCP 恢复

这个 Skill 用于排查和恢复 Codex 中的 `gapm_agent_tools`，尤其适合以下情况：

- 当前对话没有注入 `gapm_log_query_v2` 等 GAPM Tool；
- `codex mcp get` 显示已启用，但 App Server 的 `serverInfo` 为空或 Tool 列表为空；
- Tool 调用返回 `invalid_client`、`authentication_required` 等 OAuth 错误；
- 日志排查似乎只能通过重启 Codex 或新开对话继续。

它把配置、MCP 服务启动、Tool 枚举和实际调用分层诊断。只要 App Server 健康，即使当前
对话没有原生 GAPM Tool，也可以通过临时只读 thread 直接调用 MCP，重启 Codex 只作为最后
手段。

## 依赖与兼容性

- Python 3.9+，仅使用标准库；
- 支持 `mcp` 和实验性 `app-server` 子命令的 Codex CLI；
- 能访问 `https://tech.baijia.com/mcp-server/gapm_agent_tools/mcp`；
- OAuth 过期时需要用户在浏览器完成授权；
- 当前已在 macOS 验证。脚本使用 POSIX 可用的 pipe/select 机制，Windows 尚未验证。

Skill 不包含账号、Cookie、token、uid、sid、traceId 或 questionId。

## 安装

复制整个目录到 Codex 的个人 Skill 目录：

```bash
cp -R gapm-mcp-recovery ~/.codex/skills/gapm-mcp-recovery
```

若尚未配置 GAPM MCP，可执行：

```bash
codex mcp add gapm_agent_tools \
  --url https://tech.baijia.com/mcp-server/gapm_agent_tools/mcp
```

后续 Codex 任务遇到 GAPM Tool 缺失、OAuth 错误或疑似需要重启时，会根据 `SKILL.md` 的
触发条件使用本 Skill。

## 快速检查

在当前项目目录执行：

```bash
python3 ~/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py status
```

常见状态：

| 状态 | 含义 | 建议操作 |
| --- | --- | --- |
| `HEALTHY` | MCP 已启动且三个 GAPM Tool 枚举完整 | 优先使用原生 Tool；未注入时直接使用 bridge `call` |
| `AUTH_REQUIRED` | OAuth 无效或服务未完成启动 | 执行 `login` 并在浏览器授权 |
| `CONFIG_MISSING` | Codex 没有该 MCP 配置 | 执行输出中的 `recommended_command` |
| `CONFIG_INVALID` | 配置存在但 URL 或启用状态不正确 | 检查输出中的 remove/add 命令 |
| `TOOLS_MISSING` | 服务响应但 Tool 枚举不完整 | 重试一次，仍失败则联系 MCP 服务维护方 |
| `STARTUP_FAILED` | App Server 无法启动或读取 MCP 状态 | 保留脱敏错误并检查 Codex CLI/MCP 服务 |

`codex mcp list/get` 中出现 `enabled` 或 `OAuth` 只代表配置及认证类型，不代表登录和服务
一定健康。

## 恢复 OAuth

```bash
python3 ~/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py login
```

命令会调用 `codex mcp login gapm_agent_tools`。完成浏览器授权后，脚本自动重新检查真实
App Server 状态。不要把 `logout` 作为固定第一步；只有直接 `login` 反复失败时才清除旧
凭证后重新登录。

## 无害连通性检查

```bash
python3 ~/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py smoke
```

`smoke` 使用唯一随机且不存在的关键字调用 `gapm_log_query_v2`，不包含业务关联标识，也不
打印或持久化原始结果。`SMOKE_OK` 表示 MCP Tool 与日志后端可连通；空结果不代表某条业务
链路没有调用 Agent、Tool 或下游服务。

## 不重启直接查询

将 Tool 参数写入当前项目 Git 忽略的 `.local` 文件：

```json
{
  "env": "prod",
  "serviceName": "ai-search-platform",
  "keyword": "<本地关联键>",
  "logType": "app",
  "fromTimestampInSeconds": 0,
  "toTimestampInSeconds": 0,
  "limit": 20
}
```

通过 App Server bridge 调用：

```bash
python3 ~/.codex/skills/gapm-mcp-recovery/scripts/gapm_mcp.py call \
  --tool gapm_log_query_v2 \
  --arguments-file .local/gapm/query.json \
  --output .local/gapm/result.json
```

bridge 会创建临时、只读、`ephemeral` 的 Codex thread，再调用已配置的 MCP。参数文件和
输出文件必须位于当前项目 `.local/` 下；输出文件权限固定为 `0600`。脚本只允许调用：

- `gapm_log_query_v2`
- `gapm_trace_query_v2`
- `gapm_trace_and_log_query_v2`

## 重启边界

仅当任务明确依赖“当前对话的原生 Tool 注入”，且 bridge 无法满足时，才考虑重启：

1. 先把当前任务状态写入 MRS 或其他持久化记录；
2. 完全退出并重新打开 Codex；
3. 优先恢复原任务；
4. 只有原任务的 Tool 快照仍旧失效时才新建任务。

一般日志查询不需要走到这一步。

## 安全约束

- 原始日志、Tool 参数、traceId、questionId、uid 和 sid 只能保存在 Git 忽略的 `.local/`；
- 不把 OAuth token、授权回调 URL、Cookie 或原始日志写入 README、报告或聊天回复；
- 本 Skill 不调用 `mainSearch`，不修改生产数据；
- 查询无结果只能记为 `TELEMETRY_MISSING` 或 `INSUFFICIENT_DATA`，不能断言未发生调用。

## 目录结构

```text
gapm-mcp-recovery/
├── README.md
├── SKILL.md
├── evals/
│   └── evals.json
└── scripts/
    └── gapm_mcp.py
```

## 验证

```bash
python3 scripts/gapm_mcp.py --help
python3 scripts/gapm_mcp.py status
python3 scripts/gapm_mcp.py smoke
```

其中 `status` 和 `smoke` 会访问本机 Codex 配置及内部 GAPM MCP；离线环境只运行
`--help` 和 Skill frontmatter 校验。
