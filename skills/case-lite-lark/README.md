# case-lite-lark

面向云端 Pod 中 Claude Code 的小需求用例生成 Skill。使用平台的 lark-cli 访问飞书，
内置脚本读取选定章节、处理媒体并写回搬山，无需配置 stdio MCP。
它与原始 case-lite 独立安装、独立产物目录，原始 Skill 保持不变。

## 安装与依赖

复制整个 `case-lite-lark/` 到 Agent 的 skills 目录。运行依赖为 Python 3.10+ 和
平台预置的 lark-cli；CLI 契约已按 1.0.97 核对。Python 脚本仅使用标准库，
无需安装 feishu-docx-blocks、MCP SDK、httpx 或其他 Skill。
平台负责 CLI 应用配置和每位用户的登录态，首次使用或 scope 变化时按
[授权指南](references/auth-and-runtime.md) 在用户浏览器完成 Device Flow。

```bash
python3 /path/to/case-lite-lark/scripts/feishu_docs.py doctor
```

该检查不登录、不读取凭证、不修改全局配置；成功仅代表 CLI 命令可用。
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

测试使用合成文档与模拟 CLI/搬山响应，不需要账号。云端发布前仍需验证实际授权、
真实文档/图片读取、模型视觉输入与 Pod 重建后的状态恢复。
行为评估场景见 [evals/evals.json](evals/evals.json)，实现来源见 [UPSTREAM.md](UPSTREAM.md)。
