# Changelog — gapm-mcp-recovery

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 1.0.0 - 2026-09-03

首个标注版本。此前变更见 git 历史，不追认为 release。

当前能力基线：

- 诊断并恢复 Codex 中的 GAPM MCP；当前对话未注入 Tool 时可经 App Server bridge 直接调用
- 覆盖 Tool 缺失、`invalid_client` / `authentication_required`、`serverInfo` 为空等症状
- OAuth 过期仍需浏览器授权；参数与原始日志只落 `.local/`；查询无结果不得断言未调用
