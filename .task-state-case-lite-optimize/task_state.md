# Task State

**Last Updated:** 2026-07-01 21:10:00
**Updated By:** Claude (review + fixes)

## Goal
优化 case-lite skill：分析现有问题，设计并实施改进方案，提升用例生成质量与稳定性

## Status
active

## Active Todos
_(none)_

## Current Phase
Phase 6.1: Review 复核 + F1–F5 修复完成，待 codex 复核

## Next Action
交 codex 复核 setup_mcp.py 与文档改动。复核重点见 findings.md 末尾三条：(1) _strip_toml_table 写侧仍为字符串裁剪的边角风险；(2) ambiguity 选路后凭证读取一致性；(3) 是否需要“只刷新 env 凭证”的更细粒度选项

## Completed Items
- [x] 分析 case-lite 现有 skill 内容与结构（2026-05-19，见 findings.md）
- [x] 识别用例生成流程中的问题点（5 个问题，P0×1 P1×2 P2×2，见 findings.md）
- [x] darwin 基线评分：62.3/100（2026-05-19）
- [x] Round 1 改进：Step 3b corpus 约束重写，评分 62.3→75.0（2026-05-19）
- [x] Round 2 改进：Step 2a 选章记录格式标准化，评分 75.0→76.5（2026-05-19）
- [x] 修复 `case-lite/scripts/writeback.py` 执行步骤 bullet 解析缺失，并添加回归测试（2026-05-29）
- [x] 优化 case-lite 文档获取流程：新增 `get_child_documents` 递归发现 wiki/docx-in-wiki 子文档，用户确认后作为同类文档纳入章节浏览（2026-06-15）
- [x] 优化首次使用依赖安装：新增 `setup_mcp.py` 诊断/修复脚本、安装参考文档和安全契约测试（2026-07-01）
- [x] Phase 6 Review 复核并修复 F1–F5：路径歧义拒盲写、no-clobber、原子写/权限收敛、凭证来源读取、测试与文档补齐（2026-07-01，见 findings.md review 表；待 codex 复核）

## Open Questions
_(none)_

## Artifacts
- plan.md (created at init)
- snapshot.md (created at init)

## Project Context
See CLAUDE.md for project constraints, AGENTS.md for agent guidelines.
