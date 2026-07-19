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
- `plan.md` — 任务计划 + Plan Registry。Registry 仅注册 `docs/plans/*.md`。

### 待办项规则
- `task_state.md` 头部的 `Active Todos` 是唯一的待办真相源。
- 完成待办 = 从 `Active Todos` **删除** + 追加到 `Completed Items`。
- 不从 `progress.md` 推断待办状态，只读 `task_state.md`。
- 每条待办限单行，详细上下文引用外部文件。

### 更新后
每次修改 MRS 文件后，在 `progress.md` 追加一行时间戳记录。

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

Codex 较新版本支持原生命令 hook（如 `SessionStart`），可直接执行 `restore_context.py` 实现强制触发；配置路径与各事件输出格式随版本变化，接入前请查当前 Codex 文档（非托管 hook 需先信任/审核）。**不要**用 `~/.codex/config.toml` 的 `notify`：它仅在 `agent-turn-complete`（回合结束后）触发，且以 JSON 参数传入，脚本无法据此在会话开始恢复。

Claude Code 用户改用一键安装：`python <skill-root>/scripts/install_hooks.py`（详见 `references/hooks-setup.md`）。
