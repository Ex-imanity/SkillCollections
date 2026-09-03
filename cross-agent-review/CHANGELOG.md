# Changelog — cross-agent-review

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

- 本机 Codex 与 ClaudeCode 双向只读评审：primary 保连续性与修复责任，reviewer 只返回带证据的 verdict
- 仅依赖本机 `claude` + `codex` CLI，官方 Codex plugin 仅为可选 fallback
- fail-closed、并发安全的固定 round cap（每 artifact 至多 2 次启动 / 2 次成功）、脱敏持久化
- readiness 判定基于真实结果信封，不采信 auth status
- 注：SKILL.md 内另有 `Status:` 成熟度标注，与版本号是两个独立维度
