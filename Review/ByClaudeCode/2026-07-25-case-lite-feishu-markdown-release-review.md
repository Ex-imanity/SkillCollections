# Cross-Agent Review - case-lite-feishu-markdown-release-20260725

Reviewer: ClaudeCode
Gate: `case-lite-feishu-markdown-release-20260725`
Reviewer session: `98fc62e3-2d2e-43dc-a2c5-4c0d699e6e03`
Reported cost USD: `1.56871475`

## Review

Review complete. Verdict below (evidence-cited, Chinese as required).

---

## 独立评审结论：`APPROVE WITH NITS`（同意，附小问题）

3.4.0 候选**可以发布**。核心的"精准输入"边界在代码层被强制执行，并被单测 + 实机验证覆盖；所有发现均为文档一致性 / 可选健壮性，**无 P0–P2 阻断项**。

### 逐问回答

**Q1 元数据优先、仅选中内容第二步，是否无泄漏？** 是。
- 默认 `preview_chars=0`（`get_markdown_file_sections.py:60-66`），`_index_section` 仅在 `preview_chars>0` 时才加 `preview`（`:300-310`）；目录模式只返回 `id/title/level/section_path/range`。
- 正文仅在 `section_ids` 分支经 `_selected_section` 返回（`:182-191, 312-315`）；`full_content` 仅在"无标题 + 显式 `include_full_content=true`"时返回（`:132-144`）。
- 单测证据：`Test/test_markdown_file_sections.py:70`（默认无 preview）、`:74-83`（preview 仅显式）、`:143-156`（无标题全文需显式）。

**Q2 URL 路由 / 标题范围 / 父子去重 / Docx 回退？** 均正确。
- `/wiki/TOKEN` 经 `get_wiki_node` 校验 `obj_type=="file"`，非 file 明确拒绝且**不下载**（`:209-243`；单测 `:124-140`）。
- 围栏感知 ATX 解析、层级 ID、行范围（`:245-298`；单测 `:49-70`）。
- `_deduplicate_selected` 按行范围包含关系剔除被父章节覆盖的子章节，防语料重复（`:317-331`）。
- Docx 隔离：`download_file` 走 `/drive/v1/files/:token/download` 与 `download_media` 分离（`feishu_client.py:452-471`）；Skill 禁止对原生 Markdown 走 Docx 工具链（`SKILL.md:202`）。

**Q3 OAuth / token？** 正确。
- `99991668/99991677` 判为无效（`auto_auth.py:402-404, 420-421`；单测 `:238-261`）。
- `.env` 未预加载恢复：`TokenManager.load_tokens` 缺 env 时直读 `.env`（`token_manager.py:46-66`）；`mcp_server.py:73-102` 用缓存 `refresh_token` 刷新（单测 `:197-220`）。

**Q4 文档/测试一致性？** 基本一致，两处文档描述陈旧（P3-1/P3-2）；两处逻辑缺直接单测（P3-3）。

**Q5 是否可发布？** 可以，边界代码层强制且实机验证通过。

### 发现（按严重度）

- **P0/P1/P2：无。**
- **P3-1（model-facing 文档）** `get_markdown_file_sections.py:35` 描述称"不传 `section_ids` 时返回目录**和原文预览**"，与实际默认（`preview_chars=0`，无预览）矛盾。该描述即模型可见契约，建议改为"默认仅目录元数据，预览需显式开启"。无实际泄漏。
- **P3-2（文档）** `docs/plans/2026-07-25-case-lite-feishu-drive-markdown.md` 的 Tool contract 写 `preview_chars` 默认 **300** 且把 `preview` 列为常规索引字段，与实现（默认 0、可选）不符。实现是正确版本,应更新计划文档。
- **P3-3（测试缺口，非阻断）** 缺 `_deduplicate_selected` 父子去重、以及 `section_ids` 缺失 ID 分支的直接单测。
- **P3-4（可选健壮性）** `download_file` 未校验 `content-type`；非 Markdown 但合法 UTF-8 的 Drive 文件会被当作无标题文本（只读、非破坏性，可接受）。

### 测试局限
只读评审未复跑测试，依赖主评审记录（MCP 17 passed / case-lite 24 passed / `uv build` + `twine check` + 洁净 venv 注册工具 / 实机 38 章节仅元数据 + 选中返回 35,595 字符）。实机仅单文件；多文件混合、超大文件、非 UTF-8 未压测。

### 下一步
1. 发布 3.4.0（不阻断）。2. 修正 P3-1/P3-2 对齐"默认仅元数据"。3. 补 P3-3 单测。4. 由 Codex 收口发布。

完整报告已写入评审计划文件。我未编辑任何代码、未运行写操作、未改动任务状态或调用其他评审者。
