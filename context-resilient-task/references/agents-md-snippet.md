# AGENTS.md MRS Snippet

Copy the section below into your project's root `AGENTS.md` file to ensure all agents (Claude Code, Codex, etc.) follow the same MRS update rules.

---

```markdown
## MRS 操作规范 (.task-state/)

本项目使用 `.task-state/` 目录管理跨会话任务状态。所有 agent 必须遵守以下规则。

### 文件职责与更新方式
- `task_state.md` — 当前状态唯一真相源。**原地修改**已有字段，不追加新的日期段落。限 300 行。
- `progress.md` — 执行日志。**仅追加**，不覆写已有内容。
- `snapshot.md` — 最新检查点快照。每次**覆写整个文件**，不追加段落。覆写前先归档旧版本。
- `decisions.md` — 稳定结论与决策记录。**仅追加**。
- `plan.md` — 任务计划 + Plan Registry。Registry 仅注册 `docs/plans/*.md`。

### 待办项规则
- `task_state.md` 头部的 `Active Todos` 是唯一的待办真相源。
- 完成待办 = 从 `Active Todos` **删除** + 追加到 `Completed Items`。
- 不从 `progress.md` 推断待办状态，只读 `task_state.md`。
- 每条待办限单行，详细上下文引用外部文件。

### 更新后
每次修改 MRS 文件后，在 `progress.md` 追加一行时间戳记录。

### 校验
运行 `python <skill-root>/scripts/verify_mrs.py .task-state/` 检查 MRS 健康度（或使用 `--json` 获取结构化输出）。
`<skill-root>` 为 context-resilient-task skill 的安装路径。
```
