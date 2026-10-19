# case-lite-lark

面向团队成员本地 Agent 和云端 Pod 中 Claude Code 的小需求用例生成 Skill。使用 lark-cli 访问飞书，
内置脚本读取选定章节、处理媒体并写回搬山，无需配置 stdio MCP。
它与原始 case-lite 独立安装、独立产物目录，原始 Skill 保持不变。

## 安装与依赖

复制整个 `case-lite-lark/` 到 Agent 的 skills 目录。运行依赖为 Python 3.10+ 和
本机或平台预置的 lark-cli；读取契约已按 1.0.97、接入契约按 1.0.98 核对。Python 脚本仅使用标准库，
无需安装 feishu-docx-blocks、MCP SDK、httpx 或其他 Skill。
同一份 Skill 支持两种接入方式，成员各自授权自己的飞书账号：

| 模式 | 应用配置 | 首次接入 |
| --- | --- | --- |
| 平台 | 复用 Agent 绑定并提供给 CLI 的已有应用 | 平台完成配置；用户按需授权 |
| 本地 | 复用团队提供的已有应用，使用命名 profile | 导入一次内部配置，随后按需授权 |

平台建议在 Agent 环境中设置 `CASE_LITE_LARK_MODE=platform`；脚本不会创建或重配应用。
未明确模式且没有本地接入设置时，doctor 返回 `mode:auto`、`needs_mode_choice:true`，
Agent 先确认本地或平台，再进入对应接入流程；不会默认把本地新用户交给平台管理员。
本地接入后自动复用，平台明确选择模式后沿用现有 CLI 上下文。首次本地接入：

```bash
python3 /path/to/case-lite-lark/scripts/setup_lark.py local \
  --config-file /path/to/private/team-app.json
```

管理员通过内部渠道提供已有 App 的配置，格式参考 [配置示例](assets/team-app.example.json)。
完成填写的配置放在 Skill 分发目录之外；安装包只包含占位示例。
脚本默认创建 `case-lite-team` profile；同名冲突时中止，同应用已配置时直接复用原 profile，
不修改 CLI 默认应用。用户设置保存在 `~/.config/case-lite-lark/runtime.json`，仅含模式和 profile，
后续无需重复接入。首次使用或 scope 变化时，按 [认证指南](references/auth-and-runtime.md)
通过 `setup_lark.py login` 完成用户授权。

已有 case-lite/feishu-docx-blocks 的成员仍需首次接入 CLI，可使用同一个团队 App；
旧 MCP 配置和 token 不自动迁移。仅移除旧 Skill 目录不影响独立保存的 CLI 配置。
全新成员从管理员取得已有团队应用配置并授权自己的账号，无需申请或创建新 App。

```bash
python3 /path/to/case-lite-lark/scripts/feishu_docs.py doctor
```

该检查返回当前模式与 profile，不登录、不读取 token、不修改配置；成功仅代表 CLI 命令可用。
本包不包含公司平台的遥测/自动升级脚本，不应复制其他 Skill 的 version.json。
平台可在正式发布时按自身规则生成分发元数据。

## 使用

```text
case-lite-lark
需求名称：用户自助重置密码
迭代名称：账号能力10月迭代（可省略）
后端方案：https://example.feishu.cn/wiki/TOKEN
需求文档：https://example.feishu.cn/docx/TOKEN
```

Agent 会依次发现子文档并确认纳入、展示目录并等待选章、统一收集补充信息，
再读取原文和图片、审核场景结构、审核完整用例、询问是否自检，以及可选写回搬山。
不自动读入所有子文档，不自动选章。默认产物为 `case-lite-lark-output/需求slug/`。

Docx 原文通过 CLI 原始 blocks API 读取，复用上游渲染器保留完整表格和图片锚点。
原生 Markdown 支持代码围栏外的 ATX 标题、父子章节去重和原文保留。
目录与正文间文档变化会中止，重新选章后继续。

图片/画板保存在任务目录，并返回可供 Claude Code Read 的绝对路径。
媒体失败或未读取的内嵌 Sheet 等会报告 partial，须补充或由用户确认带缺口继续。
内嵌资源的处理边界见 [工具指南](references/document-tools.md)。

## 搬山

参考用例和写回都通过已有 HTTP JSON-RPC 服务，不要求 Agent 注册 MCP。
可用 `BANSHAN_MCP_ENDPOINT` 指定同业务部署端点。
写回必须先 dry-run，用户确认后加 `--confirm`。已有节点会阻塞，脚本不覆盖或删除。
写回成功还须读回并核对内容。超时或状态未知时不自动重发。

## 验证

```bash
python3 -m unittest discover -s skills/case-lite-lark/tests
python3 -m unittest discover -s tests
git diff --check
```

测试使用合成文档与模拟 CLI/搬山响应，不需要账号，覆盖首次接入、重复接入、配置冲突、
跨命令 profile 一致性和平台模式不初始化。云端发布前仍需验证实际授权、
真实文档/图片读取、模型视觉输入与 Pod 重建后的状态恢复。
行为评估场景见 [evals/evals.json](evals/evals.json)，实现来源见 [UPSTREAM.md](UPSTREAM.md)。
