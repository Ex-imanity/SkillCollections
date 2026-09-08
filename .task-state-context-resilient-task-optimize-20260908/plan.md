# Plan

**Last Updated:** 2026-09-08 21:08:00
**Goal:** 基于真实项目 MRS 优化 context-resilient-task，降低长对话遗忘并分离 utils 上下文

## Phase 1: 盘点真实 MRS 失败证据
**Status:** complete
**Description:** TODO — describe how this phase delivers "盘点真实 MRS 失败证据".
**Deliverables:**
- TODO

## Phase 2: 新增 utils.md 工具环境资源档案
**Status:** complete
**Description:** TODO — describe how this phase delivers "新增 utils.md 工具环境资源档案".
**Deliverables:**
- TODO

## Phase 3: 恢复与压缩摘要保留有限决策发现
**Status:** complete
**Description:** TODO — describe how this phase delivers "恢复与压缩摘要保留有限决策发现".
**Deliverables:**
- TODO

## Phase 4: 验证重复 todo 区块
**Status:** complete
**Description:** TODO — describe how this phase delivers "验证重复 todo 区块".
**Deliverables:**
- TODO

## Phase 5: ClaudeCode 审核后的缺陷修复
**Status:** complete
**Description:** 根据真实历史 MRS 审核结果修复预算、最新性、重复区块、pinning、敏感度和漂移检测问题，并以真实形态 fixtures 回归。
**Deliverables:**
- `Review/ByClaudeCode/2026-09-08-context-resilient-task-optimization-review.md`
- `context-resilient-task/tests/fixtures/`（待补）

## Plan Registry (docs/plans)

<!--
Strict boundary: register ONLY docs/plans/*.md files.
Do NOT register CLAUDE.md, AGENTS.md, .task-state/*, or docs/runbooks/*.
Status values: pending | in_progress | completed | abandoned
-->

| File | Source Skill | Date | Status |
|------|--------------|------|--------|

## Phase 6: 二次复审后的 P0/P1 修复
**Status:** complete
**Description:** 修复 ClaudeCode 二次复审发现的敏感度分段、源行号、单 MRS 预算、最新 MRS 选择和模板脚手架问题。
**Deliverables:**
- `Review/ByClaudeCode/2026-09-08-context-resilient-task-optimization-rereview.md`
- 覆盖真实历史格式的回归测试

## Phase 7: 第三轮复审
**Status:** complete
**Description:** 对 1.4.0 修复执行独立 ClaudeCode 复审并关闭剩余阻塞。

## Phase 8: 第四轮复审
**Status:** complete
**Description:** 对 1.5.0 的敏感度 fail-closed、按区块 snapshot 压缩和统一 recency 逻辑执行独立复审。

## Phase 9: 最终复审后的 P1 修复
**Status:** complete
**Description:** 修复中文敏感度标签、legacy 轮次区块兼容和 precompact 尾部保留问题。

## Reference Index

<!--
Optional. For non-plan reference files (runbooks, external design docs).
NOT for CLAUDE.md / AGENTS.md (auto-loaded) or MRS files. Delete this section if unused.
-->

| File | Purpose |
|------|---------|
