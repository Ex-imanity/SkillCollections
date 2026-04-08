---
name: case-lite
description: 小需求测试用例生成 skill。用户提供飞书文档链接 → 浏览并手动选择章节 → 生成场景结构 → 生成完整用例 → 写回搬山。不含模块拆分和自动选章，适用于单一功能点的小需求。当用户说"小需求用例"、"简单需求生成用例"、"case-lite"，或明确只有 1-2 篇文档且无需模块拆分时触发。
---

# case-lite：小需求用例生成

## 定位

面向**单一功能点的小需求**，核心理念是**精准输入**：用户自己选择相关章节，避免读入无关信息影响判断和浪费 token。

- 无模块拆分、无自动选章、无质量门禁
- 用户主导章节选择，AI 专注生成
- 可独立分发，不依赖 skills-migration 其他模块

## 环境要求

**进入 Step 1 之前，必须先检查以下 MCP 工具是否可用。** 如果不可用，引导用户安装后再继续。

### 飞书文档工具（必需）

尝试调用 `parse_document_id` 或 `extract_document_structure`。如果工具不存在，提示用户在 Claude Code MCP 配置中添加：

```json
{
  "mcpServers": {
    "feishu-docx-blocks": {
      "command": "uvx",
      "args": ["feishu-docx-blocks@latest"],
      "env": {
        "FEISHU_APP_ID": "<你的飞书应用 App ID>",
        "FEISHU_APP_SECRET": "<你的飞书应用 App Secret>"
      }
    }
  }
}
```

> 飞书应用需要开通 `docx:document:readonly` 和 `wiki:wiki:readonly` 权限。

### 搬山测试平台工具（推荐）

尝试调用 `testCaseDetail`。如果工具不存在，提示用户添加：

```json
{
  "mcpServers": {
    "Banshan": {
      "type": "streamable-http",
      "url": "https://tech.baijia.com/mcp-server/banshan/mcp"
    }
  }
}
```

> 搬山 MCP 用于获取参考用例（Step 3a）。写回功能由内置脚本直接调用 HTTP 完成，不依赖此配置。
> 如果用户无法安装，Step 3a 的参考用例获取降级为手动粘贴 markdown，其余流程不受影响。

## 产物目录

```
case-lite-output/{slug}/
├── chapters/
│   └── {docKey}-chapters.md    ← 章节树展示（供用户选章）
├── corpus/
│   └── selected-corpus.md      ← 用户选定章节的拼接语料
├── style-ref/                  ← 可选
│   └── reference-cases.md      ← 用户提供的参考用例
├── structure.md                ← 场景结构（用户审核）
├── full.md                     ← 完整用例（用户审核）
└── writeback/
    ├── node-tree.json          ← writeback.py 生成的节点树
    └── writeback-log.json      ← 写回日志
```

`slug` 由需求名称生成，如 `ai-audit-model`。

---

## 执行流程

### Step 1：收集输入

从用户消息中提取：

1. **需求名称**（必须）→ 用于生成 slug 和产物目录
2. **文档链接**（必须）→ 飞书文档 URL 列表
3. **文档类型标签**（可选）→ 需求 / 前端 / 后端 / 客户端 / 算法

引导话术：

```
请提供以下信息：
1. 需求名称（如：AI审核模型变更）
2. 相关文档链接（飞书链接，可多个）
3. 文档类型（可选，如：需求文档、后端技术方案等）

示例：
- 需求名称：AI审核模型变更
- 后端技术方案：https://xxx.feishu.cn/docx/TOKEN1
- 需求文档：https://xxx.feishu.cn/wiki/TOKEN2
```

收到后创建产物目录 `case-lite-output/{slug}/`。

### Step 2：章节浏览与选择 [HITL]

对每个文档依次执行：

1. **解析文档 ID**：调用 `parse_document_id(url)` 获取 document_id
2. **获取章节树**：调用 `extract_document_structure(document_id, max_level=4, output_format="json")`
3. **格式化展示**：将章节树转为用户友好的编号列表

展示格式示例：

```markdown
## 📄 UOS 相关需求 后端反讲（后端文档）

1. 一、变更历史
2. 二、背景
   2.1 需求
   2.2 关联方
3. 三、整体设计
   3.1 Apollo 新增/变更配置
      3.1.1 新增模型连接配置
      3.1.2 变更业务模型路由配置
   3.2 需求六（账号类型字段）
4. 四、详细设计
   4.1 AI审核模型变更
      4.1.1 整体流程图
      4.1.2 核心实现
      4.1.3 关键设计检查
```

4. **保存章节树**：写入 `chapters/{docKey}-chapters.md`

5. **引导用户选章**：

```
请选择需要纳入用例生成的章节（可多选）：

选择方式：
- 按编号：3, 4.1, 4.2（支持整章或子章节）
- 按关键词：整体设计, AI审核
- 混合：3, "核心实现"

输入 "全选" 选择该文档所有章节。
多个文档请分别选择。
```

6. **记录选择**：保存用户选定的章节及其 position range（从 extract_document_structure 的 JSON 结果中获取）

> **飞书工具详细用法**：见 [references/feishu-tools-guide.md](references/feishu-tools-guide.md)

7. **收集补充信息**（可选，不阻塞）：

```
已选定的文档章节会作为用例生成的主要依据。

是否还有补充信息需要纳入？例如：
- TAPD/Jira 上的需求描述或验收标准
- 产品口头沟通的额外规则或约束
- 接口文档、字段说明等技术细节
- 其他背景信息

可以直接粘贴文本，也可以回复"没有了"继续。
```

如果用户提供了补充信息，保存到 `corpus/extra-context.md`，在后续 Step 3 生成时与选定语料一同作为输入。

### Step 3：生成场景结构 [HITL]

#### 3a. 收集参考用例（可选，不阻塞）

```
是否有可以参考的优秀用例？（用于学习风格和覆盖度）
- 输入搬山用例 ID（如：20612）
- 粘贴 markdown 格式的用例片段
- 回复"跳过"使用默认风格
```

- 搬山 caseId → 调用 `testCaseDetail(caseId)` 获取，保存到 `style-ref/reference-cases.md`
- markdown 片段 → 直接保存到 `style-ref/reference-cases.md`
- 跳过 → 使用内置 [assets/case-learning.md](assets/case-learning.md) 默认风格规则

#### 3b. 拉取选定语料

对每个选定章节，按以下两步拉取完整内容（文本 + 媒体）：

**Step 3b-1：拉取文本和媒体元数据**
```
get_document_blocks(document_id, start_position=X, end_position=Y)
```
返回章节的文本内容和媒体元数据。**注意：图片/画板只返回 block_id 和 token，不包含实际图片。**

**Step 3b-2：下载图片**（如果上一步返回了图片元数据）
```
download_image_blocks(document_id, image_block_ids=["block_id_1", "block_id_2"])
```
将实际图片下载到本地，返回可视化的图片内容。

如果章节包含画板（流程图、架构图等），额外调用：
```
download_board_as_image(board_tokens=["token_1"], document_id=document_id, board_block_ids=["block_id_1"])
```

将所有选定章节内容拼接为 `corpus/selected-corpus.md`，格式：
```markdown
<!-- SOURCE: {docKey} | {section_title} | pos:{start}-{end} -->
{章节文本内容}
[📷 图片: {image_description_or_context}]
<!-- END SOURCE -->
```

> **关键**：文档中的流程图、接口说明图、交互稿等视觉信息对用例生成至关重要。
> 如果跳过图片下载，生成的用例可能遗漏图中描述的分支逻辑和交互细节。

#### 3c. 生成场景结构

基于以下输入生成 `structure.md`：
- 选定语料（`selected-corpus.md`）
- 补充信息（`extra-context.md`，如有）
- 风格参考（参考用例或默认规则）
- 需求名称

**生成 prompt 要点**：
- 按功能/流程拆分场景
- 每个场景列出测试点，标注优先级（P0/P1/P2）
- 覆盖维度：正常流程、异常处理、边界值、安全/权限
- 命名格式：操作对象 + 操作 + 结果/场景（不用"验证"/"测试"前缀）

生成后输出 `structure.md` 并请用户审核：

```
场景结构已生成，请审核：
[展示 structure.md 内容]

请确认或提出修改意见。确认后将生成完整用例。
```

### Step 4：生成完整用例 [HITL]

基于已审核的 `structure.md` + `selected-corpus.md` 生成 `full.md`。

**生成 prompt 要点**：
- 严格按照 structure.md 的场景和测试点展开
- 每个测试点只包含：执行步骤、预期结果（**不生成"前置条件"section**）
- 如有前置条件，将其精简后融入执行步骤的第一步（如"1. 已登录管理后台，进入XX页面"）
- 执行步骤精确到字段名/按钮名/接口路径
- 预期结果多层验证（UI/交互/接口/数据层），断言可量化
- 不扩写 structure.md 中没有的场景
- 即使参考用例中包含"前置条件"节点，也不要模仿，一律融入执行步骤

生成后输出 `full.md` 并请用户审核：

```
完整用例已生成，请审核：
[展示 full.md 内容或告知文件路径]

确认无误后，可输入搬山用例 ID 进行回填。
```

### Step 5：回填搬山 [HITL]

> **建议**：本步骤为纯机械操作，优先使用 `writeback.py` 脚本完成全部处理（解析 → 写入 → 验证），避免 LLM 读取 full.md 浪费 token。
> 如果脚本执行失败，允许 agent 读取 full.md 排查原因并修复格式问题后重试。

1. **收集 caseId**：
   ```
   请提供搬山用例 ID（caseId），用于写回搬山平台。
   如还未创建用例，请先在搬山创建后提供 ID。
   ```

2. **定位 writeback.py**：在本 skill 安装目录的 `scripts/writeback.py`。用 Glob 查找：
   ```
   Glob("**/case-lite/scripts/writeback.py")
   ```

3. **dry-run 验证**（**必须先执行，不可跳过**）：
   ```bash
   python {writeback.py路径} case-lite-output/{slug}/full.md \
     --case-id {caseId} --dry-run
   ```
   脚本会执行以下检查：
   - 格式验证：检测未被识别的 `##` / `###` 标题（格式漂移）
   - 数量校验：对比 markdown 原文与解析出的场景/测试点数
   - 完整性检查：检测无执行步骤的测试点
   
   **如果有 ⚠ 警告，必须先修复 full.md 再写回。** 不要带警告强行写入。
   展示场景概览和节点数给用户确认。

4. **用户确认后，执行写回**：
   ```bash
   python {writeback.py路径} case-lite-output/{slug}/full.md \
     --case-id {caseId} --modifier case-lite
   ```
   脚本自动完成：
   - 重复写入检测：若 caseId 已有 AI 节点则提醒并中止，请用户先在搬山平台清空用例后重试
   - 解析 markdown → 构建节点树 → 调用搬山 batchAddNode → testCaseDetail 验证
   
   agent 只需读取终端输出摘要并告知用户结果。

5. **产物**：
   - `writeback/node-tree.json` — 节点树 JSON
   - `writeback/writeback-log.json` — 写回日志

脚本源码：[scripts/writeback.py](scripts/writeback.py)。零外部依赖，纯 Python 标准库。
MCP 端点可通过环境变量 `BANSHAN_MCP_ENDPOINT` 覆盖。

---

## structure.md 格式规范

```markdown
### 场景1：场景标题
  - 测试点1.1：测试点标题（P0）
  - 测试点1.2：测试点标题（P1）

### 场景2：场景标题
  - 测试点2.1：测试点标题（P0）
  - 测试点2.2：测试点标题（P2）
```

## full.md 格式规范

```markdown
## 场景1：场景标题

### 测试点1.1：测试点标题

#### 执行步骤
1. 前置：已登录XX系统，进入XX页面（前置条件融入第一步）
2. 操作步骤（精确到字段/按钮/接口级）

#### 预期结果
1. 期望结果（可量化断言）
```

- 场景：`## 场景N：标题`
- 测试点：`### 测试点N.M：标题`
- 执行步骤 / 预期结果：`####` 级标题 + 编号列表
- **不生成 `**前置条件**` section**，前置条件融入执行步骤第一步

### full.md 写回解析约束（必须严格遵守）

`writeback.py` 用正则逐行解析 full.md，以下格式偏差会导致节点丢失：

| 规则 | 正确 | 错误（会被跳过） |
|------|------|-----------------|
| 场景标题用 `##` + 阿拉伯数字 | `## 场景1：标题` | `## 场景一：标题`、`## 1. 标题` |
| 测试点用 `###` + N.M 编号 | `### 测试点1.1：标题` | `### 1.1 标题`、`### 测试点1：标题` |
| 冒号分隔（半角或全角均可） | `场景1：标题` 或 `场景1:标题` | `场景1 标题`（无冒号） |
| 步骤/结果标题用 `####` | `#### 执行步骤` | `### 执行步骤`、`**执行步骤**` |
| 步骤/结果内容用编号列表 | `1. 操作内容` | `- 操作内容`（步骤不支持 `-`） |
| 每个测试点必须有执行步骤 | 先 `#### 执行步骤` 再 `#### 预期结果` | 只有预期结果无执行步骤（结果会被丢弃） |
| 测试点之间不用分割线 | 直接换行进入下一个 `###` | `---` 分割线可能干扰解析 |
| 不生成前置条件 section | 将前置条件融入执行步骤第一步 | `**前置条件**` 内容会被解析器跳过，不写入搬山 |

> 生成 full.md 时务必逐项检查上述格式。如果 `writeback.py --dry-run` 输出的场景/测试点数与 full.md 不符，说明存在格式问题。

---

## 工具依赖

| 工具 | 用途 | 阶段 | 必需 |
|------|------|------|------|
| feishu-docx-blocks MCP | 文档解析、章节获取、语料拉取 | Step 2, 3 | 是 |
| Banshan MCP | 通过 caseId 获取参考用例 | Step 3a | 推荐（可降级） |
| scripts/writeback.py | full.md 解析 + 节点树构建 + HTTP 写回搬山 | Step 5 | 内置，无需安装 |

## 风格规则

详见 [assets/case-learning.md](assets/case-learning.md)。
