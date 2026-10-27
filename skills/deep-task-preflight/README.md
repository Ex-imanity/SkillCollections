# deep-task-preflight

一个在实现前建立“目标—范围—验收—证据”闭环，并在实现后核对“输入—转换—结果”的 Skill。它解决的不是让 Agent 展示更多隐藏思维，而是把容易被遗漏的判断变成可检查的产物，减少“做了很多但没解决真正问题”、范围混淆和反复返工。

## 适用场景

- 多文件、跨仓库或跨系统改动
- 用户要做 PPT、报告、方案、评审材料等面向他人的交付物
- 需求背景、动机、范围或完成边界不清楚
- 用户说“先想清楚”“先写计划”“定义验收标准”“避免后面重做”
- 之前的实现被发现漏了背景、边界、证据、异常路径或结果
- 调试、异步链路、权限/数据边界、接口或存储等兼容或验证风险明显的变更
- 需要对照已有客户端/服务端实现、解析器、渲染器或数据合同的任务

UI、数据管道、文档、调试、合同/运维等领域的专门检查由 `references/adapters/`
按需补充；单纯的“帮我确认结果”类请求不需要本 Skill。一行修复、明确的直接问答
和其他低风险小改动使用轻量模式即可。

## 模式

- **轻量模式**：一个明确、可逆的小改动，只输出目标、一个验收检查、范围边界和下一步。
- **中等模式**：目标清楚但存在兼容或验证风险，使用压缩版 Preflight Packet（保留
  验收 ID、未知项、闸门和验证矩阵）。
- **完整模式**：目标不清、之前被驳回、跨仓库/系统、面向受众交付物、不可逆或多阶段任务。

## 核心产物

完整模式在动手前形成一份 Preflight Packet，至少包含：

1. 用户真正要得到的结果，以及为什么做、给谁看
2. 范围内/范围外和事实来源
3. 可观察、可验证的验收标准
4. 未知项、假设、风险和替代方案
5. 具体改动面、兼容/回滚边界和验证矩阵
6. `READY`、`NEEDS INPUT` 或 `BLOCKED` 闸门结论

实现过程中还要求记录参考实现，并沿着“输入 → 转换 → 输出”检查每个边界；通用验证梯度是：自动检查、边界检查、消费者真实读回、验收矩阵闭环。UI、数据管道、文档、调试和合同/运维的专门规则放在 `references/adapters/`，按需读取，避免核心 Skill 被具体场景不断打补丁。

实现结束后逐条关闭验收矩阵。没有证据的效果、上线状态或完成度必须标为未验证，
不能用“文件已生成”代替验收。

## 与其他 Skill 配合

`repository-code-style` 负责本地代码风格，`context-resilient-task` 负责跨会话持久化，
`cross-agent-review` 负责用户明确要求的独立 Agent 评审。本 Skill 先把目标和验收理顺，再交给这些 Skill 执行或复核。

## 目录

```text
deep-task-preflight/
├── SKILL.md
├── README.md
├── CHANGELOG.md
└── references/
    ├── packet-template.md
    ├── challenge-checks.md
    └── adapters/
        ├── code-changes.md
        ├── contracts-and-operations.md
        ├── data-pipelines.md
        ├── debugging.md
        ├── documents.md
        └── ui-interactive.md
```

## 安装

复制整个 `deep-task-preflight/` 目录到目标 Agent 的 skills 目录，不要只复制
`SKILL.md`。

## 源码维护与验证

评估场景在源码仓库的 `evals/deep-task-preflight/`，新增领域 adapter 的维护指南在
`docs/maintainers/deep-task-preflight.md`；安装和运行不需要这些开发文件。
维护时在源码仓库根目录执行：

```bash
python tools/run_tests.py
```
