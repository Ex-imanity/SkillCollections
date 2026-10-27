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

本轮可执行复查场景见 `evals/repository-code-style/evals.json`；合成输入见
`evals/repository-code-style/fixtures/scenarios.md`、`evals/repository-code-style/fixtures/discovery/README.md` 和
`evals/repository-code-style/fixtures/frontend-scenarios.md`、`evals/repository-code-style/fixtures/client-scenarios.md`。
它们不冒充真实仓库文件；S4-S6 的目录可以复制到一次性 Git 仓库并暂存，实际
检查隐藏文件发现和跟踪状态，但不要在真实业务仓库中创建这些 fixture。
