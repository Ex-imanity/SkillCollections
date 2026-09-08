# Changelog — context-resilient-task

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 1.5.0 - 2026-09-08

- 敏感度解析覆盖粗体字段、中文全角冒号、表格行和未知高风险等级，默认 fail-closed。
- 超长 snapshot 按区块压缩并保留恢复必需区块；统一 list/restore/precompact 的 MRS 新旧排序。
- 补充 4000 字符预算、敏感度和结构保留回归测试。

## 1.4.0 - 2026-09-08

- 修复超长 task state 导致 snapshot 丢失必需区块、restore 丢失 Next Action 的问题。
- 敏感度解析兼容 Markdown 粗体、等号和中文标签；`Pinned` 标记兼容模板写法。
- 统一 MRS recency 信号，确保单/多 MRS 输出预算与必需恢复字段同时满足。

## 1.3.0 - 2026-09-08

- 修复 restricted utils 混合条目泄露、HTML comment/fenced code 源行号错位和单 MRS 输出超限。
- 统一 restore/precompact 的 MRS 新旧排序，过滤模板脚手架，兼容 `Pinned: yes` 标记并修正嵌入标题层级。
- 修正文档中的 Tier 1 条目归属与 pinned invariants 说明。

## 1.2.0 - 2026-09-08

- 修复多 MRS 摘要无全局预算、历史日志读取文件头部、轮次后缀权威区块漏检等长对话恢复缺陷。
- 新增固定约束（`Invariants (pinned)`）优先恢复、utils 敏感度分级与疑似凭据校验。
- 快照中的嵌入条目降级为三级标题，并在 Tier 1 更新晚于快照时发出漂移告警。

## 1.1.0 - 2026-09-08

- 新 MRS 自动创建 `utils.md`，独立保存工具、环境、数据库/服务器、日志和本地资源指针。
- 恢复、压缩摘要和快照纳入 `decisions.md`、`findings.md`、`utils.md` 的最新有限条目，降低长对话遗忘风险。
- 验证器拒绝 `task_state.md` 中重复的 `Active Todos` / `Completed Items` 权威区块；旧 MRS 缺少 `utils.md` 仅告警。

## 1.0.0 - 2026-09-03

首个标注版本。此前变更见 git 历史，不追认为 release。

当前能力基线：

- 基于磁盘 MRS（`.task-state/`）的上下文弹性任务管理，跨 `/clear`、会话中断、agent 切换恢复任务状态
- `task_state.md` 为 source of truth 且原地更新；`progress.md` / `decisions.md` 仅追加
- 缺少 Tier 0 文件时先初始化 MRS
