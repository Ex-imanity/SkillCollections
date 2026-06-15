# Task State

**Last Updated:** 2026-06-15 20:25:37
**Updated By:** Codex

## Goal
优化 case-lite skill：分析现有问题，设计并实施改进方案，提升用例生成质量与稳定性

## Status
active

## Active Todos
_(none)_

## Current Phase
Phase 5: wiki 子文档递归发现优化完成

## Next Action
如需继续优化，进行下一轮 case-lite 质量评估或同步安装目录

## Completed Items
- [x] 分析 case-lite 现有 skill 内容与结构（2026-05-19，见 findings.md）
- [x] 识别用例生成流程中的问题点（5 个问题，P0×1 P1×2 P2×2，见 findings.md）
- [x] darwin 基线评分：62.3/100（2026-05-19）
- [x] Round 1 改进：Step 3b corpus 约束重写，评分 62.3→75.0（2026-05-19）
- [x] Round 2 改进：Step 2a 选章记录格式标准化，评分 75.0→76.5（2026-05-19）
- [x] 修复 `case-lite/scripts/writeback.py` 执行步骤 bullet 解析缺失，并添加回归测试（2026-05-29）
- [x] 优化 case-lite 文档获取流程：新增 `get_child_documents` 递归发现 wiki/docx-in-wiki 子文档，用户确认后作为同类文档纳入章节浏览（2026-06-15）

## Open Questions
_(none)_

## Artifacts
- plan.md (created at init)
- snapshot.md (created at init)

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
