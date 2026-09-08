# SkillCollections

个人维护的 Agent Skills 合集，用于沉淀可复用的工作流、测试设计方法、上下文恢复机制和 Dify DSL 编排经验。

这个仓库的定位不是一个单一应用，而是一组可独立安装、按需触发的 skill。每个 skill 目录通常包含：

- `SKILL.md`：skill 的触发条件、执行流程、输出规范和注意事项，是 agent 读取的主入口。
- `README.md`：面向人的使用说明。不是所有 skill 都已有 README。
- `references/`：可按需加载的长文档、模式库、规则说明或补充材料。
- `assets/`：模板、默认风格样例或初始化资源。
- `scripts/`：可复用的脚本工具，优先让 agent 调用脚本而不是手写重复逻辑。
- `examples/`：示例文件或可参考的产物。
- `tests/`：脚本或关键逻辑的测试用例。

## 目录结构

```text
.
├── case-design-strategy-skill/
│   ├── SKILL.md
│   └── references/
├── case-lite/
│   ├── README.md
│   ├── SKILL.md
│   ├── assets/
│   ├── references/
│   └── scripts/
├── context-resilient-task/
│   ├── README.md
│   ├── SKILL.md
│   ├── assets/
│   ├── docs/
│   ├── references/
│   ├── scripts/
│   └── tests/
├── cross-agent-review/
│   ├── README.md
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
├── dify-dsl-generator/
│   ├── SKILL.md
│   ├── examples/
│   └── references/
├── gapm-mcp-recovery/
│   ├── README.md
│   ├── SKILL.md
│   ├── evals/
│   └── scripts/
├── internal-api-cookie-auth/
│   ├── SKILL.md
│   ├── scripts/
│   └── tests/
└── docs/
    └── plans/
```

## Skills 总览

| Skill | Version | 作用 | 适用场景 | 主要注意事项 |
| --- | --- | --- | --- | --- |
| `case-design-strategy-skill` | 1.0.0 | 测试用例设计策略层，用于补强覆盖度、评审场景和设计边界/异常/权限/埋点等测试点 | 需求用例评审、覆盖度补充、事件埋点校验、跨端一致性风险分析 | 它不是端到端用例生成器；如果已经进入 `case-lite` 主流程，只在自检或覆盖度评审阶段借用其策略，不覆盖 `case-lite` 的产物格式和写回规则 |
| `case-lite` | 1.1.0 | 小需求测试用例生成流程，从飞书文档选章到生成用例，再可选写回搬山 | 单一功能点、1-2 篇文档、无需模块拆分的小需求用例生成 | 依赖飞书文档 MCP；搬山 MCP 推荐配置；所有阶段产物必须落盘到 `case-lite-output/{slug}/`，章节选择和补充信息确认是人工检查点 |
| `case-reorganize` | 1.0.0 | 将搬山中已有测试用例整理为链路 case：合并冗余用例、去除边界 case、将串联操作合并为一个场景 | 已有用例过碎、需要按业务链路重组；整理后替换原 case 或追加到目标 case | 与 `case-lite` 的区别是输入来自搬山已有用例而非文档；写回前必须 dry-run；替换模式会调用 `deleteNode` 级联删除且**不可逆**，执行前务必确认；其 `full.md` 格式保留「前置条件」独立节点，与 `case-lite` 不同 |
| `context-resilient-task` | 1.5.0 | 上下文弹性任务管理，用磁盘上的 MRS 文件恢复长期任务状态 | 多阶段开发、跨会话继续、`/clear` 后恢复、避免 agent 忘记待办或编造状态 | `task_state.md` 是 source of truth；`progress.md` / `decisions.md` 只追加，`utils.md` 独立保存工具/环境/资源指针；恢复输出有 4000 字符预算；缺少 Tier 0 文件时应先初始化 MRS |
| `cross-agent-review` | 2.1.0 | 本机 Codex / ClaudeCode / Grok 互做跨代理评审：primary 保连续性与修复，reviewer 返回带证据的 verdict | 跨代理评审 handoff：任一 primary 请另一 peer 审计划/代码；防作者自漏 | 依赖本机 `claude`/`codex`/`grok` 中实际调用的 reviewer CLI；fail-closed、并发 round-cap、脱敏；readiness 看真实信封；不用于单 agent 自审或普通 code review |
| `dify-dsl-generator` | 1.0.0 | 生成、重构或评审 Dify workflow/chatflow/agent DSL | 把业务需求、后端接口、规则系统或已有 YAML 转为可导入的 Dify DSL | 先冻结输入输出和应用形态，再写 YAML；优先复用 `references/` 和已有示例中的验证模式；输出前检查节点类型、变量路径、edge 和结构化输出 |
| `gapm-mcp-recovery` | 1.0.0 | 诊断并恢复 Codex 中的 GAPM MCP；当前对话未注入 Tool 时可通过 App Server bridge 直接调用 | GAPM Tool 缺失、`invalid_client` / `authentication_required`、`serverInfo` 为空、日志排查疑似需要重启 Codex | 依赖 Codex CLI、Python 3.9+ 和内部网络；OAuth 过期仍需浏览器授权；参数及原始日志只能放在 `.local/`；查询无结果不能断言未调用 |
| `internal-api-cookie-auth` | 1.0.0 | 为受支持内部 API 获取短期 CAS Cookie，并规范认证失败后的处理 | Internal AD/UOS、Athena、Compass 的接口开发与排障，Cookie 缺失或 HTTP 401 | 仅限允许的内部域名；不输出或持久化凭证；403 视为可能的权限问题，禁止盲目重试写操作 |

## 各 Skill 简介

### case-design-strategy-skill

这是一个测试设计策略 skill，强调覆盖深度、颗粒度稳定、可观测断言和风险披露。它适合在已有需求、技术方案、交互说明或埋点表的基础上，帮助 agent 设计或评审测试点。

重点覆盖：

- 功能路径、边界、异常、权限、状态切换和恢复场景。
- APP、WEB、后端/API、跨端一致性等不同域的测试角度。
- 埋点事件的触发、不触发、参数契约、去重和证据路径。

注意：它主要是策略层，不负责飞书文档读取、搬山写回或完整 case-lite 流程。

### case-lite

`case-lite` 面向小需求测试用例生成，核心理念是精准输入：用户先选择飞书文档中的相关章节，agent 再基于选定语料生成场景结构和完整用例。

典型流程：

1. 收集需求名称、飞书文档链接和文档类型。
2. 展示章节树，由用户手动选择纳入范围。
3. 统一确认补充信息。
4. 生成 `structure.md` 并等待审核。
5. 生成 `full.md` 并等待审核。
6. 可选执行 agent 自检补漏。
7. 可选写回搬山测试平台。

主要产物保存在 `case-lite-output/{slug}/`，包括章节树、选定语料、参考用例、场景结构、完整用例、自检结果和写回日志。

### case-reorganize

`case-reorganize` 处理的是**已经存在于搬山的用例**，把过碎的用例整理成按业务链路组织的
case：合并冗余用例、去除意义不大的边界 case、把本就该串联执行的操作收敛成一个场景。

它与 `case-lite` 的输入端完全不同——`case-lite` 从飞书文档生成新用例，`case-reorganize`
从搬山已有用例读取再重组。两者的 `full.md` 格式也不一致：`case-reorganize` 保留「前置条件」
作为独立节点，串联在测试点与执行步骤之间，不可省略。

写回支持两种模式：追加到目标 case，或替换原 case。**替换模式会调用 `deleteNode` 级联删除
原有场景节点，不可逆**，执行前必须确认。与 `case-lite` 一样，写回前必须先 dry-run 校验节点数。

### context-resilient-task

`context-resilient-task` 用 MRS（Minimum Recovery Set）把任务状态写到磁盘，避免复杂任务在会话中断、上下文压缩、agent 切换后无法继续。

核心文件：

- `task_state.md`：当前状态和待办的唯一权威来源。
- `plan.md`：任务计划和 `docs/plans/*.md` 的 Plan Registry。
- `snapshot.md`：最新恢复快照。
- `findings.md` / `progress.md` / `decisions.md`：发现、执行日志和稳定决策。
- `utils.md`：开发工具、数据库/服务器、日志和本地资源指针；按敏感度分级，不记录密钥值。

恢复会优先保留 pinned invariants 和最新有限上下文；单 MRS 与多 MRS 输出均限制在 4000 字符内。

注意：不要依赖聊天记录恢复任务；恢复时应从 `.task-state/` 或 `.task-state-<slug>/` 读取事实。多任务并行时使用不同的 MRS 目录隔离状态。

### cross-agent-review

`cross-agent-review` 让本机 AI CLI agent（Codex、ClaudeCode、Grok）互相做跨代理评审：任一 agent 作为 primary 产出计划/代码，调用**另一个** agent 做带证据的 review，primary 保留连续性与修复责任。三角对称、去插件依赖；只依赖本机实际调用的 `claude` / `codex` / `grok` CLI。

仓内直连适配器（统一 `to_<peer>` reviewer 桥）：

- `scripts/to_claude.py` → `claude -p`（任意 primary → ClaudeCode）
- `scripts/to_codex.py` → `codex exec` 全权限无确认（任意 primary → Codex）
- `scripts/to_grok.py` → `grok --prompt-file` headless + `--always-approve`（任意 primary → Grok）

官方 Codex plugin 仅作 Codex 评审的可选 fallback。

核心保证：

- readiness 由真实结果信封判定，绝不用 auth-status 命令；任务契约禁止 reviewer 改 primary 工件（子进程为非交互放行工具权限，仅可信工作区使用）。
- 并发安全的固定 round/attempt cap（marker 锁）；已启动失败也消耗 attempt；任何非成功 fail closed 到脱敏 durable handoff。
- Codex 成功需真实 `thread_id`+`usage`；Grok 成功需真实 `sessionId`+带 verdict 的 `text`；缺/partial USD 记 `null` 不伪造 0。

验证：以本 bundle `tests/` 为准；历史 play-book 数字仅为 provenance。Grok 方向需在本机再跑一次真实 gate 后再宣称 e2e。

注意：不用于单 agent 自审、普通 code review 或认证排障；每个 review gate 需显式传入 request/artifact key/可读目录/输出路径/超时/用户批准的单次预算。

### dify-dsl-generator

`dify-dsl-generator` 用于把需求、接口、规则流程或已有 Dify YAML 转换为更稳定、可导入、可维护的 Dify DSL。

该 skill 参考 [wwwzhouhui/skills_collection 的 dify-dsl-generator](https://github.com/wwwzhouhui/skills_collection/tree/main/dify-dsl-generator) 二次开发调整而来，并结合本仓库的 Dify 迁移经验补充了本地验证模式和注意事项。

它强调先设计再输出：

- 先确定 app 类型：`workflow`、`advanced-chat` 或 `agent-chat`。
- 冻结输入变量、阶段输出和下游机器可解析字段。
- 选择最简单可维护的节点组合，例如 `llm`、`code`、`http-request`、`if-else`、`iteration`、`end`。
- 输出前校验 frontmatter、version、变量引用、value selector、edge、文件输入和结构化输出。

注意：Webhook、vision files、structured output 和复杂迁移流程是高风险区域，应优先参考 `references/` 和 `examples/` 中已有模式。

### gapm-mcp-recovery

`gapm-mcp-recovery` 用于恢复 Codex 中的 `gapm_agent_tools`。它不会把
`codex mcp list/get` 的 `enabled` 或 `OAuth` 字样误判为服务健康，而是进一步检查 App
Server 的 `serverInfo` 和三个 GAPM Tool 是否完整枚举。

当 MCP 已健康但当前对话没有原生 `gapm_*` Tool 时，内置脚本可以创建临时只读 thread，
通过 `mcpServer/tool/call` 直接查询 GAPM，从而避免为了刷新 Tool 快照而频繁重启 Codex 或
新开对话。OAuth 失效时优先重新登录，浏览器授权完成后再次检查真实状态。

该 Skill 只允许调用三个 GAPM 只读查询 Tool，参数和原始结果必须保存在 Git 忽略的
`.local/`，不会调用 `mainSearch` 或修改生产数据。详细安装、状态含义和 bridge 用法见
`gapm-mcp-recovery/README.md`。

### internal-api-cookie-auth

`internal-api-cookie-auth` 解决内部 HTTPS 接口调用时的 CAS 认证问题，避免每次都让用户手动
粘贴 session Cookie。适用于脚本或服务缺少 Cookie、会话过期、被重定向到 `cas.baijia.com` /
`test-cas.baijia.com`、返回 HTTP 401 或 CAS 风格的 JSON code 700 等情况。

它也覆盖另一个常见场景：用户从浏览器复制了一段 `copy as cURL`。此时不应照搬粘贴过来的
Cookie，而是用新鲜 Cookie 加最小必要 header 重新组装请求——命令、bash 或 Python 形式均可。
对 POST/PUT/PATCH/DELETE 这类有副作用的请求，重放前必须先向用户确认。

适用域名限定在 `internal-ad.gaotu100.com`、`athena.baijia.com`、`dis.baijia.com` 及其
`test-` 前缀版本。凭证不输出、不持久化。未知域名只有在用户明确授权做只读探测后才可尝试；
HTTP 403 应视为可能的权限问题，而不是"刷新 Cookie 就能解决"的信号，禁止盲目重试写操作。
详细流程见 `internal-api-cookie-auth/README.md`。

## 安装与使用建议

可以按需复制单个 skill 目录到本地 agent 的 skills 目录，也可以通过支持 GitHub skill 安装的工具安装整个仓库。

```bash
# 示例：手动安装单个 skill
cp -r case-lite ~/.cc-switch/skills/case-lite
cp -r context-resilient-task ~/.cc-switch/skills/context-resilient-task
cp -r gapm-mcp-recovery ~/.codex/skills/gapm-mcp-recovery
```

使用建议：

- 修改 skill 行为时，优先编辑对应目录下的 `SKILL.md`，并同步更新相关 `README.md` 或 `references/`。
- 长篇规则放在 `references/`，让 `SKILL.md` 只保留触发条件、关键流程和必须遵守的约束。
- 可执行流程尽量沉淀到 `scripts/`，减少 agent 每次手写逻辑带来的不稳定。
- 涉及外部系统的 skill 要明确依赖，例如 MCP 配置、认证方式、降级路径和写回风险。
- 如果新增 skill，建议至少包含 `SKILL.md`，并在本 README 的总览表中补充入口说明。

## 维护注意事项

- 保持 skill 边界清晰：流程型 skill 负责端到端步骤，策略型 skill 只提供评审和设计方法。
- 不要让多个 skill 对同一产物格式提出冲突要求。组合使用时，以当前主流程 skill 的输出格式为准。
- 示例、模板和脚本最好能独立运行或被快速验证，避免只停留在 prompt 描述。
- 对外部平台的写回操作应保留 dry-run、日志或可复查产物。
- 根目录 README 只做导航和简述，细节放回各 skill 自己的 README 或 references。

## 版本与变更日志约定

每个 skill 都要标注版本号并维护变更日志，方便使用者判断手上装的副本是否落后于仓库。

**三处必须一致**（由 `tests/test_repo_conventions.py` 机械校验，新增 skill 自动纳入）：

| 位置 | 角色 |
| --- | --- |
| `<skill>/SKILL.md` frontmatter 的 `version` | **唯一真相**。安装出去的副本靠它自报家门 |
| `<skill>/CHANGELOG.md` 顶部条目 | 变更明细，必须与 frontmatter 版本一致，条目从新到旧 |
| 根 README「Skills 总览」表的 Version 列 | 一览用 |

**变更日志放独立 `CHANGELOG.md`，不要放进 `SKILL.md`。** SKILL.md 每次触发都会被完整
加载进上下文，而变更日志只增不减且对 agent 执行任务毫无用处——放进去等于给每一次调用
都上一道永久递增的 token 税。

**版本语义按「对使用者坏了什么」判定**，不套代码 semver 的直觉：

- **MAJOR** — 已有产物或用法失效，需要迁移（如产物目录结构不兼容、工作流步骤移除）
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调 prompt 措辞，行为不变

**规则是「版本与日志同进退」**：不是每个 commit 都要升版本，但**每次升版本必须留下日志
条目**。这比判定「什么算重大更新」更好执行，也不会让日志出现空洞。

新增 skill 时：frontmatter 写 `version: 1.0.0`，建 `CHANGELOG.md` 并写首条 `## 1.0.0 - <日期>`，
在总览表补一行。跑 `python3 -m pytest tests/ -q` 确认。
