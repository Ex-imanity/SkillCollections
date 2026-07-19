# SkillCollections

个人维护的 Agent Skills 合集，用于沉淀可复用的工作流、测试设计方法、上下文恢复机制和 Dify DSL 编排经验。

这个仓库的定位不是一个单一应用，而是一组可独立安装、按需触发的 skill。每个 skill 目录通常包含：

- `SKILL.md`：skill 的触发条件、执行流程、输出规范和注意事项，是 agent 读取的主入口。
- `README.md`：面向人的使用说明。不是所有 skill 都已有 README。
- `references/`：可按需加载的长文档、模式库、规则说明或补充材料。
- `assets/`：模板、默认风格样例或初始化资源。
- `scripts/`：可复用的脚本工具，优先让 agent 调用脚本而不是手写重复逻辑。
- `examples/`：示例文件或可参考的产物。
- `tests/`：脚本或关键逻辑的测试用例。

## 目录结构

```text
.
├── case-design-strategy-skill/
│   ├── SKILL.md
│   └── references/
├── case-lite/
│   ├── README.md
│   ├── SKILL.md
│   ├── assets/
│   ├── references/
│   └── scripts/
├── context-resilient-task/
│   ├── README.md
│   ├── SKILL.md
│   ├── assets/
│   ├── docs/
│   ├── references/
│   ├── scripts/
│   └── tests/
├── dify-dsl-generator/
│   ├── SKILL.md
│   ├── examples/
│   └── references/
├── internal-api-cookie-auth/
│   ├── SKILL.md
│   ├── scripts/
│   └── tests/
└── docs/
    └── plans/
```

## Skills 总览

| Skill | 作用 | 适用场景 | 主要注意事项 |
| --- | --- | --- | --- |
| `case-design-strategy-skill` | 测试用例设计策略层，用于补强覆盖度、评审场景和设计边界/异常/权限/埋点等测试点 | 需求用例评审、覆盖度补充、事件埋点校验、跨端一致性风险分析 | 它不是端到端用例生成器；如果已经进入 `case-lite` 主流程，只在自检或覆盖度评审阶段借用其策略，不覆盖 `case-lite` 的产物格式和写回规则 |
| `case-lite` | 小需求测试用例生成流程，从飞书文档选章到生成用例，再可选写回搬山 | 单一功能点、1-2 篇文档、无需模块拆分的小需求用例生成 | 依赖飞书文档 MCP；搬山 MCP 推荐配置；所有阶段产物必须落盘到 `case-lite-output/{slug}/`，章节选择和补充信息确认是人工检查点 |
| `context-resilient-task` | 上下文弹性任务管理，用磁盘上的 MRS 文件恢复长期任务状态 | 多阶段开发、跨会话继续、`/clear` 后恢复、避免 agent 忘记待办或编造状态 | `task_state.md` 是 source of truth，必须原地更新；`progress.md` 和 `decisions.md` 只追加；缺少 Tier 0 文件时应先初始化 MRS |
| `dify-dsl-generator` | 生成、重构或评审 Dify workflow/chatflow/agent DSL | 把业务需求、后端接口、规则系统或已有 YAML 转为可导入的 Dify DSL | 先冻结输入输出和应用形态，再写 YAML；优先复用 `references/` 和已有示例中的验证模式；输出前检查节点类型、变量路径、edge 和结构化输出 |
| `internal-api-cookie-auth` | 为受支持内部 API 获取短期 CAS Cookie，并规范认证失败后的处理 | Internal AD/UOS、Athena、Compass 的接口开发与排障，Cookie 缺失或 HTTP 401 | 仅限允许的内部域名；不输出或持久化凭证；403 视为可能的权限问题，禁止盲目重试写操作 |

## 各 Skill 简介

### case-design-strategy-skill

这是一个测试设计策略 skill，强调覆盖深度、颗粒度稳定、可观测断言和风险披露。它适合在已有需求、技术方案、交互说明或埋点表的基础上，帮助 agent 设计或评审测试点。

重点覆盖：

- 功能路径、边界、异常、权限、状态切换和恢复场景。
- APP、WEB、后端/API、跨端一致性等不同域的测试角度。
- 埋点事件的触发、不触发、参数契约、去重和证据路径。

注意：它主要是策略层，不负责飞书文档读取、搬山写回或完整 case-lite 流程。

### case-lite

`case-lite` 面向小需求测试用例生成，核心理念是精准输入：用户先选择飞书文档中的相关章节，agent 再基于选定语料生成场景结构和完整用例。

典型流程：

1. 收集需求名称、飞书文档链接和文档类型。
2. 展示章节树，由用户手动选择纳入范围。
3. 统一确认补充信息。
4. 生成 `structure.md` 并等待审核。
5. 生成 `full.md` 并等待审核。
6. 可选执行 agent 自检补漏。
7. 可选写回搬山测试平台。

主要产物保存在 `case-lite-output/{slug}/`，包括章节树、选定语料、参考用例、场景结构、完整用例、自检结果和写回日志。

### context-resilient-task

`context-resilient-task` 用 MRS（Minimum Recovery Set）把任务状态写到磁盘，避免复杂任务在会话中断、上下文压缩、agent 切换后无法继续。

核心文件：

- `task_state.md`：当前状态和待办的唯一权威来源。
- `plan.md`：任务计划和 `docs/plans/*.md` 的 Plan Registry。
- `snapshot.md`：最新恢复快照。
- `findings.md` / `progress.md` / `decisions.md`：发现、执行日志和稳定决策。

注意：不要依赖聊天记录恢复任务；恢复时应从 `.task-state/` 或 `.task-state-<slug>/` 读取事实。多任务并行时使用不同的 MRS 目录隔离状态。

### dify-dsl-generator

`dify-dsl-generator` 用于把需求、接口、规则流程或已有 Dify YAML 转换为更稳定、可导入、可维护的 Dify DSL。

该 skill 参考 [wwwzhouhui/skills_collection 的 dify-dsl-generator](https://github.com/wwwzhouhui/skills_collection/tree/main/dify-dsl-generator) 二次开发调整而来，并结合本仓库的 Dify 迁移经验补充了本地验证模式和注意事项。

它强调先设计再输出：

- 先确定 app 类型：`workflow`、`advanced-chat` 或 `agent-chat`。
- 冻结输入变量、阶段输出和下游机器可解析字段。
- 选择最简单可维护的节点组合，例如 `llm`、`code`、`http-request`、`if-else`、`iteration`、`end`。
- 输出前校验 frontmatter、version、变量引用、value selector、edge、文件输入和结构化输出。

注意：Webhook、vision files、structured output 和复杂迁移流程是高风险区域，应优先参考 `references/` 和 `examples/` 中已有模式。

## 安装与使用建议

可以按需复制单个 skill 目录到本地 agent 的 skills 目录，也可以通过支持 GitHub skill 安装的工具安装整个仓库。

```bash
# 示例：手动安装单个 skill
cp -r case-lite ~/.cc-switch/skills/case-lite
cp -r context-resilient-task ~/.cc-switch/skills/context-resilient-task
```

使用建议：

- 修改 skill 行为时，优先编辑对应目录下的 `SKILL.md`，并同步更新相关 `README.md` 或 `references/`。
- 长篇规则放在 `references/`，让 `SKILL.md` 只保留触发条件、关键流程和必须遵守的约束。
- 可执行流程尽量沉淀到 `scripts/`，减少 agent 每次手写逻辑带来的不稳定。
- 涉及外部系统的 skill 要明确依赖，例如 MCP 配置、认证方式、降级路径和写回风险。
- 如果新增 skill，建议至少包含 `SKILL.md`，并在本 README 的总览表中补充入口说明。

## 维护注意事项

- 保持 skill 边界清晰：流程型 skill 负责端到端步骤，策略型 skill 只提供评审和设计方法。
- 不要让多个 skill 对同一产物格式提出冲突要求。组合使用时，以当前主流程 skill 的输出格式为准。
- 示例、模板和脚本最好能独立运行或被快速验证，避免只停留在 prompt 描述。
- 对外部平台的写回操作应保留 dry-run、日志或可复查产物。
- 根目录 README 只做导航和简述，细节放回各 skill 自己的 README 或 references。
