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
└── scripts/                 # 作为 Python 包运行：`python -m scripts.<module>`
    ├── codex_to_claude.py            # Codex→ClaudeCode 适配器（claude -p，fail-closed 网关）
    ├── claude_to_codex.py            # ClaudeCode→Codex 直连适配器（codex exec --sandbox read-only）
    └── measure_claude_skill_trigger.py  # 真 skill 自动触发量具（eval 工具）
```

## 用法

从本 skill 目录运行（`scripts/` 需作为包解析）：

```bash
cd <skill-dir>
python -m scripts.codex_to_claude --help    # Codex 主 → ClaudeCode 评审
python -m scripts.claude_to_codex --help     # ClaudeCode 主 → Codex 评审
```

每个 review gate 需显式传入：request 文件、artifact key、可读目录、输出路径、超时、用户批准的单次预算。先读 `references/cross-agent-review-protocol.md`。

## 核心安全保证（协议）

- readiness 由**真实结果信封**判定，绝不用 `claude auth status`。
- reviewer 物理只读（claude `--permission-mode plan` + 固定 `Read,Grep,Glob`；codex 硬编码 `--sandbox read-only`）；无调用方 override。
- 并发安全的硬性 round cap（marker 锁从 check 到 commit）；**仅成功 review 后才计数**，失败调用不吃轮次；损坏计数 fail closed。
- 任何非成功 → fail closed 到**脱敏** durable handoff；禁止递归互审。
- codex 反向成功需真实 `thread_id` + `usage`，否则 fail closed；缺 USD 记 JSON `null`，绝不伪造 0。
- 只持久化经校验的非空 reviewer 输出;落盘前对已知 endpoint/token 值与密钥模式脱敏。

## 依赖

- 本机 `claude` + `codex` CLI（`codex exec --sandbox read-only --json` / `claude -p --output-format json`）。
- 无官方 Codex plugin 依赖（plugin 仅作可选 fallback，见 mapping reference）。
- 连续性契约：marker/成本日志为调用方指定的文件路径，可由任意 MRS/task-state 机制（如 `context-resilient-task`）满足；本 skill 不硬依赖它。

## 验证证据（提炼自 play-book）

- 适配器单测 `124 passed`；6 个安全 finding（3 P1 + 3 P2）闭环（provenance 校验、并发轮次锁、gate 级 I/O fail-closed、USD null、无 resume/session、固定只读工具）。
- 端到端：正向 adapter first-use PASS；反向 `codex exec` 直连 PASS。
- 压力 A/B：with-skill 拒绝伪造 verdict 有明显 uplift。
- 真 installed-skill 自动触发量具：**正例 9/10、负例 10/10（0 误触发），19/20 确定、0 ambiguous**。
