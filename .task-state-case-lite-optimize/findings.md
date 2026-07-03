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

## 2026-07-01 — 首次使用依赖安装与 MCP 配置优化设计

**数据来源**：
- 用户提供截图：标准化本地工作流分发，目标包括一键检查 uv/Python/MCP 配置、安装或更新 `feishu-docx-blocks`、检查 Banshan MCP 连通性、输出诊断报告
- 飞书文档 `Case-lite skill使用说明` 的“安装”章节（wiki token `CNBZwz8rwiew8dkXHt1cRIAAn8g`，docx token `SpPsdDalSo7CU4xop1pc8OjSnM9`）
- 用户确认点（2026-07-01）：主要面向 Claude Code 与 Codex；默认全局 MCP 配置但需征求用户同意；已有 `feishu-docx-blocks` 默认询问升级；Banshan URL 固定；飞书授权维持 `feishu-docx-blocks` 自身逻辑

---

### 发现：当前 case-lite 环境检查只提示安装，首次使用门槛仍高

当前 `case-lite/SKILL.md` 在进入 Step 1 前要求检查 feishu-docx-blocks 和 Banshan MCP 是否可用，但环境不满足时主要给出手动配置片段。对首次使用者来说，仍需要理解 Agent 类型、MCP 配置路径、uvx、全局/项目配置、飞书应用凭证、重启 MCP 等细节。

### 安装章节关键信息

- skill 安装方式：`/skill-install https://github.com/Ex-imanity/SkillCollections`、手动复制、或 cc-switch 技能仓库导入
- Claude Code MCP 配置：
  - 用户级配置存在新旧差异：新版默认 `~/.claude/.claude.json`，旧版 cc-switch 可能覆盖为 `~/.claude.json`
  - 项目级配置为项目根目录 `.mcp.json`
  - feishu-docx-blocks 推荐 `uvx feishu-docx-blocks@latest`
- Codex MCP 配置：
  - 全局配置在 `~/.codex/config.toml`
  - 可用 `codex mcp add feishu-docx-blocks --env ... -- uvx feishu-docx-blocks@latest`
- Banshan MCP 固定 URL：`https://tech.baijia.com/mcp-server/banshan/mcp`

### 已确认设计边界

- 目标 Agent：优先支持 Claude Code 与 Codex；其他 Agent 继续输出手动提示，不做自动配置
- 配置目标：默认全局 MCP 配置，但写入前必须询问用户意见
- 已有 `feishu-docx-blocks`：默认询问是否升级到 `@latest`，不静默覆盖
- 飞书授权：由 `feishu-docx-blocks` 现有逻辑负责，过期时会自动拉起浏览器授权；case-lite 不额外接管
- 凭证安全：`FEISHU_APP_ID` / `FEISHU_APP_SECRET` 不写入 skill 明文。默认值让用户去内部文档链接自行获取；脚本支持环境变量或交互输入，避免命令行参数和日志泄露 secret
- 渐进式披露：非首次使用不展示完整安装链路；仅当依赖缺失或版本不满足时加载安装文档/运行 setup 流程

### 建议实现形态

- `case-lite/SKILL.md`：保留轻量环境检查入口和“缺依赖时进入首次使用依赖向导”的决策流程
- `case-lite/references/install-mcp.md`：存放 Claude Code / Codex 手动配置、自动配置说明、风险与降级方案
- `case-lite/scripts/setup_mcp.py`：提供确定性诊断与可选修复能力：
  - `--check` 输出诊断报告
  - `--agent claude-code|codex`
  - `--target global`
  - `--fix` 在用户确认后写配置
  - 从环境变量或交互输入读取 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
  - 写配置前备份，merge 而不是覆盖

### Review 重点

- 是否存在明文 `FEISHU_APP_SECRET` 或默认凭证落入 skill / README / 测试快照
- 自动配置是否必须经过用户确认，尤其是全局配置写入
- Claude Code 配置路径是否兼容 `~/.claude/.claude.json` 与 `~/.claude.json`
- Codex TOML 写入是否 merge 而非破坏已有配置
- 已配置但缺 `get_child_documents` 或非 `@latest` 时，是否只建议/询问升级
- 普通 case-lite 流程是否仍保持轻量，不强制每次执行完整安装诊断

## 2026-07-01 — Phase 6 Review 复核结果（待 codex 复核）

**背景**：用户要求基于 MRS 与最新改动，review codex 已完成的 Phase 6（首次使用依赖安装 + MCP 自动配置）是否合理，重点关注 Claude Code MCP 配置路径问题。

**结论**：方向正确、落地扎实、无安全红线。已用飞书文档 `安装` 章节（docx `SpPsdDalSo7CU4xop1pc8OjSnM9`，H4 `ClaudeCode配置` position 20-30）核对：配置内容（`type:stdio`、env 结构、Codex `[mcp_servers.*.env]` 拆表、Banshan `Banshan`/`banshan` 大小写不对称）均忠实还原文档。凭证安全验证通过：全仓库 grep 不到真实 secret（`cli_a9ca99bc8778dcc1` / `drRCI...`），仓库为**公开** GitHub，不内嵌凭证的决策正确。

**发现与已实施修复（本次改动）**：

| # | 严重度 | 问题 | 修复 |
|---|--------|------|------|
| F1 | 高 | Claude Code 路径检测靠“哪个文件存在”静默猜测，与文档“需确认自己的路径”矛盾；旧 cc-switch 用户若两路径都存在会写到失效文件（静默失败），且零测试 | `detect_claude_code_config` 改为返回 `ClaudeCodeConfigChoice(path, candidates, ambiguous, note)`；两路径同存判为 ambiguous，报告列出候选 + cc-switch PR，`--fix --yes` 拒绝(exit 3)、交互让用户选或用 `--config` 指定；补 4 个路径检测测试 |
| F2 | 中 | `--fix` 无条件重写 feishu+Banshan，覆盖源码安装/自定义 feishu，违反“不静默覆盖”边界 | merge/apply 增加 `write_feishu`/`write_banshan` 开关；默认仅写缺失项，已有 feishu 默认保留，需 `--replace-feishu` 或交互确认才替换；写入前打印“将写入/将保留”摘要；补 no-clobber 测试 |
| F3 | 中 | 整体重写 `~/.claude.json`（含大量其它状态）有并发覆盖风险，备份含明文 secret | 改原子写（临时文件 + `os.replace`）；config 与备份 chmod 0o600；claude-code 写入前提示退出 CC；`install-mcp.md` 补充 `claude mcp add-json` 官方 CLI 方案；备份为空时不再生成空 `.bak` |
| F4 | 低/中 | 诊断只读环境变量，已配置用户会误报“未提供/需要补充” | 新增 `resolve_creds`：优先 env，其次读现有配置(`read_claude_code_creds`/`read_codex_creds`)；报告标注凭证来源；补读取测试 |
| F5 | 低 | 路径检测/凭证读取无测试；`test_report_redacts_secret` 弱断言；Codex TOML 纯字符串解析；无连通性说明 | analyze/读取 Codex 改用 `tomllib`（读侧，写侧仍字符串并文档化）；弱断言改为验证 uv 缺失区块 + 凭证来源；报告与 install-mcp.md 补“OK≠连通、需实际调用工具验证”说明 |

**未改动的取舍（F6，用户已拍板维持现状）**：因公开仓库，凭证只留在内部文档，首次使用需用户自行 export，接受该残余摩擦。

**验证**：`python -m unittest discover -s case-lite/tests` 全绿（新增至 21 用例）；`/tmp` 临时配置烟测确认：(A) codex 源码安装 feishu + 缺 Banshan，`--fix --yes` 只加 Banshan、保留源码 feishu；(B) claude-code 两路径同存 + `--fix --yes` 返回 exit 3 拒绝写入。未触碰任何真实全局配置。

**交给 codex 复核的重点**：
- `_strip_toml_table` 写侧仍是手写字符串裁剪（读侧已换 tomllib），复杂 TOML（多行数组、行内注释）是否仍有边角风险
- ambiguity 交互选择后 re-analyze 的路径是否需要同样做 F4 凭证读取（当前 resolve_creds 用的是初始 config_path）
- `--replace-feishu` 是否应同时提供“只刷新 env 凭证而不改 command/args”的更细粒度选项
