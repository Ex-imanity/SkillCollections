# Changelog — cross-agent-review

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 2.1.0 - 2026-09-07

- 抽出公共 `common.run_review_gate`：三向 gate 共享 lock → reserve → invoke → cost → cleanup → persist/commit 编排
- Grok provenance 与 Codex 对称：成功须 `sessionId` **且** `usage.input_tokens/output_tokens` 非负完整对
- 文档与回归同步（含 missing usage pair）

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
