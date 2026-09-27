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
   脚本、参考资料和模板可能是工作流的一部分。

例如：

```bash
git clone https://github.com/Ex-imanity/SkillCollections.git
cp -R SkillCollections/skills/context-resilient-task <your-agent-skills-dir>/
```

安装前请先检查 Skill 中的依赖、脚本和外部服务。涉及内部域名或内部账号体系的
Skill 不应直接用于不具备相应权限的环境。

## Skill 总览

| Skill | 版本 | 适用场景 | 文档 |
| --- | ---: | --- | --- |
| `case-design-strategy-skill` | 1.0.0 | 需求用例评审、覆盖度补充、边界/异常/权限/埋点分析 | [SKILL.md](skills/case-design-strategy-skill/SKILL.md) |
| `case-lite` | 1.2.0 | 从飞书文档选章，生成小需求测试用例并可选写回搬山 | [README](skills/case-lite/README.md) |
| `case-reorganize` | 1.0.0 | 将搬山已有用例按业务链路合并和重组 | [SKILL.md](skills/case-reorganize/SKILL.md) |
| `context-resilient-task` | 1.8.0 | 用文件化 MRS 保存任务状态，支持跨会话恢复 | [README](skills/context-resilient-task/README.md) |
| `cross-agent-review` | 2.1.0 | 让不同本地 Agent 对计划或代码进行带证据评审 | [README](skills/cross-agent-review/README.md) |
| `dify-dsl-generator` | 1.0.0 | 生成、重构或评审 Dify workflow/chatflow/agent DSL | [SKILL.md](skills/dify-dsl-generator/SKILL.md) |
| `gapm-mcp-recovery` | 1.0.0 | 诊断和恢复 GAPM MCP | [README](skills/gapm-mcp-recovery/README.md) |
| `internal-api-cookie-auth` | 1.0.0 | 内部 HTTPS/CAS 认证与安全请求封装 | [README](skills/internal-api-cookie-auth/README.md) |
| `repository-code-style` | 1.2.0 | 根据目标仓库已有范例约束实现和 Review 风格 | [README](skills/repository-code-style/README.md) |
| `whitebox-op-combo` | 1.0.0 | 按读写集分析多操作组合、代码路径和缺陷候选 | [README](skills/whitebox-op-combo/README.md) |

`gapm-mcp-recovery`、`internal-api-cookie-auth` 和 `repository-code-style` 包含内部
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
└── tests/         # 可选：脚本或协议测试
```

`SKILL.md` 是每个 Skill 的行为入口。长文档放到 `references/`，运行逻辑放到
`scripts/`，避免把一次触发不需要的内容全部加载进上下文。

## 质量与版本

- 仓库级约定测试：`python -m unittest discover -s tests`
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
