---
name: dify-dsl-generator
description: Generate, refactor, or review Dify workflow DSL/YML for chatflow, workflow, agent, or webhook-triggered apps. Use when translating business requirements, backend APIs, rule-based workflows, or existing Dify YAML into importable DSL; when choosing node types and graph structure; or when migrating complex repo workflows such as TCG_A/TCG_B/TCG_C into cleaner Dify designs.
---

# Dify DSL Generator

生成或优化 Dify DSL 时，先基于现有事实设计，再输出 YAML。优先复用当前仓库已经验证过的模式，不要凭空发明节点结构。

## Use This Skill

执行下列任务时使用本 skill：

- 根据业务需求生成新的 Dify workflow/chatflow DSL
- 改写、拆分、合并已有 Dify YML
- 把规则系统、后端接口、设计文档迁移成 Dify 编排
- 为已有 DSL 补节点、修变量路径、修 graph edges、修版本兼容
- 评审某个 Dify DSL 是否可导入、是否符合当前项目的落地方式

## Work From Evidence

优先读取这些真实来源，再决定 DSL 结构：

1. 当前 skill 自带参考
   - 字段级节点说明：`references/dsl-structure.md`
   - 当前仓库验证过的模式：`references/repo-patterns.md`
2. 当前仓库的已完成 DSL
   - `/opt/casegenerator/dify/TCG_A.yml`
   - `/opt/casegenerator/dify/TCG_B.yml`
   - `/opt/casegenerator/dify/TCG_C_noLLM.yml`
   - `/opt/casegenerator/dify/webhook/TCG_gate.yml`
3. 当前仓库的迁移与设计文档
   - `/opt/casegenerator/docs/plans/2026-02-13-dify-migration-design.md`
   - `/opt/casegenerator/docs/plans/2026-02-21-tcg-large-workflow-split-node-mapping.md`
4. 规则系统
   - `/opt/casegenerator/.cursor/rules/core/case-workflow.mdc`
5. 完整运行工件
   - `/opt/casegenerator/data/tmp/case-21089-m21-rule-run-20260216_123705`

如果用户给了已有 YAML，先以用户文件为主；仓库参考仅用于补缺和校验。

## Workflow

### 1. Decide App Shape

先决定应用模式，不要先写节点：

- `workflow`：单次执行、结构化输出、适合后端编排
- `advanced-chat`：需要对话态、直接面向用户回复
- `agent-chat`：需要自主工具调用，但只有在确实需要 Agent 行为时才选

当前仓库的主流程以 `workflow` 为主，Webhook 入口也优先走 `workflow`。

### 2. Freeze Inputs And Outputs

先列清楚以下内容，再生成节点：

- 输入变量
- 每个阶段的结构化输出
- 哪些字段给人看，哪些字段给下游节点读
- 哪些输出必须稳定为 JSON/object/array

如果下游节点要机器解析，优先让上游 LLM 使用 `structured_output_enabled: true`。

### 3. Select Nodes

按“最简单可维护”原则选节点：

- 文本生成或推理：`llm`
- 确定性加工、清洗、校验、组装 payload：`code`
- 调后端 API 或插件服务：`http-request`
- 门禁、阻断、分流：`if-else`
- 最终结构化返回：`end`
- 面向对话用户直接展示：`answer`
- 数组逐条处理：`iteration` + `iteration-start`

仅在确有收益时再用辅助节点，如 `parameter-extractor`、`tool`、`variable-aggregator`、`template-transform`、`question-classifier`。

### 4. Prefer Repo-Proven Patterns

当前仓库已经验证过的高价值模式：

- A/B/C 拆分：一次性规划流程、逐模块执行流程、收尾/写回流程分开建模
- 后端 deterministic，Dify 负责 LLM：后端读文档、下载媒体、做门禁；Dify 做推理和生成
- `llm -> code(parse/clean/assert) -> http-request(submit)`：最稳的生成提交链路
- `iteration` 处理动态模块列表，而不是写死并行分支
- `http-request(files) -> vision llm`：视觉链路优先吃真实文件，不要让 code 伪造 file 类型

详细模式见 `references/repo-patterns.md`。

### 5. Build Graph Carefully

生成 graph 时遵守这些约束：

- 除 `start` 外，每个节点通常只有一个主入边
- `if-else`、`iteration` 可以有多出边
- `sourceType` / `targetType` 必须与节点 `data.type` 对齐
- 迭代内节点必须显式标记 `isInIteration: true` 和 `iteration_id`
- workflow 型应用优先以 `end` 收口；chatflow 才优先 `answer`

### 6. Validate Before Hand-Off

输出前至少自检：

- frontmatter / app / dependencies / workflow 结构完整
- version 与目标实例兼容
- provider/name 与实例中真实模型一致
- 变量引用格式为 `{{#node.var#}}`
- 所有 `value_selector` 路径存在且语义一致
- 所有被引用的 `structured_output`、`files`、`body`、`output` 都有上游来源
- 阻断分支和成功分支都能闭环

## Default Decisions

没有额外约束时，默认采用：

- `version: 0.5.0`，除非用户明确要求兼容旧实例
- `workflow` 模式
- LLM 节点保留完整 `vision.configs` 结构
- 需要稳定 JSON 时启用 `structured_output`
- 后端调用走 `http-request`
- 最终返回结构化结果走 `end`

## Rules For Common Risk Areas

### Webhook Start

Webhook 场景优先在 Dify UI 配好触发器后导出 DSL，再做精修。不要手写一套未经验证的 webhook start 结构。

### Vision Files

视觉模型优先读取：

- `start` 的 `file/files`
- 或 `http-request` 在二进制响应下生成的 `files`

不要指望 `code` 节点产出 `file` / `array[file]`。

### Structured Output

只要 LLM 输出要给下游机器消费，就优先启用 `structured_output_enabled: true`。下游 `code` 节点优先读 `structured_output`，`text` 仅作兜底。

### Repo Migration

从当前项目规则系统迁移到 Dify 时，优先保留规则里的过程控制思想：

- 先获取语料，再过门禁，再允许生成
- 画板必须下载并留痕
- 模块化流程优先于一次性大 prompt
- 证据和日志优先于 prompt 硬编码

不要为单个模块写特化 prompt 或硬编码先验。

## Output Standard

交付 DSL 时，默认提供：

1. 完整 YAML
2. 节点流程摘要
3. 关键输入/输出字段说明
4. 版本或兼容性假设
5. 若有风险，列出最可能踩坑的 1 到 3 项

## Reference Map

按需读取，不要把所有细节塞进主 skill：

- 需要字段级节点模板、节点类型覆盖、变量格式、edge 约束时：读取 `references/dsl-structure.md`
- 需要当前仓库已经验证的编排模式、媒体链路、A/B/C 拆分经验时：读取 `references/repo-patterns.md`
- 需要最小可用示例时：参考 `examples/`
