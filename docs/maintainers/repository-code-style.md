# Repository Code Style maintenance

Developer-only guidance; not part of the installed runtime bundle. Paths below are relative to the source repository.

## 更新、检查与验证

- 业务仓库当前规范和实现变化后重新核对样本。先修正相应 reference，必要时
  再调整主流程；同步 version、CHANGELOG、根 README 的版本和验证记录。
- 能稳定判定的格式/静态规则优先使用仓库已有检查器。新增检查器或规则配置应是
  单独的、可审查的仓库改动；不要以正则把所有字符串、Map 或数字判成风格违规。
- 用历史 Review 作回归案例，用未参与提炼的任务作保留场景。相同输入比较有/无
  skill 的产物、证据选择、契约保持及过度抽象。由 reviewer 判断主观风格项。
- 保留基线和使用 skill 后的证据，标出未运行项。若基线本已符合规则，不能宣称
  skill 改善了结果。合成场景通过不等于在真实仓库或 leader Review 中已验证有效。

## 本地档案与人工 CR 回归

- `assets/local-style-profile.template.md` 是执行任务会使用的空白模板，随 skill 分发。
  真实档案默认位于目标仓库本地忽略目录；源仓维护时可放在忽略的任务记录中，不把
  私有档案、CR 原文或业务源码复制到 `skills/`。
- 新业务派生场景、历史 diff、原始结果、档案和评分保存在
  `evals/repository-code-style/.local/`。公开 S1-S12 保持独立，不引用本地材料。
- 除内部表达，还检查组织/职责、工具语义、生产用途、近期实质取样、冲突反例与
  缓存失效；含“旧但当前有效”“近期只有格式变化”“HEAD 未变但工作区已变”等反例。
- 有原始 CR 输入时核对所有独立要求及历史未闭环项，区分建议/延期和已改/已验证，
  保留原始版本与定位；转写歧义不能自动变成规则。复用的验收检查具体 API/有效
  版本、实际调用和最小等价证据，不只统计工具名。新增层比较删除/合并方案，
  业务说明需与重构后的职责一致，验证结论绑定实际交付快照。
- 使用旧快照和新版在相同输入下分开执行，评估真实读到的代码、文件落点与发现，
  不以 Skill 文本出现关键词作为效果测试。已参与规则提炼的案例只算回放，不是
  保留任务或盲测；需后续真实开发/人工 CR 才能评估漏检是否减少。

本轮可执行复查场景见 `evals/repository-code-style/evals.json`；合成输入见
`evals/repository-code-style/fixtures/scenarios.md`、`evals/repository-code-style/fixtures/discovery/README.md` 和
`evals/repository-code-style/fixtures/frontend-scenarios.md`、`evals/repository-code-style/fixtures/client-scenarios.md`。
它们不冒充真实仓库文件；S4-S6 的目录可以复制到一次性 Git 仓库并暂存，实际
检查隐藏文件发现和跟踪状态，但不要在真实业务仓库中创建这些 fixture。
