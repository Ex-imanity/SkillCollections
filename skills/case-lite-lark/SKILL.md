---
name: case-lite-lark
version: 0.2.3
description: >-
  使用 lark-cli 从飞书 Docx、Wiki 或原生 Markdown 中手动选章，为单一功能点生成测试用例并可选写回搬山。
  用户明确说 case-lite-lark、lark-cli 版用例生成，或要求在云端 Claude Code 中不配置 stdio MCP 生成小需求用例时使用。
  保留选章、补充信息、场景分层复核、完整用例审核和可选自检；适用于 1-2 篇主要文档及经用户确认纳入的子文档。
compatibility: Python 3.10+、lark-cli（读取已核对 1.0.97，接入契约核对 1.0.98）、具备图片 Read 能力的 Agent；可选搬山 HTTP 服务。
metadata:
  requires:
    bins: [python3, lark-cli]
---

# case-lite-lark

把用户选择的需求原文和图示转成可执行测试用例。飞书请求统一通过当前模式的
`lark-cli --as user`，不注册 MCP，不读取 CLI token。平台复用绑定配置；本地首次
导入用户指定的内部团队应用配置，成员各自授权，不创建新应用。
这是独立安装单元，运行时不访问原始 case-lite 或 FeishuMCP 仓库。

## 入口与运行条件

定位本 `SKILL.md` 的实际目录，记为 `{skill}`；所有脚本从该目录执行，无需修改
全局 Agent 配置。在用户任务工作目录运行，产物必须位于 CWD 内。

```bash
python3 "{skill}/scripts/feishu_docs.py" doctor
```

`doctor` 返回 `mode`、`profile` 和 `needs_mode_choice`，仅检查 CLI 能力；
`auth_verified:false` 不代表认证失败，不能据此发起配置或授权。
若返回 `mode:auto`、`needs_mode_choice:true`（缺 CLI 时也可能在 `error` 中），先询问
“这次在本地 Agent 还是公司平台运行？”并等待回复，不先登录、导入或读取文档。
用户已明确说明运行位置时直接采用，不重复询问。

用户选择平台后，对本次后续入口显式传入 `CASE_LITE_LARK_MODE=platform`，保留绑定配置；
平台 Agent 建议预置这个环境变量。选择本地且尚未接入时，读取
[认证与运行模式](references/auth-and-runtime.md)，用内部提供的配置路径执行一次接入。
本地设置保存后自动复用；不从旧 case-lite/MCP 自动搬取凭证或登录态。

普通任务先尝试实际读取。只有认证、身份或 scope 错误时，按上述认证指引恢复；
缺少应用配置与缺少用户授权分开处理。平台缺配置交由管理员接入绑定应用；
本地缺配置引导一次性接入。即使 CLI hint 建议 `config init --new`，也不要执行。
不要自动安装、升级、覆盖应用或重置已有登录态。用户授权统一使用
`setup_lark.py login/status/qrcode`，确保与文档读取使用同一 profile。
授权恢复后重试读取；资源访问拒绝应由文档所有者授权，不能靠切换 bot 绕过。

输出 JSON 的 `ok:true` 代表命令完成；`read` 的 `data.status` 还须检查：
`complete` 为已获取选定文本和可下载媒体，`partial` 表示仍有媒体或内嵌资源待处理。
它们都不表示模型已经看过图片，也不等于云端发布验收通过。

## 产物与恢复

- 收集需求名称、文档链接和可选文档类型（需求/前端/后端/客户端/算法）。
- 迭代名称可选，不主动追问。名称转小写英文 kebab-case，日期版本保留数字。
- 无迭代：`case-lite-lark-output/{需求slug}/`。
- 有迭代：`case-lite-lark-output/{迭代slug}/{需求slug}/`。
- 若本次指定迭代，而同名平铺目录已有产物，展示“迁移/新建”并等待用户选择；
  不自动移动旧目录。相同迭代复用已有目录，拼写冲突先确认。

每步结束前写入相应产物；进入下一步前检查文件存在且内容已更新。
跳过项目写明原因，不删除中间产物。后续修改要同步对应源文件。

```text
{产物根目录}/
├── chapters/                 # 子文档树、各文档目录 JSON、章节展示与用户选择
├── corpus/
│   ├── parts/                # 脚本维护的每文档原文和媒体 manifest
│   ├── selected-corpus.md    # 由 parts 确定性合并，不手工摘要或追加
│   ├── extra-context.md      # 用户补充，含后续 Review 补充
│   └── visual-notes.md       # 图片 Read 结果、无法读取的资源及用户决定
├── feishu_images/            # 下载到与 Agent 相同的文件系统
├── style-ref/reference-cases.md
├── structure.md
├── full.md
├── review.md
└── writeback/                # node-tree.json、writeback-log.json
```

有迭代时，在迭代目录维护 `iteration-index.md`：需求、产物目录、caseId、状态、
更新时间。仅追加/更新本需求行，不重写其他需求；状态为“进行中/用例已生成/已写回”。
新任务从“进行中”开始，写回验证通过后才填 caseId 和“已写回”。

## Step 1：输入与子文档发现 [HITL]

初始化 `extra-context.md`、`visual-notes.md`、`reference-cases.md` 和 `review.md`
占位说明。对 Docx/Wiki 只发现子文档元数据：

```bash
python3 "{skill}/scripts/feishu_docs.py" children "{url}" --recursive
```

将结果、父子层级和文档类型写入 `chapters/child-documents.md`。有子文档时列出
编号并等待用户选择“全部纳入/指定编号/跳过”；默认类型继承父文档，可由用户覆盖。
发现不等于纳入，更不等于允许读取正文。只有确认纳入的文档进入下一步。
普通 Docx 不在 Wiki 树中可返回空列表；权限/网络错误须报告，不能当作“没有子文档”。
原生 `/file/` 跳过子文档发现并记录“不适用”。

## Step 2：逐篇浏览与手动选章 [HITL]

按输入顺序分配稳定 `doc-key`（如 `01-backend`、`02-requirement`），再获取目录：

```bash
python3 "{skill}/scripts/feishu_docs.py" outline "{url}" \
  --output "{产物根目录}/chapters/{doc-key}.json"
```

脚本识别 Docx/Wiki/原生 Markdown。Docx 读取最新 blocks，不传入或校验 revision_id；
Markdown 保存内容哈希。输出仅包含标题等元数据，脚本内部读取文档用于解析，
不向模型提前返回全文。
将目录转成用户编号树，写入 `chapters/{doc-key}-chapters.md` 并展示。
用户可按编号、关键词或“全选”选择；将展示编号映射到 JSON 的真实 `sections[].id`，
并记录标题、ID、range。Docx 的 ID 是 block ID，Markdown 的 ID 是 `1`/`1.1`。

无标题时，等待用户选择“全文导入/跳过/手动补充”。“全选”表示选中目录里的全部
章节；仅用户明确要求全文（包含开头无标题内容）时使用后续的 `--all`。

**所有文档选章完成后，统一询问是否还有补充信息，并等待明确回复。**
已有补充也要确认是否完整。文本保存至 `corpus/extra-context.md`；没有则写占位。
此处完成后再进入 Step 3，不因“全选”或需求简单跳过。

## Step 3：原文、图片、参考风格与场景结构 [HITL]

### 3a：参考用例（可选）

用户可提供搬山 caseId、粘贴 Markdown 或跳过。仅学习措辞和粒度，不复制参考层级、
前置条件节点或优先级。获取 caseId 参考无需 Agent MCP 配置：

```bash
python3 "{skill}/scripts/banshan_reference.py" --case-id {caseId} \
  --output "{产物根目录}/style-ref/reference-cases.md"
```

失败可粘贴或使用 [默认风格](assets/case-learning.md)，在文件中记录选择。

### 3b：读取选定语料与图片

```bash
python3 "{skill}/scripts/feishu_docs.py" read \
  --outline-file "{产物根目录}/chapters/{doc-key}.json" \
  --section-id "{真实章节ID1}" "{真实章节ID2}" \
  --output-dir "{产物根目录}" --doc-key "{doc-key}"
```

用户确认全文导入时，用 `--all` 代替 `--section-id ...`。
每篇完成后脚本立即更新原文分片、媒体 manifest 和 `selected-corpus.md`。
同文档重跑替换其分片，不重复追加；不同文档不得复用同一 doc-key。
Docx 按最新 blocks 中的章节 ID 重新计算范围，不因版本或块数量变化中止；
所选章节已不存在时重新展示目录并确认选择。Markdown 哈希变化时仍须重新选章。

`selected-corpus.md` 是脚本提取的选定原文，保留代码、字段、JSON、curl 和完整表格；
不得摘要、精简或改写。其 `SOURCE` 注释记录来源与章节。
原生 Markdown 保留原始文本和图片链接，不自动下载其外链图片。

**对 manifest 中每个 `status:downloaded` 的图片/画板，实际调用 Agent 的 `Read`
读取其绝对路径。** 将图中规则、分支、章节关联写入 `visual-notes.md`，不改写原文。
只打印路径、下载成功或在网页显示预览均不算模型已读图。
下载失败、Read 不可用或 `needs_context/unsupported` 内嵌资源时，参考
[工具与资源指南](references/document-tools.md)，报告具体缺口，请用户补充、重试或
明确同意带缺口继续；未获决定前暂停生成，不默默将文本当完整需求。

进入生成前确认：所有入选章节已落盘；图片已 Read 或记录用户的降级决定；
`extra-context.md` 和 `reference-cases.md` 均存在。

### 3c/3d：生成并复核场景层级

此时读取 [生成与格式规则](references/generation.md)，执行 3c 和必做的 3d。
按选定语料、补充信息和图示生成 `structure.md`；逐个顶层场景评估是否拆子场景，
向用户展示覆盖全部场景的分层复核表。复核表只放在确认消息，不写进 structure.md。
等待用户确认场景结构后进入 Step 4。

## Step 4：完整用例 [HITL]

按 [生成规则 Step 4](references/generation.md) 和已确认的 structure.md 展开 full.md。
编号即路径，场景/测试点不混排；前置条件融入执行步骤第一步。
full.md 不生成 P0/P1/P2。发现结构需调整时先回到结构审核，不能自行改已确认结构。
保存完整用例并等待用户审核；有迭代时更新索引为“用例已生成”。

保存 full.md 后先做纯本地格式校验，无需 caseId：

```bash
python3 "{skill}/scripts/writeback.py" "{产物根目录}/full.md" --dry-run
```

修复格式错误和警告后再交用户审核；这一步不请求搬山接口。

## Step 5：可选自检 [HITL]

按 [生成规则 Step 5](references/generation.md) 询问是否自检，并等待回复。
选择跳过也写 review.md。选择自检时先收集新增信息，再检查边界、异常、状态、权限、
交互、重复用例和来源一致性，先记录/展示建议，不直接修改 full.md。
用户同意后才增量修订；结构变化先更新 structure.md 并重新审核，再展开 full.md。

## Step 6：可选写回搬山 [HITL]

用户可只保留本地产物。需要写回时收集目标 caseId，命令参数只传正整数，不带
文字标签，不凭空补全 ID。必须先 dry-run：

```bash
python3 "{skill}/scripts/writeback.py" "{产物根目录}/full.md" \
  --case-id {caseId} --dry-run
```

修复全部阻塞错误与格式警告，展示树形概览与目标 caseId，等待用户确认写回。
确认后再执行：

```bash
python3 "{skill}/scripts/writeback.py" "{产物根目录}/full.md" \
  --case-id {caseId} --confirm
```

目标已有节点或写前检查失败时中止，不删除、不自动重复追加。
只有写入响应成功且读回业务内容与节点树一致时才报告成功。
写入超时或读回不一致要报告“状态未确认”，先人工核对，不能自动重发。
检查 `writeback-log.json` 的 success；验证通过才更新迭代索引。
搬山仍依赖既有 HTTP 服务，可用 `BANSHAN_MCP_ENDPOINT` 指定同业务部署端点。
不要求在 Claude Code 中注册任何 MCP server。
