# 文档工具与原文保证

命令统一为 `python3 "{skill}/scripts/feishu_docs.py" ...`。脚本只允许既定只读
shortcuts 和 raw GET，通过 subprocess argv 调用 CLI，不使用 shell 拼接和凭证提取。

| 命令 | 输入 | 输出 |
|---|---|---|
| doctor | 无 | 版本与命令能力；不验证登录态 |
| children | HTTPS Docx/Wiki URL；可加 --recursive | 仅直接/递归 Docx 子文档元数据 |
| outline | URL、--output、可选 --max-level | 目录 JSON；无章节正文 |
| read | --outline-file、--section-id ID... 或 --all、--doc-key、--output-dir | 直接落盘原文和媒体 manifest；JSON 返回路径与状态 |

Docx 通过 raw GET 获取 document metadata 与最新分页 blocks，不传入或校验 revision_id，不使用
可能返回瘦身表格的 `docs +fetch --scope section`。使用 FeishuMCP 3.4.0 的纯 Python
BlockProcessor 渲染文本、完整表格、代码块和表格单元格内图片锚点。
只保存目录与选定语料，不持久化全文 blocks 缓存。一个 read 可批量处理多个章节，
父子重叠范围自动合并，避免重复原文与图片。

Docx ID 是真实 block ID；先按 parent/children 重建文档顺序，标题 range 是该顺序的
全局 0-based inclusive position，不能把未选表格的后置子块混进其他章节。
读取时重新获取最新 blocks，按章节 ID 重新计算范围，不比较目录中的版本和块数量；
旧目录文件中的 revision_id 会被忽略。Markdown 用原文 SHA256 检测变化；
只识别代码围栏外 ATX 标题，保留原文换行符和空白。
目录展示为 H1-H4，未展示的深层标题仍保留在父章节内容里。

## 媒体与内嵌资源

- 图片使用 CLI `docs +media-preview`，特定权限错误时尝试 `+media-download`。
- 画板使用 `whiteboard +export --output-type preview`。
- 两种图片路径分别来自 saved_path 和 preview_image_path；检查实际非空文件。
- 同步更新渲染标记中的媒体路径。manifest 记录 block_id、section_id、章节上下文、
  状态与保存路径。下载失败会在原文后附缺口说明，不阻塞其余章节下载。
- 表格里的图片同样处理；Native Markdown 外链作为原文保留，不发起自动外网下载。
- `partial` 要查看 manifest。图片下载成功还须调用 Read，读图结果写 visual-notes.md。

## 内嵌 Sheet 等资源

内嵌 Sheet、Base、思维笔记或不支持的图表会显式标记 needs_context/unsupported，
不会伪装成已读取正文。先报告资源与章节，用户可授权读取或补充文本/截图。
已安装相应 lark-sheets/lark-base 等 Skill 时可按其只读指南读取；它们不是本包的
隐式必需依赖。不具备相应工具时明确请求用户补充或确认带缺口继续。

对仅有一个嵌入工作表的 token，可通过 CLI 的 raw GET 读取指定范围（沿用用户身份）：

```bash
lark-cli api GET "/open-apis/sheets/v2/spreadsheets/<spreadsheet_token>/values/<sheet_id>!A1:Z100" \
  --as user --format json
```

这是范围读取，不能宣称已读取整个表格。需要全文时先检查工作表尺寸、按范围分批，
保留范围/来源信息。不要将 Base 当 Sheet 调用，不自动读取用户未确认的关联文档。

## 错误与恢复

- stdout 为成功 JSON，stderr 为失败 JSON；不能用 OpenAPI 顶层 code==0 判断 CLI 成功。
- 返回 bot 身份直接中止；登录与 scope 按认证指南处理。
- 分页 cursor 缺失/重复、重复 block ID、子块缺失、超过上限均报错，不能使用半篇正文。
- Docx 所选章节 ID 已不存在时，重新 outline 并确认选章；读取使用当前内容，不锁定版本。
- Markdown 哈希变化时重新 outline 并确认选章，不复用旧目录的 ID/range。
- read 按 doc-key 替换原文分片并重建 selected-corpus.md；修改选择时重新执行该文档的
  read 即可。用户补充和图示解读放独立文件，不手改生成的原文文件。
- 网络或解析失败不会替换既有语料；媒体部分失败会保存已取得的正文、缺口清单和 partial 状态。
