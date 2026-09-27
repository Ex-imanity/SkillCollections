# Changelog — whitebox-op-combo

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 1.0.0 - 2026-09-23

首个版本。方法论来自 AI 搜索回答卡片的操作顺序分析（服务端 + Android/iOS/Web 三端），
该分析发现的问题已由开发确认并修复。

当前能力基线：

- 七阶段工作流：基线与范围 → 读写点 → 原子动作与覆盖检查 → 组合剪枝 → 缺陷模式推演 → 验证定级归属 → 输出用例，外加回流
- 原子定义为读写集等价类；覆盖度由孤儿写入点 / 孤儿读取点 / 替换型原子漏写字段 / 隐式动作清单等可计算缺口证明
- `scripts/op_matrix.py`：覆盖检查、有序对标记（RAW/WAW/STALE/RACE/LAYER）与剪枝、三元穿透链、中断点，仅依赖标准库
- atoms.json 结构校验（必填字段、重复 id、悬空引用、`represented_by` 链/环 → 返回 1）；隐式动作清单答案须引用已有原子或 `N/A: 理由`；缺少层信息的读写点单独报出
- 发布前经 Grok 跨代理评审（APPROVE WITH NITS），2 个 P1 与全部 P2 已修复
- 8 类缺陷模式、验证与归属规则、atoms.md / analysis.md / cases.md 模板；cases.md 与 case-lite full.md 格式兼容
- 示例：`examples/ai-search-answer-card/`（atoms.json + 脚本输出）
