# cross-agent-review

让本机 AI CLI agent（Codex、ClaudeCode、Antigravity `agy`、Grok）互相做**不改 primary 工件的评审**的可复用 skill：任一 agent 作为 primary 产出计划/代码，调用**另一个** agent 做带证据的 review，primary 保留连续性与修复责任。评审子进程为避免非交互权限阻塞而使用全权限执行，但任务契约禁止它修改被评审工件、生产代码、配置和 primary 的 MRS。**四方对称、去插件依赖、可分发**——只依赖本机 `claude` / `codex` / `grok` / `agy` 中你实际调用的 reviewer CLI。

## 何时触发

- 需要「让另一个本地 agent review 这个计划/PR」「Codex 写、ClaudeCode/Antigravity/Grok 评审」「Antigravity 写、Codex/Claude/Grok 审」「四方互审」这类跨代理评审 handoff 时。
- **不**用于单 agent 自审、普通 code review、认证排障等（近邻负例已验证不误触发）。

## 结构

```text
cross-agent-review/
├── SKILL.md                 # agent 主入口：触发条件、权威来源指针、不可协商守则
├── README.md                # 本文件（面向人）
├── references/
│   ├── cross-agent-review-protocol.md          # CLI 机制层协议（readiness/凭证/round-cap/fail-closed/脱敏）
│   ├── codex-primary-claudecode-review-loop.md # 基础协作清单（角色/停止条件/失败模式；agent 映射可换）
│   ├── timeout-continuation.md                 # Codex/Grok/ClaudeCode/Antigravity 超时后原会话续跑与计数边界
│   └── claude-to-codex-mapping.md              # 可选官方 Codex plugin 映射（fallback）
└── scripts/                 # 作为 Python 包运行：`python -m scripts.<module>`
    ├── __init__.py                  # Python 包入口
    ├── common.py                    # 共享 fail-closed 协议运行时 + run_review_gate 编排
    ├── continuation.py              # 未完成 gate 的会话身份、内容绑定和续跑状态
    ├── to_claude.py                  # 任意 primary→ClaudeCode（claude -p）
    ├── to_codex.py                   # 任意 primary→Codex（codex exec 全权限无确认）
    ├── to_grok.py                    # 任意 primary→Grok（grok --prompt-file headless）
    ├── to_agy.py                     # 任意 primary→Antigravity（agy stream-json headless）
    └── runtime_capabilities.py       # 本机已知 agent CLI 能力报告（不发起评审）
```

## 用法

代码 Review 默认要求 reviewer 独立核对实际修改和新增/未跟踪源码、适用规范及
同职责历史实现。Primary 交接比较基准、风格依据、自审和偏离理由；reviewer 自行
打开来源验证，不接受“已检查”背书，也不能把通用最佳实践直接称为仓库风格。

交接增加可访问的本地档案摘录/定位、近半年实质范例、旧例回退理由和本次文件落点。
Reviewer 核对档案版本与相关工作区差异，先审类/文件必要性、目录分层和生产/框架
入口，再审能力复用与内部表达；新旧冲突和机制验证分别记录，不能用编译通过抵消
职责或复用问题。缺少档案时自行补查，不把缓存文件本身当作规范。

档案不可读时，交接内联授权范围内的机制身份、同机制范例路径/符号/commit、能力
所有者及仓库/基准。原始 CR 按项保留要求强度、处理和验证状态，继承未结项；
新增层比较删除/合并方案，实际复用核实具体 API、有效版本和语义。审查同时检查
业务说明的真实性，并注明验证对应的快照，避免工作区与部分暂存版本混淆。

最终回复除总体 verdict 外，单列 `Style consistency: PASS | NEEDS CHANGES |
NOT VERIFIED`，选择一个状态并附双方路径、检查范围及偏离/缺口。纯计划或文档使用
`NOT APPLICABLE`，不强求代码 diff；混合任务只检查代码部分。状态不自动决定严重度，
依据不可访问只限制相应审查范围。可以联动 `repository-code-style`，未安装也能按
共用 prompt 的自包含清单完成。适配器的成功校验没有机械检查这些新增字段或语义，
primary 必须复核后才能声称风格闭环；prompt 不是工具拦截器。

从本 skill 目录运行（`scripts/` 需作为包解析）：

```bash
cd <skill-dir>
python -m scripts.to_claude --help            # 任意 primary → ClaudeCode 评审
python -m scripts.to_codex --help             # 任意 primary → Codex 评审
python -m scripts.to_grok --help              # 任意 primary → Grok 评审
python -m scripts.to_agy --help               # 任意 primary → Antigravity 评审
python -m scripts.runtime_capabilities --json # 本机 agent CLI 发现（不发起模型调用）
```

四个模块都是 **reviewer 桥**（`to_<peer>`），primary 不绑定。Codex / ClaudeCode / Antigravity / Grok 任一方作 primary 都可以调用其他三方的 `to_<peer>`。共享协议运行时在 `scripts/common.py`。

每个 review gate 需显式传入：request 文件、artifact key、可读/工作目录、输出路径、超时和用户明确批准。Claude 评审还必须传 `--max-budget-usd`；Codex / Grok / Antigravity CLI 在此路径没有等价 USD 上限，只能以用户批准、超时和固定 attempt cap 限制。先读 `references/cross-agent-review-protocol.md`。

Codex/Grok/ClaudeCode/Antigravity 审核已启动但超时时，可在原命令上增加 `--resume`，继续同一个 gate 和会话，**不增加 attempt 次数**；最终完成只计一次 success。初次调用与续跑都用 `--artifact-path <file>` 登记所有被审文件（Antigravity 方向**必须**提供 `--artifact-path` 才具备续跑资格），防止文件已变更却复用旧审核。每次续跑仍单独计费、记录时长且需要处于用户已批准的范围内；不会自动无限续跑。Codex 从超时前的原生 JSONL 事件获取 UUID 并使用 `codex exec resume <UUID>`；Antigravity 从 `stream-json` 的 `init` 事件捕获 `conversation_id`，校验 `~/.gemini/antigravity-cli/conversations/<UUID>.db` 非空普通主库后使用原生 `--conversation=<UUID>` 续跑，且每次恢复段都必须收到匹配的 `init` UUID 回执。ClaudeCode/Grok/Antigravity primary 调用 Codex reviewer 的方法见包内 [Codex reviewer 入口](references/timeout-continuation.md#codex-reviewer)。细节见 [超时续跑](references/timeout-continuation.md)。

约定输出目录（四方对称）：

- 请求：`Review/ForClaudeCode/`、`Review/ForCodex/`、`Review/ForGrok/`、`Review/ForAntigravity/`
- 结果：`Review/ByClaudeCode/`、`Review/ByCodex/`、`Review/ByGrok/`、`Review/ByAntigravity/`

四个 adapter 都可选传 `--model <MODEL>`。不传时保持本机 CLI 默认模型；注意 `agy` 同时托管 Gemini 与 Claude 模型，若 ClaudeCode 与 Antigravity 互审，建议显式传 `--model gemini-4-neon-high` 等 Gemini 模型以保证真正的跨模型家族独立性。传入时 adapter 将其校验后以单个 `--model=<MODEL>` 原生参数传递，并在子进程实际启动后于成本日志记录 `requested_model`，不会把它称为实际生效模型。模型名不做内置白名单；空值、前导 `-`、ASCII 控制字符和超过 128 字符的值会在预留 attempt 前 fail closed。CLI `--help` 明确不支持 `--model` 时也会在预留前失败；帮助探测不可用时保持 inconclusive 并由真实结果信封裁决。Claude 方向仍受 `--max-budget-usd` 限制；Codex / Grok / Antigravity 方向没有 provider USD 上限，选择更高成本模型必须纳入用户明确授权、固定两次 attempt 和 timeout 的成本边界。

模型选择只是在原有 gate 命令末尾按需追加：

```bash
# 默认：不要追加 --model，使用本机 CLI 配置的默认模型。
python -m scripts.to_claude <正常的必填 gate 参数>
python -m scripts.to_codex <正常的必填 gate 参数>
python -m scripts.to_grok <正常的必填 gate 参数>
python -m scripts.to_agy <正常的必填 gate 参数>

# 显式选择 reviewer 模型（ClaudeCode ↔ Antigravity 互审建议显式选 Gemini 模型）。
python -m scripts.to_claude <正常的必填 gate 参数> --model sonnet
python -m scripts.to_codex <正常的必填 gate 参数> --model gpt-5.6-terra
python -m scripts.to_grok <正常的必填 gate 参数> --model grok-4.5
python -m scripts.to_agy <正常的必填 gate 参数> --model gemini-4-neon-high
```

已验证的一个特定 Anthropic 兼容网关会对 Claude Code 默认的 `sdk-cli` 身份返回 pre-model 403；这不是通用 token 故障结论。首选让网关放行官方身份。只有用户明确批准兼容方案后，才在 **Claude 评审** 路径传 `--gateway-compat-cli-identity`：adapter 从实际解析到的本机 `claude --version` 导出 plain `claude-cli/<version>`，并用同一个绝对路径启动 reviewer。它不接收调用者填写的版本、不伪装 `claude-vscode`、不接收任意 Header，且版本探测失败时不预留 attempt；新版本 artifact 应使用新的 artifact key，不能靠换 key 绕过同一 artifact 的两次调用上限。

`runtime_capabilities` 只检查明确列出的本机 CLI 候选（含 `claude`、`codex`、`grok`、`agy` 和常见的其他 agent CLI）及其 `--version`，以 `PATH`-only 子进程运行，不传递凭证。其中的 `supported` 仅代表已注册该评审方向且本机 `--version` 探测通过（完整 gate flag 仍由各 adapter 的 `--help` preflight 与真实结果信封把关）；发现其他 CLI（如独立的 `gemini`）仅供诊断，不会自动接入互审。当前被 skill 支持的 reviewer 方向是 `to_claude`、`to_codex`、`to_grok`、`to_agy`。

## 核心安全保证（协议）

- readiness 由**真实结果信封**判定，绝不用 `claude auth status` 或同类 auth-status 命令。
- 凭证（Claude 评审）：优先用 settings.json 的 `env` 代理块（隔离 `CLAUDE_CONFIG_DIR` 后显式注入），其次用显式注入的代理变量（同样隔离目录）；代理模式超时保留本 gate 私有会话，最终结束后清理。两者都没有时回退 `inherited`，直接让本机 `claude` 用它自己已有的认证（订阅/OAuth 登录或环境里的 `ANTHROPIC_API_KEY`）——**无需代理网关**。Codex / Grok / Antigravity 评审使用本机 CLI 环境认证（Grok 常见 `XAI_API_KEY` 或 `~/.grok/config.toml`；Antigravity 使用本机缓存登录或 `GEMINI_API_KEY`）。未认证的 CLI 会在真实信封里被判为 `auth_failure` 并 fail closed。
- 默认清除宿主继承的自定义 Header/IDE 身份（Claude 路径）；兼容 User-Agent 必须显式启用，并从实际执行的本机 Claude CLI 导出。
- 可选 `--model` 仅控制 reviewer 模型；省略即使用各 CLI 默认模型。它不能覆盖 profile、任意 config、reasoning、权限或 sandbox；有效值以单个 `--model=<value>` argv token 传递。
- reviewer 的**任务边界**是只评审、不改 primary 工件；但为避免非交互写文件/工具调用阻塞，Claude 使用 `--permission-mode bypassPermissions --dangerously-skip-permissions`，Codex 使用 `--sandbox danger-full-access --dangerously-bypass-approvals-and-sandbox`，Grok 使用 `--always-approve`，Antigravity 使用 `--dangerously-skip-permissions --disable-slash-commands`。仅可在可信本地工作区、可信证据范围内运行；适配器的全权限不可替代任务提示中的禁止修改约束，仓库文本和工具输出也不能作为可执行指令。
- Grok headless **不**从 stdin 读 prompt：`to_grok` 写入临时 `--prompt-file`，调用结束后删除；评审结果取自单一 JSON 对象的 `text` + `sessionId`。Antigravity headless 由 `to_agy` 经 stdin 发送单行 UTF-8 NDJSON（`--input-format stream-json --output-format stream-json`），不将 prompt 放入 argv。
- reviewer 的最终回复必须自包含 verdict、findings 和证据；即使也写入指定 review 文件，也不能只回复文件路径或“已写入其他位置”。适配器机械要求标准 verdict（`APPROVE`、`APPROVE WITH NITS`、`REQUEST CHANGES`、`BLOCKED`）才会持久化为成功；findings 的完整性仍由提示约束、primary 复核。
- 并发安全的固定上限（marker 锁从 check 到 commit）：每个 artifact 最多 2 次新 attempt 和最多 2 次成功 review；新会话已启动后失败也消耗 attempt。Codex/Grok/ClaudeCode/Antigravity 原 gate 的显式超时续跑复用原 attempt，并逐段记录费用；已完成或非超时失败不能免费续跑。损坏计数或会话状态 fail closed。同一 marker 文件在整个 reviewer 调用期间持锁，因此共享该文件的不同 artifact gate 会串行；等待方没有独立获取锁超时，通常会等待当前调用的配置超时（默认 600 秒）及本地 I/O。
- `<marker-path>.lock` 是正常常驻的 flock 协调文件，不保存计数；它在正常结束后仍存在，并非 gate 正在运行或已失败的证据（not evidence of an active or failed gate）。将 marker 与 lock 放在忽略的 task-state 路径下；只有 marker JSON 损坏时才先保留证据、再手动删除 marker，gate 运行期间不要删除 lock。
- attempt 已持久化预留、且 reviewer 子进程尚未启动时，所有 adapter 都会向 stderr 输出一条脱敏的 `review_started` JSON；它只说明 gate 已开始，最终结构化结果仍在 stdout。
- 任何非成功 → fail closed 到**脱敏** durable handoff（含 handoff 文件名与成本日志字符串脱敏）；禁止递归互审。
- Codex 成功需真实 session/thread id + 真实非负 token 对，否则 fail closed；Grok 成功需真实 `sessionId` + `usage` token 对 + `stopReason=end_turn` + 带标准 verdict 的非空 `text`；Antigravity 成功需严格单 `init` 先于单 `result` + 一致 UUID `conversation_id` + `status=SUCCESS` + 非负整数 `usage.input_tokens/output_tokens` + 带标准 verdict 的非空 `response`；缺或非有限 USD 记 JSON `null`，绝不伪造 0。
- 只持久化经校验的非空 reviewer 输出；落盘前对已知 endpoint/token 值与密钥模式脱敏。

## 依赖

- 本机 reviewer CLI（按方向）：`claude -p ...` / `codex exec ...` / `grok --prompt-file ... --output-format json --always-approve` / `agy --input-format stream-json --output-format stream-json --dangerously-skip-permissions --disable-slash-commands`。Claude gate 用到 `--max-budget-usd`，需要支持所需 flag 的较新 `claude`；旧版本会 fail closed 并落 handoff。
- 无官方 Codex plugin 依赖（plugin 仅作可选 fallback，见 mapping reference）。
- Python 3.8+，仅用标准库。跨平台：POSIX 用 `fcntl`、Windows 用 `msvcrt` 做 marker 锁；两者都没有的平台 fail closed，而不是跳过串行化。
- 连续性契约：marker/成本日志为调用方指定的文件路径，可由任意 MRS/task-state 机制（如 `context-resilient-task`）满足；本 skill 不硬依赖它。
- 证据分类与缺失处理使用包内清单和协议；历史 play-book 本机路径只是可选出处，不是分发安装后的必读依赖。

## 验证与历史证据

- **2.5.0 源码验证（2026-11-26）**：全仓 `python3 tools/run_tests.py`（7 个 suite，含仓库约定、分发边界及 `tests/cross-agent-review/` 152 项确定性与真实子进程回归）及 `git diff --check` 通过。本机 macOS 完成两轮 **Antigravity primary → Codex reviewer** 真实设计评审 gate（`car-2.5.0-agy-design-r1` / `r2`），以及一次用户授权的 `agy 1.5.18`（`gemini-3.8-flash-low`）2 轮 `CLI-path verified (manual probe)`（验证 `stream-json` 输入/输出、`~/.gemini/antigravity-cli/conversations/<UUID>.db` 落盘及 `--conversation=<UUID>` 续跑）。`to_agy` 的真实 `timeout → native resume → success`、`adapter end-to-end first-use` 评审 gate、真实 `agy` 错误信封，以及 Linux/Windows/shim 实机运行均明确标记为 **pending**。

- **2.3.0 源码验证（2026-10-28）**：113 项技能测试及 8 项仓库约定通过；三向 runner 捕获的 prompt 风格契约断言先失败、修改共用 prompt 后通过。fresh-context 合成审核能输出独立风格状态、双侧依据，以及证据不足/纯文档分流。旧版在同一简单场景也发现偏离，不能宣称漏检率降低。集合内的 repository-code-style 另有合成对照记录；没有为风格状态增加机械结果校验。
- **2.3.0 ClaudeCode 真实只读审核（2026-10-28）**：用户授权 1200 秒 / USD 5，首次调用 241.986 秒完成，报告费用 USD 1.548766；结论 `APPROVE WITH NITS`、`Style consistency: PASS`，20 个受审文件保持不变。唯一非阻断项是基础清单继承的本机路径必读指令，随后已改为包内指引；这次文档修正经过本地检查，未再次付费复审，不把原 verdict 扩大为对修正后版本的复审结论。
- **2.2.0 源码验证（2026-10-19）**：113 项技能测试、8 项仓库约定检查及 `git diff --check` 通过。覆盖三向超时续跑、文件与会话绑定、attempt 复用、单次 success 提交、完成后拒绝续跑，以及 Codex 启动器/原生子进程终止。
- **Codex 真实本机验证**：macOS、`codex-cli 0.163.0`，首段 60.021 秒超时，原 UUID 续跑 111.935 秒完成；计数从 `attempts=1/successes=0` 变为 `1/1`，完成后再次续跑被拒绝且没有启动模型调用。这验证的是适配器生命周期，不代表独立跨 Agent 审核通过。
- **ClaudeCode 真实本机验证**：首段及原会话续跑均在约 60 秒超时，计数保持 `attempts=1/successes=0`；本次尚未真实验证续跑后的最终完成分支。Grok 的本次 2.2.0 续跑实现已通过确定性回归，尚未对本次源码完成真实模型验证。
- **平台边界**：Codex 真实调用验证在 macOS 进行；Windows 的 `taskkill` 超时与失败分支通过受控回归测试验证，未在 Windows 实机运行。审核发现的该清理分支问题在真实调用后修复，并重新通过完整回归。

适配器回归位于源码仓库的 `tests/cross-agent-review/`，自动触发量具与真实调用
验证说明位于 `evals/cross-agent-review/`。这些是维护资料，不属于安装后的运行依赖。
在源码仓库根目录运行当前回归：

```bash
python tools/run_tests.py
```

以下为历史证据，不能替代当前版本的验证：

- 历史 play-book 适配器单测 `124 passed` 及其他数字仅为 provenance；维护者应在源码仓库运行当前回归，实际 review gate 仍需在用户批准范围内验证。
- 端到端：正向 Claude adapter first-use PASS；2026-07-25 使用真实 `claude-cli/2.1.216` 子进程身份完成网关兼容 gate；Codex `codex exec` 直连 PASS。Grok 方向的历史依据是当时的源码单测 + 本机 `grok` headless 能力，安装后仍需各自做一次真实 gate 再宣称 e2e。
- 压力 A/B：with-skill 拒绝伪造 verdict 有明显 uplift。
- 真 installed-skill 自动触发量具（历史）：**正例 9/10、负例 10/10（0 误触发），19/20 确定、0 ambiguous**。
