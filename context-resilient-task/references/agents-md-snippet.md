# AGENTS.md MRS Snippet

The section below — starting at the line `## MRS 操作规范 (.task-state/)` and ending at this file's end — is meant to be copied **verbatim** into your project's root `AGENTS.md`. It contains no code-fence wrappers, so you can append it directly without stripping anything.

This snippet ensures all agents (Claude Code, Codex, etc.) follow the same MRS update rules even when they don't have access to this skill's references.

---

## MRS 操作规范 (.task-state/)

本项目使用 `.task-state/` 目录管理跨会话任务状态。所有 agent 必须遵守以下规则。

### 文件职责与更新方式
- `task_state.md` — 当前状态唯一真相源。**原地修改**已有字段，不追加新的日期段落。限 300 行。
- `progress.md` — 执行日志。**仅追加**，不覆写已有内容。
- `snapshot.md` — 最新检查点快照。每次**覆写整个文件**，不追加段落。覆写前先归档旧版本。
- `decisions.md` — 稳定结论与决策记录。**仅追加**。当多会话/多 agent/>10 phases 时必需。
- `utils.md` — **唯一资源注册表**：飞书文档、外部网页、仓库、本地路径、接口、数据库、日志平台、看板、本地进程、静态页、CLI/MCP 工具、工单、测试数据、凭据名称，全部登记在此。按行原地更新，禁止写入密钥值。
  - 表头：`| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |`
  - Type 取自枚举 `feishu-doc | web-page | repo | local-path | service-api | database | log-platform | dashboard | local-process | static-site | cli-tool | mcp-tool | ticket | test-asset | credential-ref`，未覆盖的用 `other:<label>`。
  - 每行必须写 `Sensitivity: public|internal|restricted`；`restricted` 行不进快照与恢复摘要。
  - `Access` 写凭据名/角色/`open`/**读取命令**（如 `lark-cli docs +fetch --doc <url>`）；`Verified` 写日期 + **读到的版本**（如 `2026-09-07 (rev 607)`）。
  - 子资源清单（Base 表清单、文档章节）挂 `## Notes` 并以 ID 开头，不一行一条；作为证据引用的单个源码文件不登记。
  - 其他文件（findings/decisions/plan/task_state）**只按 ID 引用**（如 `(res: R3)`），不复制链接或路径。资源首次使用时立即登记。
  - 遗留 MRS 迁移：`python <skill-root>/scripts/scan_resources.py .task-state`（只读草稿，加 `--write` 写入）。
- `plan.md` — 任务计划 + Plan Registry。Registry 仅注册 `docs/plans/*.md`。

### 待办项规则
- `task_state.md` 头部的 `Active Todos` 是唯一的待办真相源。
- 完成待办 = 从 `Active Todos` **删除** + 追加到 `Completed Items`。
- 不从 `progress.md` 推断待办状态，只读 `task_state.md`。
- 恢复或压缩前优先读取 `decisions.md`、`findings.md`、`utils.md` 的最新有限条目，避免长日志遮蔽当前约束。
- 每条待办限单行，详细上下文引用外部文件。

### 更新后
每次修改 MRS 文件后，在 `progress.md` 追加一行时间戳记录。

### Tier 0 文件损坏 ≠ 缺失
Tier 0 文件存在但格式不合规时，**修复该文件，绝不重新初始化** —— MRS 里是真实历史。只有文件**不存在**才进初始化流程。

### 校验
运行 `python <skill-root>/scripts/verify_mrs.py .task-state` 检查 MRS 健康度（或加 `--json` 获取结构化输出）。`<skill-root>` 为 context-resilient-task skill 的安装路径。

## 多任务支持（Multiple MRS）

同一项目内允许多个 MRS 共存：

- 默认 `.task-state/` 不变；并行任务使用 `.task-state-<slug>/`（兄弟目录）
- agent 启动时从 CWD 向上找 `.task-state/` 和 `.task-state-<slug>/`：
  - 找到 0 个 → 初始化新 MRS
  - 找到 1 个 → 使用该 MRS
  - 找到多个 → 必须列出并询问用户恢复哪个，可推荐 mtime 最新的，但不自动选
- 切换任务靠用户在对话中明示，不写"当前任务"指针文件
- 已完成的任务归档到 `.task-state/archive/<slug>-completed/`

完整规则见项目内的 `references/multi-task-workflow.md`（如已安装 context-resilient-task skill）。

## 自动上下文恢复（非 Claude Code agent）

Claude Code 通过 hooks 自动恢复；其他 agent（Codex、Gemini CLI 等）用以下脚本达到同样效果。`<skill-root>` 为 context-resilient-task skill 的安装路径，脚本无第三方依赖、只读、无 MRS 时静默。

- **会话开始 / `/clear` 后 —— 必须先恢复**：运行
  `python <skill-root>/scripts/restore_context.py`
  读取它打印的 "Reconstructed Task State"，据此重建目标、待办、下一步；不要凭记忆继续。
- **结束前 —— 自检漂移**：运行
  `python <skill-root>/scripts/gate_check.py`
  若提示 snapshot 落后于工作区，先更新 `snapshot.md` 并在 `progress.md` 追加记录再结束。
- **上下文将被压缩前（可选）**：运行
  `python <skill-root>/scripts/precompact_digest.py`
  把关键状态打印到对话中，帮助摘要保留要点。

以上"会话开始运行脚本"是给模型的指令（guidance），依赖模型遵守，无需 agent 原生 hook 支持，任何 agent 通用。

Codex 用户可运行 `python <skill-root>/scripts/install_hooks.py --codex`，将 `SessionStart`、`PreCompact`、`Stop` 安装到当前项目 `.codex/hooks.json`，实现强制触发（新增定义需信任/审核）。**不要**用 `~/.codex/config.toml` 的 `notify`：它仅在 `agent-turn-complete`（回合结束后）触发，且无法在会话开始恢复。

Claude Code 用户改用一键安装：`python <skill-root>/scripts/install_hooks.py`（详见 `references/hooks-setup.md`）。
