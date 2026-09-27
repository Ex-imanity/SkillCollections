# 飞书 MCP 工具使用指南

本文件供 case-lite skill 在 Step 2（章节浏览）和 Step 3（语料拉取）阶段参考。

## 0. 原生云空间 Markdown 文件

原生 Markdown 是飞书云空间中的 `.md` **文件/附件**，不是 Docx。支持直接 `/file/TOKEN`，以及最终对象类型为 `file` 的 `/wiki/TOKEN`：

```
get_markdown_file_sections(
  url = "https://xxx.feishu.cn/file/TOKEN",
  max_level = 4,
  preview_chars = 0
)
```

首轮只返回 `sections` 的 `id`、`title`、`level`、`section_path`、`range.start_line/end_line`，不返回正文或预览。标题仅解析代码围栏外的 ATX 标题（`#` 至 `######`）。只有用户明确要求在选章前查看少量上下文时，才设置正数 `preview_chars`。

用户选章后，按 ID 一次取得原始 Markdown：

```
get_markdown_file_sections(
  url = "https://xxx.feishu.cn/wiki/TOKEN",
  section_ids = ["1", "2.1"]
)
```

- `selected_sections[].content` 必须原样写入语料，不得摘要或改写。
- 选中的父章节会包含其子章节；工具会去重重叠范围。
- 如果 Wiki 的最终对象不是 `file`，工具会明确返回“不是原生飞书 Markdown 文件”；此时才转到下方 Docx 流程。
- 该工具只读，要求 `drive:file:download` 授权。
- 不下载图片或画板：Markdown 中的媒体引用作为原始 Markdown 文本保留。

无标题的短 Markdown 在用户确认后可使用 `include_full_content=true` 读取全文；长文件应要求用户补充范围或跳过，避免无边界地把全文加入语料。

## 1. 发现 wiki/docx-in-wiki 子文档

在解析正文前，先用 `get_child_documents` 检查用户给出的飞书链接是否是知识库节点，或是否属于知识库节点树。

```
get_child_documents(
  url = "https://xxx.feishu.cn/wiki/TOKEN",
  fetch_all = true,
  include_non_docx = false
)
```

参数要点：
- `url`：支持 `/wiki/TOKEN` 和位于知识库中的 `/docx/TOKEN`
- `fetch_all=true`：拉取所有分页，避免漏掉同级子文档
- `include_non_docx=false`：case-lite 只读取可解析为文档正文的 docx 子文档，跳过 sheet/file/bitable 等非文档节点

返回内容：
- `parent`：父节点信息
- `children`：直接子节点列表，每项包含 `title`、`url`、`node_token`、`obj_token`、`obj_type`、`has_child`
- `parse_hint.document_id`：当子节点为 docx 时，后续可作为 document_id 使用

递归规则：
1. 对用户原始链接调用 `get_child_documents(fetch_all=true, include_non_docx=false)`
2. 对返回中 `has_child == true` 的子文档继续调用同一工具
3. 使用 `node_token` 去重；没有 `node_token` 时用 `url` 去重，避免循环
4. 本阶段只收集标题、链接、类型等元数据，不读取正文
5. 将发现树展示给用户，等待用户确认纳入后，再把入选子文档加入 Step 2 文档列表

普通 docx 如果不在知识库节点树中，工具会返回成功但 `children=[]`，可直接继续处理该文档本身。

## 2. 解析文档链接 → document_id（仅 Docx）

用户提供的飞书链接通常有两种格式：

| 类型 | URL 格式 | 说明 |
|------|---------|------|
| docx | `https://xxx.feishu.cn/docx/TOKEN` | 直接从 URL 提取 TOKEN 即为 document_id |
| wiki | `https://xxx.feishu.cn/wiki/TOKEN` | 需要 API 转换，TOKEN 是 wiki node token |

**统一用 `parse_document_id` 处理**：

```
parse_document_id(url="https://xxx.feishu.cn/wiki/TOKEN")
→ { "success": true, "document_id": "实际docId", "url_type": "wiki" }
```

如果 `parse_document_id` 对 wiki 链接失败，备用方案：
```
wiki_v2_space_getNode(query={ token: "TOKEN" })
→ 从返回的 obj_token 获取 document_id
```

## 3. 获取章节结构（标题树，仅 Docx）

**用 `extract_document_structure`**，这是最轻量的方式，只返回标题层级：

```
extract_document_structure(
  document_id = "docId",
  max_level = 4,           # H1-H4 全部提取
  output_format = "json"   # 返回结构化 JSON，便于程序处理
)
```

返回内容包含：
- `heading_tree`：嵌套的标题树结构
- `flat_headings`：扁平的标题列表，每项有：
  - `text`：标题文本
  - `level`：层级（1-4）
  - `position`：在文档中的位置索引（0-based）
  - `block_id`：块 ID

**关键**：`position` 用于后续 `get_document_blocks` 的 range 参数。

如果需要同时获取章节预览内容（如判断章节是否相关），可用 `get_document_section_digests`：
```
get_document_section_digests(
  document_id = "docId",
  max_level = 3,
  include_preview = true,    # 包含截断预览文本
  preview_chars = 300
)
```

返回每个章节的 `range`（start_position / end_position）和 `preview` 文本。

## 4. 精准拉取章节内容（仅 Docx）

用户选章后，按 position range 拉取指定章节的完整内容：

```
get_document_blocks(
  document_id = "docId",
  start_position = 45,      # 章节起始位置（inclusive）
  end_position = 120         # 章节结束位置（inclusive）
)
```

**重要**：
- `start_position` 和 `end_position` 来自 `extract_document_structure` 或 `get_document_section_digests` 的输出
- 这种方式只拉取选定范围的 blocks，不会加载整个文档，**节省 token**
- 返回的内容包含文本、表格、代码块等结构化信息
- **图片和画板只返回元数据（block_id、token），不包含实际图片文件**

### 3.1 下载图片（必须配合 get_document_blocks 使用）

`get_document_blocks` 返回的"图表元数据信息"中会列出图片的 block_id。需要额外调用：

```
download_image_blocks(
  document_id = "docId",
  image_block_ids = ["block_id_1", "block_id_2"],
  include_context = true     # 返回图片所属章节和前后文本
)
```

返回：实际图片文件（base64 ImageContent）+ 上下文信息（section_path、context_before/after）。

### 3.2 下载画板（流程图、架构图等）

如果章节包含画板类型的 block：

```
download_board_as_image(
  board_tokens = ["HCXEwkQOmh6CpEbVfRccAC1SnHd"],
  document_id = "docId",
  board_block_ids = ["block_id_1"]
)
```

画板会被导出为 PNG 图片。

> **完整拉取流程**：`get_document_blocks` → 检查返回的图片/画板元数据 → 如有，调 `download_image_blocks` / `download_board_as_image` → 合并到语料中

## 5. 章节 position range 的确定（仅 Docx）

`extract_document_structure` 返回的 `flat_headings` 中每个标题有 `position`，但**不直接包含 end_position**。

确定一个章节的 range 的方法：
- **start_position** = 当前标题的 `position`
- **end_position** = 下一个同级或更高级标题的 `position - 1`；如果是最后一个章节，则为文档末尾

建议改用 `get_document_section_digests`，它直接返回每个章节的 `range.start_position` 和 `range.end_position`，无需手动计算。

**推荐流程**：
1. 先用 `extract_document_structure` 展示标题树（轻量、快速）
2. 用户选章后，用 `get_document_section_digests` 获取选定章节的精确 range
3. 用 `get_document_blocks(start_position, end_position)` 拉取内容

## 6. 关键词搜索（补充手段，仅 Docx）

如果用户通过关键词选章，可用 `search_document_content` 辅助定位：

```
search_document_content(
  document_id = "docId",
  keywords = ["AI审核", "模型变更"],
  merge_by_heading = true    # 合并同一章节下的多个匹配
)
```

返回每个匹配项的标题层级上下文（H1/H2/H3/H4）和建议的读取范围。

## 7. 常见问题

**Q: wiki 链接获取 document_id 失败？**
→ 使用 `wiki_v2_space_getNode` 备用方案

**Q: 文档超过 500 个 blocks？**
→ 不要用 `fetch_all=true` 全量获取，坚持用 `start_position/end_position` 按需拉取

**Q: 章节内有嵌入的电子表格？**
→ 用 `get_sheet_content(spreadsheet_token)` 获取表格数据，token 从 blocks 的元数据中获取
