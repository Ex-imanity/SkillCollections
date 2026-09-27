# Dify DSL 节点与字段参考

只在需要字段级模板、节点选型或排查变量/连线错误时读取本文件。

## 1. 通用骨架

```yaml
app:
  description: 工作流描述
  icon: 🤖
  icon_background: '#FFEAD5'
  mode: workflow
  name: 工作流名称
  use_icon_as_answer_icon: false

dependencies: []

kind: app
version: 0.5.0

workflow:
  conversation_variables: []
  environment_variables: []
  features:
    file_upload:
      enabled: false
    opening_statement: ''
    retriever_resource:
      enabled: false
    sensitive_word_avoidance:
      enabled: false
    speech_to_text:
      enabled: false
    suggested_questions: []
    suggested_questions_after_answer:
      enabled: false
    text_to_speech:
      enabled: false
  graph:
    nodes: []
    edges: []
```

## 2. Repo 已验证节点

这些节点已在 `/opt/casegenerator/dify/*.yml` 中出现并验证过。

### Start

```yaml
- data:
    desc: ''
    title: 开始
    type: start
    variables:
    - label: query
      required: true
      type: paragraph
      variable: query
  id: start
  position: {x: 80, y: 280}
  type: custom
```

常见变量类型：

- `paragraph`
- `text-input`
- `select`
- `number`
- `file`
- `files`
- `object`

### Webhook Trigger

当前仓库在 `dify/webhook/TCG_gate.yml` 中出现了 webhook 触发 workflow。推荐做法：

- 先在 Dify UI 配置 webhook 触发器
- 导出 DSL 后再精修
- 输入路径通常会落在 `query_params.*`、`header_params.*`、`req_body_params.*`、`payload._webhook_raw`

### LLM

```yaml
- data:
    context:
      enabled: false
      variable_selector: []
    model:
      completion_params:
        temperature: 0.2
      mode: chat
      name: your-model
      provider: your-provider
    prompt_template:
    - id: s1
      role: system
      text: 仅输出结构化结果
    - id: u1
      role: user
      text: '{{#some_node.body#}}'
    structured_output_enabled: true
    structured_output:
      schema:
        type: object
        additionalProperties: false
        properties:
          ok: {type: boolean}
        required: [ok]
    title: 生成结果
    type: llm
    vision:
      enabled: false
      configs:
        detail: high
        variable_selector: []
  id: llm_result
  position: {x: 420, y: 280}
  type: custom
```

关键规则：

- `provider` 和 `name` 必须与实例里真实可选模型一致
- 需要机器消费时启用 `structured_output`
- 视觉场景保留 `vision.configs` 完整结构

### Code

```yaml
- data:
    code: |
      def main(text: str = "") -> dict:
          return {"clean_text": text.strip()}
    code_language: python3
    outputs:
      clean_text:
        type: string
    title: 清洗输出
    type: code
    variables:
    - value_selector: [llm_result, text]
      variable: text
  id: clean_output
  position: {x: 740, y: 280}
  type: custom
```

适合：

- 清洗 LLM 输出
- 校验门禁
- 构造 HTTP payload
- 解析 `structured_output`
- 汇总 iteration 输出

不要用它伪造 `file` 类型输出。

### HTTP Request

```yaml
- data:
    authorization:
      config: null
      type: no-auth
    body:
      data: '{"jobId":"{{#start.job_id#}}"}'
      type: json
    headers: 'X-Casegen-Api-Key: {{#start.api_key#}}'
    method: post
    timeout:
      max_connect_timeout: 0
      max_read_timeout: 0
      max_write_timeout: 0
    title: 调后端接口
    type: http-request
    url: '{{#normalize_backend.backend_url#}}/jobs/run'
  id: call_backend
  position: {x: 1060, y: 280}
  type: custom
```

关键规则：

- 二进制响应才会生成可供 vision 使用的 `files`
- JSON body 里的 `files` 不会自动变成节点输出 `files`
- headers 中 `:` 后建议保留空格

### If-Else

```yaml
- data:
    cases:
    - case_id: case_true
      conditions:
      - comparison_operator: is
        id: cond_ok
        value: 'true'
        variable_selector: [analyze_result, ok]
      id: case_true
      logical_operator: and
    logical_operator: or
    title: 门禁通过?
    type: if-else
  id: if_ok
  position: {x: 1380, y: 280}
  type: custom
```

常见比较：

- `is`
- `is not`
- `contains`
- `not contains`
- `empty`
- `not empty`
- `>`
- `<`
- `>=`
- `<=`

### End

workflow 模式优先用 `end` 返回结构化结果。

```yaml
- data:
    title: 输出
    type: end
    variables: []
    outputs:
    - value_selector: [clean_output, clean_text]
      value_type: string
      variable: result
  id: end
  position: {x: 1700, y: 280}
  type: custom
```

### Answer

chatflow 模式优先用 `answer` 返回文本。

```yaml
- data:
    answer: |
      {{#llm_result.text#}}
    title: 直接回复
    type: answer
    variables: []
  id: answer
  position: {x: 1700, y: 280}
  type: custom
```

### Iteration

```yaml
- data:
    error_handle_mode: terminated
    flatten_output: true
    is_parallel: false
    iterator_input_type: array[object]
    iterator_selector: [build_items, items]
    output_selector: [iter_finalize, iter_result]
    output_type: array[object]
    parallel_nums: 2
    start_node_id: iter_start
    title: 批量执行
    type: iteration
  id: item_iter
  position: {x: 1820, y: 220}
  type: custom
```

### Iteration Start

```yaml
- data:
    desc: ''
    isInIteration: true
    title: ''
    type: iteration-start
  id: iter_start
  parentId: item_iter
  position: {x: 24, y: 68}
  type: custom-iteration-start
```

迭代内节点要求：

- `isInIteration: true`
- `iteration_id: <iteration node id>`
- edge 也要带 `isInIteration: true`

## 3. 原 skill 未覆盖完整的辅助节点

这些节点不是当前仓库主流程的核心，但生成 DSL 时可能会用到。若用户明确需要，优先先看目标实例导出的样例再手写。

### Tool

适合调用 builtin、plugin、api 工具。适用场景：

- Dify marketplace 插件
- 搜索、文件转换、第三方工具桥接

```yaml
- data:
    provider_id: builtin
    provider_name: builtin
    provider_type: builtin
    tool_label: 工具
    tool_name: tool_name
    tool_configurations: {}
    tool_parameters:
      query:
        type: mixed
        value: '{{#start.query#}}'
    title: 工具调用
    type: tool
  id: tool_call
  position: {x: 420, y: 420}
  type: custom
```

### Variable Aggregator

适合聚合多分支输出，但动态批处理优先用 `iteration`。

### Parameter Extractor

适合从自然语言抽取参数。若输出需要强约束 JSON，通常直接用 `llm + structured_output` 更稳。

### Knowledge Retrieval

适合接知识库检索资源。若用户明确要求 RAG，优先确认实例里知识库节点的导出格式，再手写 DSL。

### Template Transform

适合做轻量模板拼接或格式转换。若转换规则复杂，优先改用 `code`。

### Question Classifier

适合基于用户问题做多路分类。若规则简单，优先改用 `if-else`；若分类依赖语义，考虑 `llm + structured_output`。

### Assigner / Variable Assigner

适合简单赋值、默认值回填、变量桥接。若涉及复杂逻辑，优先用 `code`。

### Document Extractor / List Operator

这类节点在当前仓库未验证。只有当用户明确指定且你已拿到目标实例导出的 DSL 样本时再手写；否则先说明“未验证，需要以实例导出为准”。

## 4. 依赖声明

常见依赖：

```yaml
dependencies:
- type: package
  value:
    plugin_unique_identifier: langgenius/openai_api_compatible
```

如果用到 marketplace/plugin 工具，必须声明对应依赖。

## 5. Edges

```yaml
edges:
- data:
    isInIteration: false
    isInLoop: false
    sourceType: start
    targetType: llm
  id: start-source-llm_result-target
  source: start
  sourceHandle: source
  target: llm_result
  targetHandle: target
  type: custom
```

检查点：

- `sourceType` / `targetType` 与节点 `data.type` 一致
- 迭代内 edge 必须标注 `isInIteration: true`
- 阻断分支与成功分支都能收口

## 6. 变量引用

常用格式：

- `{{#node.var#}}`
- `{{#llm_node.text#}}`
- `{{#llm_node.structured_output#}}`
- `{{#http_node.body#}}`
- `{{#http_node.files#}}`
- `{{#iteration_node.output#}}`

不要写成 `{{node.var}}`。
