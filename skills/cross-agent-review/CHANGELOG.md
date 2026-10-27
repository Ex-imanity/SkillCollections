# Changelog — cross-agent-review

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 2.3.1 - 2026-10-28

- 单元测试迁到仓库级 tests/cross-agent-review；自动触发量具及源码验证手册迁到 evals/cross-agent-review，从运行权威入口清单中移除。
- 独立分发包保留三向适配器、共享协议、会话续跑和运行诊断，源码验证统一通过仓库级入口执行。

## 2.3.0 - 2026-10-28

- 三个适配器共用的 reviewer prompt 增加代码风格独立核验：检查实际修改和新增源码、适用规范及同职责历史范例，不能接受实施者的口头背书或以通用最佳实践代替本地证据。
- 代码评审单独报告 Style consistency 状态、双方路径及偏离/缺口；纯计划/文档不要求代码 diff，缺失来源只限制相关审查范围，不把所有风格建议升级为阻断。
- 补齐 primary 交接与闭环要求，可与 repository-code-style 联动但不强制安装该 skill。既有 verdict、CLI 参数、结果 schema、预算、计数、认证及超时续跑机制不变；新增风格字段仍由 primary 核验，不冒充机械校验。
- 扩展真实 runner 入口的受控回归，验证 Claude/Codex 的 stdin 与 Grok prompt 文件均接收到同一套风格要求；行为评估与实际跨 CLI 模型验证分开记录。
- 将基础清单中的本机绝对路径必读指令替换为包内证据规则，作者机器路径仅保留为可选历史出处；修正 ClaudeCode 真实源码审核提出的非阻断可移植性问题。

## 2.2.0 - 2026-10-19

- Codex 新增 `--resume` 与 `--artifact-path`，从超时前的 `thread.started` 保存真实 UUID；续跑使用原生 `codex exec resume <UUID>`，校验本地会话记录并复用原 attempt。无 UUID、会话丢失、内容变化或原生返回其他 UUID 时拒绝续跑；成功只提交一次。
- Codex 超时终止完整启动器进程组（POSIX；Windows 使用 taskkill 进程树），避免 npm Node 启动器退出后原生审核进程继续运行；保留用户原生会话，不清理用户 CODEX_HOME。

- Grok 新审核预先分配并保存会话 UUID；超时返回明确的 `timeout`、会话及可续跑状态。
- 新增原 gate 的显式 `--resume`：恢复相同会话，复用原 attempt，完成时只提交一次 success；新审核与完成后的复审仍受两次上限约束。
- 续跑绑定原请求、artifact key、目录、模型、输出及会话存储；`--artifact-path` 支持被审文件内容校验。已完成、非超时失败、状态损坏或绑定变化时拒绝续跑。
- 每个调用段单独记录时长、费用与续跑序号；保留共享锁、来源与完整结果校验，不自动扩展时限或发起新会话。三向审核均支持原 gate 的超时续跑。
- ClaudeCode 同样支持原 gate 的 `--resume`，新增可选 `--cd` 与实际审核文件登记；续跑绑定读取范围、认证模式、客户端身份及原预算上限。
- Claude 代理模式的隔离会话目录在超时后保留，最终完成或失败后清理；显式代理注入沿用相同隔离，继承 OAuth 的用户目录不受清理影响。Codex 普通审核入口保持兼容。

## 2.1.0 - 2026-09-07

- 抽出公共 `common.run_review_gate`：三向 gate 共享 lock → prepare → reserve → invoke → cost → cleanup → persist/commit 编排
- 可失败的 argv/env 构建放在 `prepare`（预留 attempt 之前），避免 setup 错误烧 attempt / 假 `review_started`
- `build_codex_command` 校验非空 `cd`/`last_message_path`（与 Grok cwd 对称，prepare 阶段 fail closed）
- Grok provenance 与 Codex 对称：成功须 `sessionId` **且** `usage.input_tokens/output_tokens` 非负完整对；`usage_is_incomplete` 写入 provenance 诊断
- 文档与回归同步（含 missing usage pair、prepare 失败不烧 attempt）

## 2.0.1 - 2026-09-07

修复 ClaudeCode 互审 finding（F3/F1/F4/F5/F2）：

- `to_grok`：成功须 `stopReason == "end_turn"`，否则 `completion_failure`（防截断带 verdict 伪成功）
- `to_grok`：stdout 从首个 `{` `raw_decode`，容忍 leading banner
- `to_grok`：成本仅接受有限数值；缺省/非数/NaN/Inf 记 `null`（去掉未 empirically 验证的 `cost_is_partial` 分支）
- `to_grok` / `to_codex`：临时文件 cleanup 失败不再丢弃已验证成功的 review（记 `cleanup_warning`）
- `common.fail_closed` / `gate_failure_result`：按 `reviewer=` 标注方向，去掉写死的 Codex→ClaudeCode 文案
- 回归：stopReason、banner JSON、cleanup-on-success、handoff 脱敏与 reviewer 文案

## 2.0.0 - 2026-09-07

MAJOR：统一 reviewer 桥命名（历史模块路径移除），并新增 Grok 第三 peer：

- 适配器统一为 `to_<peer>`：`scripts/to_claude.py`、`scripts/to_codex.py`、`scripts/to_grok.py`
- 共享协议运行时抽到 `scripts/common.py`（caps / redaction / cost / handoff / completion contract）
- 历史名 `codex_to_claude` / `claude_to_codex` 已移除；请改用 `python -m scripts.to_claude` / `to_codex`
- 新适配器 `to_grok`：任意 primary → Grok reviewer（`grok --prompt-file` + `--output-format json` + `--always-approve`）
- Grok headless 不读 stdin：adapter 写临时 prompt 文件，gate 结束后删除
- 成功条件：非空带标准 verdict 的 `text` + 真实 `sessionId`；`total_cost_usd` 缺失/partial 记 `null`，不伪造 0
- `runtime_capabilities`：`claude`→`to_claude`，`codex`→`to_codex`，`grok`→`to_grok`
- 约定 `Review/ForGrok/`、`Review/ByGrok/` 输出目录
- 回归测试覆盖三向命令拼装、started 事件、provenance、attempt cap、model preflight

CLI 参数与 fail-closed 契约不变；调用方必须改用 `python -m scripts.to_claude|to_codex|to_grok`。

## 1.0.0 - 2026-09-03

首个标注版本。此前变更见 git 历史，不追认为 release。

当前能力基线：

- 本机 Codex 与 ClaudeCode 双向只读评审：primary 保连续性与修复责任，reviewer 只返回带证据的 verdict
- 仅依赖本机 `claude` + `codex` CLI，官方 Codex plugin 仅为可选 fallback
- fail-closed、并发安全的固定 round cap（每 artifact 至多 2 次启动 / 2 次成功）、脱敏持久化
- readiness 判定基于真实结果信封，不采信 auth status
- 注：SKILL.md 内另有 `Status:` 成熟度标注，与版本号是两个独立维度
