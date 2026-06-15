# Findings

<!-- Append research notes and discoveries below this line. -->

## 2026-05-19 — Session 分析：case-lite 实际表现问题

**数据来源**：  
Session `61a2bfdb` (`/Users/gaotu/.claude/projects/-Users-gaotu-Projects-testCases/`)，2026-05-19，5.5MB，最新一次 case-lite 完整执行记录。  
分析方式：grep 关键词 + Python 提取 assistant thinking。

---

### 问题1（P0）：corpus 阶段擅自改写/省略文档原文

**现象**：模型在 Step 3b 调用 `get_document_blocks` 拿到原始文本后，写入 `selected-corpus.md` 时对内容做了摘要式改写，把接口参数表格和 JSON 示例压缩成文字描述，而非逐字保留。

**Thinking 原文佐证**：
> "I chose to summarize it in the corpus file instead of preserving the verbatim blocks. I should update the document to include the full code blocks as they were returned."

**用户反馈**：直接指出"你为什么没有写入 selected-corpus.md（extData JSON串）？"，被迫发出纠正指令"语料文档生成阶段不允许省略和改写"后才触发重新生成。

**根因**：SKILL.md Step 3b 只说"将所有选定章节内容拼接为 selected-corpus.md"，没有**明确禁止**改写/摘要，模型自主启动 token 压缩行为。

**修复**：在 Step 3b 加硬性约束块，明确"原文写入，禁止摘要/精简/改写"。

---

### 问题2（P1）：corpus 落盘时机晚，无中间检查点

**现象**：`selected-corpus.md` 在所有章节全部拉取完、补充信息也收集完之后才一次性写入，而不是每章拉取后立即追加落盘。

**影响**：  
1. 多章节拉取中途失败时，所有内容丢失，无断点续跑能力  
2. 模型在内存中"持有"多章节内容，等到写盘时更容易做二次处理（加剧问题1）

**修复**：Step 3b 改为每完成一个章节的 `get_document_blocks` 调用后**立即追加写入** `selected-corpus.md`。

---

### 问题3（P1）：图片下载与 corpus 关联逻辑不完整

**现象**：SKILL.md Step 3b 描述了调用 `download_image_blocks`，但未说明：  
1. 下载失败时如何处理  
2. 下载成功后图片内容如何写入 corpus

**影响**：实际执行中图片处理步骤被跳过或格式不一致。

**修复**：明确格式规范——成功插入 `[📷 图片: {上下文描述}]`，失败写 `[📷 图片下载失败: block_id={id}]`，不阻塞后续流程。

---

### 问题4（P2）：选章结果缺乏标准记录格式

**现象**：Step 2a 只说"记录选择：保存用户选定的章节及其 position range"，无落盘格式规定。

**影响**：Step 3b 依赖 position range 调用 `get_document_blocks`，缺乏标准格式导致恢复困难。

**修复**：在 `chapters/{docKey}-chapters.md` 末尾追加 `## 用户选章结果` section，每行格式：`- 章节标题 | pos:{start}-{end} | docKey:{docKey}`

---

### 问题5（P2）：Step 3b 与 Step 3c 边界缺失检查点

**现象**：3b（拉取语料）和 3c（生成场景结构）之间没有"corpus 已落盘"的显式检查点。

**影响**：模型可能在 corpus 未完整落盘的情况下直接进入 3c，生成质量依赖内存而非文件。

**修复**：3b 末尾插入检查点，要求确认 `corpus/selected-corpus.md` 存在且包含所有选章的 `<!-- SOURCE -->` 注释头。

---

### 优先级汇总

| # | 问题 | 优先级 | 修复难度 |
|---|------|--------|---------|
| 1 | corpus 改写/省略 | **P0** | 低（加约束文本） |
| 2 | corpus 落盘时机晚 | P1 | 中（改流程描述） |
| 3 | 图片落盘格式不完整 | P1 | 低（补格式规范） |
| 4 | 选章记录无标准格式 | P2 | 低（加格式规范） |
| 5 | 3b/3c 边界检查点缺失 | P2 | 低（加检查点描述） |

## 2026-05-29 — 写回脚本缺陷确认：执行步骤 bullet 被丢弃

**数据来源**：
- `/Users/gaotu/Projects/testCases/case-lite-output/gaokao-ai-qa-restriction/full.md`
- `/Users/gaotu/Projects/testCases/case-lite-output/gaokao-ai-qa-restriction/writeback/node-tree.json`
- `/Users/gaotu/.cc-switch/skills/case-lite/scripts/writeback.py`

---

### 问题6（P1）：执行步骤 section 中的无序列表 bullet 未写回

**现象**：`full.md` 的 `#### 执行步骤` 中存在编号步骤下的子 bullet，例如第 55 行“分别输入以下含敏感词提问并发送”后有 3 条 `- "..."` 子项。但生成的 `node-tree.json` 只保留了父编号步骤，子 bullet 未进入执行步骤节点。

**复现证据**：
- `full.md` 执行步骤区域共有 20 行 `- ` bullet
- 解析后的执行步骤文本中不包含 `- `，也不包含样本文案“今年高考有哪些采分点”“第一次：2026年6月8日10:00”

**根因**：`writeback.py` 第 138-142 行只收集 `re.match(r"^\d+\.", line)` 的编号步骤；执行步骤里的 `- ` 子列表命中 `continue` 后被静默跳过。相对地，第 144-148 行的预期结果解析同时支持编号列表和 `- ` bullet。

**影响**：包含“分别输入以下...”这类批量输入、参数枚举、分时段枚举的执行步骤会丢失关键测试数据，搬山节点呈现为不完整步骤。

**建议修复**：执行步骤解析与预期结果保持一致，支持 `- ` bullet；同时添加回归测试，确保编号步骤下的子 bullet 被保留。

## 2026-06-15 — 子文档发现能力接入 case-lite

**数据来源**：
- `/Users/gaotu/PycharmProjects/CaseMCP/FeishuMCP` 最新提交 `dfe7a9c5246cca569c49af9577a51d6fc4af19ea`
- `src/tools/document/get_child_documents.py`
- `Test/test_get_child_documents.py`

---

### 发现：feishu-docx-blocks 已支持 wiki/docx-in-wiki 直接子文档列表

新工具名为 `get_child_documents`，支持传入 wiki URL 或位于知识库中的 docx URL。返回 `parent`、`children`、`pagination`，其中 child 包含 `title`、`url`、`node_token`、`obj_token`、`obj_type`、`has_child`、`parse_hint`。

**关键能力**：
- `fetch_all=true` 可拉取所有分页
- `include_non_docx=false` 可只保留 docx 子文档
- 普通 docx 不在知识库节点树中时返回成功但 `children=[]`
- `has_child` 可用于递归继续展开更下级子文档

**case-lite 接入策略**：
- 在章节浏览前新增 Step 1a：对用户原始链接调用 `get_child_documents(fetch_all=true, include_non_docx=false)`
- 对 `has_child == true` 的子文档递归调用同工具，用 `node_token` 或 `url` 去重
- 只读取元数据，不读取正文；必须先展示给用户并等待用户确认纳入
- 用户确认的子文档默认继承父文档类型标签，作为同类文档进入 Step 2 章节浏览
