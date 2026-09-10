# Changelog — context-resilient-task

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

条目只写**真实的修复与变更内容**。不写评审过程、评审结论、findings 编号或"已修/已清"这类过程状态 ——
读者要的是"这个版本改了什么"，评审记录属于 `Review/` 与 commit message。

## 1.6.0 - 2026-09-10

**资源注册表**

- `utils.md` 升级为**唯一资源注册表**：飞书文档、外部网页、仓库、本地路径、接口、数据库、日志平台、看板、本地进程、静态页、CLI/MCP 工具、工单、测试数据、凭据名称一律登记在同一张表；Type 为开放枚举并提供 `other:<label>` 逃逸口。其他 MRS 文件只按 ID 引用（`(res: R3)`），不复制指针。
- `utils.md` 区块改为 pinned，不再被 restore(3 段)/precompact(2 段) 的近期裁剪静默丢段；每条 1800 / 整体 4000 字符预算仍生效。
- 敏感度过滤由**整段丢弃**改为**按行丢弃**：单行 `restricted` 不再连带整张表消失；未标级别的行在同区块存在 `restricted` 时按 fail-closed 丢弃；`受限` 等中文级别计入已标注。
- 摘要预算不足时保留表头 + **最早登记**的行（ID 被其他文件引用，登记顺序优先于新鲜度），并放宽 utils 的摘要预算。
- 列语义：`Access` 容纳凭据名/角色/**读取命令或工具**，`Verified` 容纳日期 + **读到的版本**（如 `2026-09-07 (rev 607)`）；子资源清单（Base 表清单、文档章节）挂 `## Notes`，不占注册表行。

**凭据处理**

- 含凭据形态的条目**一律不进摘要**，与该行标注的级别无关；`verify_mrs.py` 判 invalid（要求删值，而非仅不显示）。覆盖 URL userinfo（含 `redis://:password@host` 这类空用户名）、查询参数 token、`Bearer`/`Basic`、复合键（`client_secret=`、`aws_secret_access_key=`、`refresh_token=`）、厂商前缀（`AKIA`、`ghp_`、`xoxb-`、`sk-`、`glpat-` …）、JWT 和 PEM 私钥块。
- 判定方式为"捕获值 + 按语法强度分档"：URL userinfo 位置任何真实值都算；`Bearer`/`Basic` 后除纯词皆算；`password:`/`token=` 要求值是单个不透明 token（不含路径/句读符号，且由数字或 `@!$^&*#?%+=~` 证明不透明）。探测器与校验器共用同一实现，不再各持一份正则。
- 已知且有意保留的漏检：纯字母口令、含非 ASCII 字符的口令、含表格分隔符 `|` 的裸口令。纯字母值与散文无法区分，而发射侧误报会静默丢掉合法注册行。
- `verify_mrs.py` 在任何 MRS 文档（`findings.md` / `progress.md` / `decisions.md` …）含疑似凭据或访问 token 时告警，因为它们同样会被回放或提交。

**遗留 MRS 迁移**

- 新增 `scripts/scan_resources.py`：扫描 MRS 内已散落的指针，分类并生成注册表草稿；默认只读，`--write` 才写入 `utils.md`。可达资源排序优先于本地文件噪音，跳过"作为证据引用的源码文件"和容器目录，标注已失效的本地路径，保留 `file:line` 出处。
- 草稿写为 `Sensitivity: restricted`：落盘但不进任何摘要，直到人工补齐用途/访问方式并改成真实级别。
- 指针内嵌的凭据在写入前脱敏为 `user:***@` / `?token=***`，并在输出中点名仍持有原始值的源文件；括号形式的 IPv6 主机不再被截断。

**恢复与校验**

- 恢复输出的 `Current Artifacts` 列出 MRS 目录内**全部**文档（含 Tier 2 与自定义文件，如 `evidence-index.md`、`test-observability.md`），归档快照除外；此前它们在恢复时完全不可见。
- Tier 0 文件"存在但格式不合规"不再判定 invalid：接受手写 `**Timestamp:**` 快照头，缺区块降级为修复告警，并在文档中明确**修复而非重新初始化**。
- `verify_mrs.py` 新增告警：注册表行 Type 未知、缺 Sensitivity、旧布局缺 `## Resource Registry` 表；长日志（decisions ≥10 条 / findings ≥20 条）没有 pinned 条目时给出实际回放比例。以上均不改变退出码。
- 新增回归测试覆盖上述各项行为。

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
