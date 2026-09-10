# Changelog — context-resilient-task

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 1.6.0 - 2026-09-10

- `utils.md` 升级为**唯一资源注册表**：飞书文档、外部网页、本地进程、静态页面、接口、数据库、看板、工单等一律登记在同一张表，Type 为开放枚举并提供 `other:<label>` 逃逸口；其他 MRS 文件只按 ID 引用（`(res: R3)`），不再复制指针。
- 修复"登记了也看不见"：`utils.md` 区块改为 pinned，不再受 restore(3 段)/precompact(2 段) 的近期裁剪而静默丢段。
- 敏感度过滤从**整段丢弃**改为**按行丢弃**：单行 `restricted` 不再连带整张表消失；未标级别的行在同区块存在 `restricted` 时仍按 fail-closed 丢弃。
- 预算不足时保留表头 + 最早登记的行（登记顺序优先于新鲜度），并放宽 utils 摘要预算。
- `verify_mrs.py` 新增注册表校验：未知 Type、缺失 Sensitivity、缺少 `## Resource Registry` 表（旧布局）均告警，不改变退出码。
- 新增 `scripts/scan_resources.py`：扫描遗留 MRS 内已散落的指针，分类并生成注册表草稿（默认只读，`--write` 写入 utils.md）；可达资源排序优先于本地文件噪音，跳过"作为证据引用的源码文件"和容器目录，标注已失效的本地路径，保留 `file:line` 出处。
- 依据 16 个真实 MRS 的形态调整列语义：`Access` 显式容纳**读取命令/工具**，`Verified` 容纳**读到的版本**（如 `2026-09-07 (rev 607)`）；子资源清单挂 `## Notes` 不占行。
- 恢复输出的 `Current Artifacts` 改为列出 MRS 目录内**全部**文档（含 Tier 2 与自定义文件，如 `evidence-index.md`），归档快照除外 —— 此前它们在恢复时完全不可见。
- `verify_mrs.py` 新增 pinned invariants 采纳提示：长日志（decisions ≥10 条 / findings ≥20 条）若没有 pinned 条目则告警并给出实际回放比例（真实数据中 16 个 MRS 的采纳率为 0，qa-ai-search 的 106 条 decisions 只回放 3 条）。
### Grok 交叉审核修复（gate `crt-1.6.0-grok-20260910`，verdict REQUEST CHANGES → 已修）

- **P1** 凭据形态的条目一律不进摘要：`utils.md` 无任何 Sensitivity 标记时曾把 `scheme://user:pass@host`、`?token=…` 原样输出到 restore/precompact/snapshot；现在无论标什么级别都拦截，且 `verify_mrs.py` 判 invalid（要求删值而非仅不显示）。
- **P1** `scan_resources.py --write` 的草稿改为 `restricted`（原为 `internal`，与文档"留空待填"自相矛盾，会把未分类资源直接发布进"总是回放"的注册表）；指针内嵌凭据先脱敏为 `user:***@` 再落盘，并点名仍持有原始值的源文件。
- **P1** `--write` 的 Notes provenance 曾被插入模板 HTML 注释内部（不可见）且 `(none recorded)` 未清除；现在跳过整个注释块。
- **P2** 文档不再声称"完整回放整张注册表"：pinned 去掉的是近期裁剪悬崖，每条 1800 / 整体 4000 字符预算仍生效。
- 密钥检测收紧为"值必须像密钥"（含数字或符号且 ≥6 字符，或纯字母 ≥13 字符），避免 `Bearer credentials`、`token: token` 这类散文误报 —— 发射侧误报会**静默丢掉合法资源行**，比告警更危险；同时把 `受限` 等中文级别纳入已标注词汇。
- `verify_mrs.py` 新增：任何 MRS 文档（`findings.md` / `progress.md` / `decisions.md`…）含疑似凭据时告警，因为它们同样会被回放或提交。实测 16 个真实 MRS 中命中 1 例真阳性。
- 新增回归测试覆盖上述每个 P1/P2 形态。

### Grok 复审修复（gate `crt-1.6.0-postfix-grok-20260910`，verdict REQUEST CHANGES → 已修）

- **P1** 空用户名的 URL 凭据（`redis://:password@host`）此前既不脱敏也不拦截：`--write` 会把明文口令落盘，标 `internal` 时还会进摘要，且 `verify_mrs.py` 判 valid。现在写入前脱敏、发射侧拦截、校验判 invalid，三条路径都有回归测试。
- **P2** 探测器与校验器的正则漂移（`_state_probe` 缺 `\b`，与 `verify_mrs` 判定不一致，会静默丢掉校验认为健康的行）：两者现在共用 `_state_probe.has_sensitive_value` 一份实现，并有"校验器不得再持有第二份实现"的测试。
- **P2** 密钥判定从"正则位置编码"改为"捕获值 + 判定函数"，按语法强度分档：URL userinfo 位置任何真实值都算；`Bearer` 后除纯词皆算；`password:`/`token=` 需要值本身不透明。补上此前漏检的 `Passw0rd`、`P@ssw0rd`、`xoxb-`/`sk-proj-`/`glpat-` 等厂商前缀和 JWT。
- **P2** `README.md:47` 残留的"完整回放"表述已改。
- 误报治理（在 16 个真实 MRS 上实测）：`sk-` 前缀曾在 `task-breakdown`／`.task-state-*` 内部误命中（78 次），中文散文和 `rotation:` 也被符号规则误判 —— 加左边界、非 ASCII 值排除、值截断到首个反引号后，真实 MRS 命中从 13/16 降到 2 行，且两条都是真实 token 值。
- 校验提示措辞覆盖"文档 token"读法：可以是删值留名，也可以是把该资源登记进注册表。

### Grok 终审 nit 修复（gate `crt-1.6.0-postfix2-grok-20260910`，verdict APPROVE WITH NITS → nit 已清）

- `references/artifact-standards.md` 最后一处"always replayed"表述已改。
- `scan_resources.py` 的 `URL_RE` 会把 IPv6 主机截断（`postgres://u:p@[::1]:5432/db` → `…@[::1`），指针被写坏（口令未泄漏）；现在把 `[...]` 整体匹配，并有回归测试。
- 补上复合凭据键（`client_secret=`、`aws_secret_access_key=`、`refresh_token=`、`mytoken=`）、`Authorization: Basic` 和 PEM 私钥块的检测。
- 检测器的"值判定"经真实语料迭代收紧：keyword 档要求值是**单个不透明 token**（不含 `/`、`:` 等路径/句读符号），且"不透明"仅由数字或普通词汇不会出现的符号（`@!$^&*#?%+=~`）判定 —— `-`/`_`/`.` 不算。这消除了 `token-gated sync/delete`、`token: ~/.claude/settings.json`、`token authenticates`、`tenant-token record-list` 等散文误报。
- **有意保留的漏检**（已写入文档）：纯字母口令（`password: SuperSecretPass`）、含非 ASCII 字符的口令、含表格分隔符 `|` 的裸口令。纯字母值与散文不可区分，而误报会**静默丢掉合法注册行** —— 这正是本版本要消灭的失效模式，故宁漏勿误。
- 真实语料实测：32 例检测矩阵全通过；16 个真实 MRS 命中 4 行，全部为真实 token 值，`utils.md` 命中 0（无合法注册行被丢）。


- Tier 0 文件"存在但格式不合规"不再判定 invalid：接受手写 `**Timestamp:**` 快照头，缺区块降级为修复告警，并在文档中明确**修复而非重新初始化**（真实数据中有 1/16 的 MRS 因此被误判）。

## 1.5.0 - 2026-09-08

- 敏感度解析覆盖粗体字段、中文全角冒号、表格行和未知高风险等级，默认 fail-closed。
- 超长 snapshot 按区块压缩并保留恢复必需区块；统一 list/restore/precompact 的 MRS 新旧排序。
- 补充 4000 字符预算、敏感度和结构保留回归测试。

## 1.4.0 - 2026-09-08

- 修复超长 task state 导致 snapshot 丢失必需区块、restore 丢失 Next Action 的问题。
- 敏感度解析兼容 Markdown 粗体、等号和中文标签；`Pinned` 标记兼容模板写法。
- 统一 MRS recency 信号，确保单/多 MRS 输出预算与必需恢复字段同时满足。

## 1.3.0 - 2026-09-08

- 修复 restricted utils 混合条目泄露、HTML comment/fenced code 源行号错位和单 MRS 输出超限。
- 统一 restore/precompact 的 MRS 新旧排序，过滤模板脚手架，兼容 `Pinned: yes` 标记并修正嵌入标题层级。
- 修正文档中的 Tier 1 条目归属与 pinned invariants 说明。

## 1.2.0 - 2026-09-08

- 修复多 MRS 摘要无全局预算、历史日志读取文件头部、轮次后缀权威区块漏检等长对话恢复缺陷。
- 新增固定约束（`Invariants (pinned)`）优先恢复、utils 敏感度分级与疑似凭据校验。
- 快照中的嵌入条目降级为三级标题，并在 Tier 1 更新晚于快照时发出漂移告警。

## 1.1.0 - 2026-09-08

- 新 MRS 自动创建 `utils.md`，独立保存工具、环境、数据库/服务器、日志和本地资源指针。
- 恢复、压缩摘要和快照纳入 `decisions.md`、`findings.md`、`utils.md` 的最新有限条目，降低长对话遗忘风险。
- 验证器拒绝 `task_state.md` 中重复的 `Active Todos` / `Completed Items` 权威区块；旧 MRS 缺少 `utils.md` 仅告警。

## 1.0.0 - 2026-09-03

首个标注版本。此前变更见 git 历史，不追认为 release。

当前能力基线：

- 基于磁盘 MRS（`.task-state/`）的上下文弹性任务管理，跨 `/clear`、会话中断、agent 切换恢复任务状态
- `task_state.md` 为 source of truth 且原地更新；`progress.md` / `decisions.md` 仅追加
- 缺少 Tier 0 文件时先初始化 MRS
