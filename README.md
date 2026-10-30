# SkillCollections

Reusable Agent Skills for QA workflows, durable context, Dify DSL generation, and
cross-agent review.

面向 Claude Code、Codex、GitHub Copilot 以及其他兼容 `SKILL.md` 的 Agent，提供可
独立安装的工作流 Skill。每个 Skill 都放在 [`skills/`](skills/) 下，包含自己的
入口、参考资料、脚本和验证文件。

> 这是一个 Skill 集合，不是一个需要编译或运行的单体应用。

## 快速开始

1. 浏览 [Skill 总览](#skill-总览)，选择一个目录。
2. 阅读该目录的 `SKILL.md`、`README.md`（如果存在）和 `CHANGELOG.md`。
3. 将整个 Skill 目录复制到目标 Agent 的 skills 目录。不要只复制 `SKILL.md`，因为
   脚本、参考资料和模板可能是工作流的一部分。`skills/<name>/` 仅包含运行包，仓库级
   `tests/`、`evals/` 和 `docs/maintainers/` 不参与安装。

例如：

```bash
git clone https://github.com/Ex-imanity/SkillCollections.git
cp -R SkillCollections/skills/context-resilient-task <your-agent-skills-dir>/
```

维护时先修改本仓库的源文件，并同步版本、`CHANGELOG.md` 和 README。完成检查、
提交和推送后，再由使用者按需手动同步到安装目录；安装目录只是运行副本。

安装前请先检查 Skill 中的依赖、脚本和外部服务。涉及内部域名或内部账号体系的
Skill 不应直接用于不具备相应权限的环境。

## Skill 总览

| Skill | 版本 | 适用场景 | 文档 |
| --- | ---: | --- | --- |
| `case-design-strategy-skill` | 1.0.1 | 需求用例评审、覆盖度补充、边界/异常/权限/埋点分析 | [SKILL.md](skills/case-design-strategy-skill/SKILL.md) |
| `case-lite` | 1.2.1 | 从飞书文档选章，生成小需求测试用例并可选写回搬山 | [README](skills/case-lite/README.md) |
| `case-lite-lark` | 0.2.3 | 本地或平台复用团队飞书应用，通过 lark-cli 选章生成用例，无需配置 stdio MCP | [README](skills/case-lite-lark/README.md) |
| `case-reorganize` | 1.0.0 | 将搬山已有用例按业务链路合并和重组 | [SKILL.md](skills/case-reorganize/SKILL.md) |
| `context-resilient-task` | 1.10.0 | 文件化 MRS 跨会话恢复与问题召回，支持嵌套 slot、旧布局兼容和可回滚迁移 | [README](skills/context-resilient-task/README.md) |
| `cross-agent-review` | 2.4.0 | 本地 Agent 带证据互审，核对目录职责、复用语义及 CR 逐项闭环，支持三向超时续跑 | [README](skills/cross-agent-review/README.md) |
| `deep-task-preflight` | 1.2.1 | 通用的实现前目标/验收闸门与输入—转换—结果验证 | [README](skills/deep-task-preflight/README.md) |
| `dify-dsl-generator` | 1.0.0 | 生成、重构或评审 Dify workflow/chatflow/agent DSL | [SKILL.md](skills/dify-dsl-generator/SKILL.md) |
| `internal-api-cookie-auth` | 1.0.2 | 内部 HTTPS/CAS 认证与安全请求封装 | [README](skills/internal-api-cookie-auth/README.md) |
| `repository-code-style` | 1.4.0 | 本地风格档案、近期取样、目录分层/复用语义、CR 核销及普通/跨 Agent Review | [README](skills/repository-code-style/README.md) |
| `whitebox-op-combo` | 1.0.1 | 按读写集分析多操作组合、代码路径和缺陷候选 | [README](skills/whitebox-op-combo/README.md) |

`internal-api-cookie-auth` 和 `repository-code-style` 包含内部
环境或组织资料。它们保留在集合中用于已授权环境，发布到其他组织前应完成独立的
脱敏和安全评审。

## 目录约定

每个 Skill 至少包含：

```text
skills/<skill-name>/
├── SKILL.md       # Agent 读取的入口，含 name/version/description
├── CHANGELOG.md   # 面向使用者的变更记录
├── README.md      # 可选：面向人的使用说明
├── references/    # 可选：按需读取的长文档
├── scripts/       # 可选：可执行工具
├── assets/        # 可选：模板和资源
└── examples/      # 可选：运行时实际使用的输入/输出示例
```

`SKILL.md` 是每个 Skill 的行为入口。长文档放到 `references/`，运行逻辑放到
`scripts/`，避免把一次触发不需要的内容全部加载进上下文。

开发验证材料统一放在仓库级目录：

```text
tests/<skill>/        # 单元测试，不随 skill 分发
evals/<skill>/        # 评估清单、合成夹具、预期和验证记录
docs/maintainers/     # 修改 skill 本身的维护指南和模板
tools/run_tests.py    # 分进程运行仓库约定和全部 skill 测试
```

实际生成任务需要的配置模板、协议参考和示例仍保留在 skill 内。合成评估输入、故意
错误的提案及评估结果不能作为业务仓库的历史风格依据。维护细则见
[CONTRIBUTING.md](CONTRIBUTING.md)、[测试说明](tests/README.md)和[评估说明](evals/README.md)。

## 质量与版本

- 开发检查使用 Python 3.11+：`python tools/run_tests.py`，覆盖仓库约定、分发边界及全部
  skill 单元测试；每组使用独立进程，避免同名模块互相污染。
- 每个 Skill 的 `SKILL.md`、`CHANGELOG.md` 和本 README 的版本必须一致。
- 版本按使用者可见的兼容性变化递增；细则见各 Skill 的变更记录。
- 每次发布前应检查相对链接、脚本依赖、示例和敏感信息。

## 贡献

新增或修改 Skill 前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按
[SECURITY.md](SECURITY.md) 处理，不要在 Issue 中公开凭证、Cookie、内部日志或真实
用户数据。

更多工作流比较资料见 [docs/workflow-skills-comparison.md](docs/workflow-skills-comparison.md)。

## License

仓库使用 [MIT License](LICENSE)。第三方来源和各 Skill 的额外限制以对应目录中的
说明为准。
