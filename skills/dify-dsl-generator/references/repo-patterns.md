# 当前仓库的 Dify 实战模式

只在需要复用 `/opt/casegenerator` 已验证方案时读取本文件。

## 1. 主设计原则

来自当前仓库迁移设计与规则系统的共识：

- 后端负责 deterministic 能力
  - 飞书读取
  - 语料裁剪
  - 媒体下载
  - 门禁校验
  - 产物落盘
- Dify 负责 LLM 推理与生成
  - 模块规划
  - 选章决策
  - 场景结构生成
  - 完整用例生成

不要把单模块特化知识硬编码进 prompt；优先修后端候选质量、归一化和门禁。

## 2. A / B / C 拆分模式

当前仓库验证过的推荐拆分：

### WF-A

一次性执行：

- 建 job
- 阶段 A 模块提取
- digest 汇总
- 模块规划
- 全局 assignment 保存

适合节点组合：

- `start`
- `code`
- `http-request`
- `llm`
- `if-else`
- `iteration`
- `end`

### WF-B

按模块执行：

- 获取候选章节
- LLM 精准选章
- acquire corpus
- 媒体准备
- 生成 structure/full
- 提交产物

典型链路：

`http-request(candidates) -> llm(select) -> code(parse) -> http-request(acquire) -> code(analyze) -> if-else(gate) -> llm(generate) -> code(clean/assert) -> http-request(submit)`

### WF-C

一次性收尾：

- merge
- 可选 verify
- 可选 writeback

若不需要 LLM，可直接 `http-request + code + end`。

## 3. 结构化输出模式

适合：

- 模块规划 JSON
- 选章计划 JSON
- 兜底判定结果
- assignment plan
- 任何需要给 `code/http-request` 消费的对象

推荐链路：

`llm(structured_output) -> code(parse/fallback) -> code(validate) -> if-else`

不要依赖模型输出自然语言 JSON 片段再用正则硬抠，除非目标实例不支持 `structured_output`。

## 4. 媒体与视觉模式

当前仓库踩过的关键坑：

- HTTP 节点只有在响应是二进制文件时才会产出可供 vision 使用的 `files`
- JSON body 里的 `files` 数组不会自动成为节点的 `files`
- `code` 不能可靠地产出 `file` 类型

推荐链路：

1. 后端下载或提供可访问的媒体 URL
2. `http-request` 拉取真实文件
3. `llm(vision.enabled=true)` 读取 `files`
4. `code` 清洗视觉结果并做图证门禁

当前仓库特别强调：

- boards 必须下载并留痕
- images 可按需下载，但必须记录决策

## 5. 迭代模式

当目标模块数量动态变化时，优先使用 `iteration`：

1. `code` 构造 `array[object]`
2. `iteration.iterator_selector` 指向该数组
3. 迭代内执行单模块链路
4. 迭代外汇总 `iteration.output`

常见坑：

- merge 节点只支持 `dict/string`，却没处理 `list`
- 迭代空输出没有被门禁拦住
- 迭代内边和节点漏写 `isInIteration`

## 6. 门禁与阻断模式

当前仓库 workflow 大量使用“先门禁，再继续”：

- 语料门禁
- style_profile 门禁
- 图证门禁
- 模块覆盖门禁
- 章节归属门禁

推荐链路：

`code(analyze) -> if-else -> code(build blocked payload) -> http-request(log) -> end`

这样比直接 `answer` 更适合 workflow 场景，因为后端能稳定拿到结构化失败原因。

## 7. Webhook Gate 模式

`/opt/casegenerator/dify/webhook/TCG_gate.yml` 提供了 webhook workflow 的落地样例。适合：

- 统一入口门禁
- 轻量鉴权
- 结构化请求校验
- 决定后续是否允许进入主流程

建议：

- 先在 UI 配置 webhook 输入
- 导出后再精修
- 输出走 `end`，方便后端统一消费

## 8. 推荐的输出习惯

生成给本仓库使用的 DSL 时，优先包含：

- 节点标题用中文且语义明确
- 每个阶段至少一个可读日志点或可解释结构化输出
- `end.outputs` 返回后端真正要消费的字段
- 需要阻断时返回 `ok/status/reason/details` 一类字段

## 9. 什么时候不要照抄现有 DSL

不要机械复制现有大 YAML。需要改写时，先保留这些稳定思想，再重组节点：

- 拆分 A/B/C 边界
- LLM 只做推理
- code 负责清洗、断言、组装
- http-request 负责后端交互
- 门禁前移
- 证据留痕
