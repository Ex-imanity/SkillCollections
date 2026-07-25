# cross-agent-review

让本机两个 AI CLI agent（Codex 与 ClaudeCode）互相做**只读评审**的可复用 skill：任一 agent 作为 primary 产出计划/代码，调用另一个 agent 做带证据的只读 review，primary 保留连续性与修复责任。**双向对称、去插件依赖、可分发**——只依赖本机 `claude` 和 `codex` 两个 CLI。

## 何时触发

- 需要「让另一个本地 agent review 这个计划/PR」「Codex 写、ClaudeCode 评审」「ClaudeCode 写、Codex 挑 bug」「Codex/ClaudeCode 互审」这类跨代理评审 handoff 时。
- **不**用于单 agent 自审、普通 code review、认证排障等（近邻负例已验证不误触发）。

## 结构

```text
cross-agent-review/
├── SKILL.md                 # agent 主入口：触发条件、权威来源指针、不可协商守则
├── README.md                # 本文件（面向人）
├── references/
│   ├── cross-agent-review-protocol.md          # CLI 机制层协议（readiness/凭证/round-cap/fail-closed/脱敏）
│   ├── codex-primary-claudecode-review-loop.md # 基础协作清单（角色/停止条件/失败模式）
│   └── claude-to-codex-mapping.md              # 可选官方 Codex plugin 映射（fallback）
├── scripts/                 # 作为 Python 包运行：`python -m scripts.<module>`
    ├── codex_to_claude.py            # Codex→ClaudeCode 适配器（claude -p，fail-closed 网关）
    ├── claude_to_codex.py            # ClaudeCode→Codex 直连适配器（codex exec --sandbox read-only）
    ├── runtime_capabilities.py       # 本机已知 agent CLI 能力报告（不发起评审）
    └── measure_claude_skill_trigger.py  # 真 skill 自动触发量具（eval 工具）
└── tests/                   # 适配器与本机能力发现回归测试
```

## 用法

从本 skill 目录运行（`scripts/` 需作为包解析）：

```bash
cd <skill-dir>
python -m scripts.codex_to_claude --help    # Codex 主 → ClaudeCode 评审
python -m scripts.claude_to_codex --help     # ClaudeCode 主 → Codex 评审
python -m scripts.runtime_capabilities --json # 本机 agent CLI 发现（不发起模型调用）
```

每个 review gate 需显式传入：request 文件、artifact key、可读目录、输出路径、超时和用户明确批准。Codex 主 → ClaudeCode 还必须传 `--max-budget-usd`；反向 Codex CLI 没有等价 USD 上限，只能以用户批准、超时和固定 attempt cap 限制。先读 `references/cross-agent-review-protocol.md`。

已验证的一个特定 Anthropic 兼容网关会对 Claude Code 默认的 `sdk-cli` 身份返回 pre-model 403；这不是通用 token 故障结论。首选让网关放行官方身份。只有用户明确批准兼容方案后，才传 `--gateway-compat-cli-identity`：adapter 从实际解析到的本机 `claude --version` 导出 plain `claude-cli/<version>`，并用同一个绝对路径启动 reviewer。它不接收调用者填写的版本、不伪装 `claude-vscode`、不接收任意 Header，且版本探测失败时不预留 attempt；新版本 artifact 应使用新的 artifact key，不能靠换 key 绕过同一 artifact 的两次调用上限。

`runtime_capabilities` 只检查明确列出的本机 CLI 候选（含 `claude`、`codex` 和常见的其他 agent CLI）及其 `--version`，以 `PATH`-only 子进程运行，不传递凭证。发现其他 CLI 仅供诊断，不会自动把它们接入互审；当前被 skill 支持的方向仍只有 `claude` 与 `codex`。

## 核心安全保证（协议）

- readiness 由**真实结果信封**判定，绝不用 `claude auth status`。
- 默认清除宿主继承的自定义 Header/IDE 身份；兼容 User-Agent 必须显式启用，并从实际执行的本机 Claude CLI 导出。
- reviewer 物理只读（claude `--permission-mode plan` + 固定 `Read,Grep,Glob`；codex 硬编码 `--sandbox read-only`）；无调用方 override。
- 并发安全的固定上限（marker 锁从 check 到 commit）：每个 artifact 最多 2 次已启动调用和最多 2 次成功 review；已启动后失败也消耗 attempt，损坏计数 fail closed。同一 marker 文件在整个 reviewer 调用期间持锁，因此共享该文件的不同 artifact gate 会串行；等待方没有独立获取锁超时，通常会等待当前调用的配置超时（默认 600 秒）及本地 I/O。
- 任何非成功 → fail closed 到**脱敏** durable handoff；禁止递归互审。
- codex 反向成功需真实 `thread_id` + `usage`，否则 fail closed；缺 USD 记 JSON `null`，绝不伪造 0。
- 只持久化经校验的非空 reviewer 输出;落盘前对已知 endpoint/token 值与密钥模式脱敏。

## 依赖

- 本机 `claude` + `codex` CLI（`codex exec --sandbox read-only --json` / `claude -p --output-format json`）。
- 无官方 Codex plugin 依赖（plugin 仅作可选 fallback，见 mapping reference）。
- 连续性契约：marker/成本日志为调用方指定的文件路径，可由任意 MRS/task-state 机制（如 `context-resilient-task`）满足；本 skill 不硬依赖它。

## 验证与历史证据

- 当前 bundle 的 P1 回归测试位于 `tests/`，覆盖固定两轮上限、双向失败调用的 attempt cap、Codex→ClaudeCode 客户端身份隔离/本地版本导出，以及本机 capability report。
- 历史 play-book 适配器单测 `124 passed` 及其他数字仅为 provenance；安装者应运行本 bundle 的测试和实际 review gate。
- 端到端：正向 adapter first-use PASS；2026-07-25 使用真实 `claude-cli/2.1.216` 子进程身份完成网关兼容 gate；反向 `codex exec` 直连 PASS。
- 压力 A/B：with-skill 拒绝伪造 verdict 有明显 uplift。
- 真 installed-skill 自动触发量具：**正例 9/10、负例 10/10（0 误触发），19/20 确定、0 ambiguous**。
