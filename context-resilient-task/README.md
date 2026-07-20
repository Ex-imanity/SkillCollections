# Context-Resilient Task — 上下文弹性任务管理

一个专为解决 AI 辅助开发中**上下文丢失**和**AI 幻觉**问题而设计的 skill。

## 解决的核心问题

在使用 AI 进行复杂多阶段开发任务时，常见痛点：

- **上下文丢失**：会话中断、`/clear` 后无法继续
- **记忆依赖**：切换 IDE 或会话后状态消失
- **AI 幻觉**：AI 编造不存在的文件、函数或状态
- **待办项遗忘**：明明已完成的任务，下次会话 AI 仍说未完成
- **孤儿计划文件**：`writing-plans` 产出的计划文件没被 MRS 追踪，recovery 时丢失上下文

**核心原则：Context is not input, it's output.**

永远不依赖对话记忆，始终从磁盘上的 artifacts 重建任务状态。

---

## 核心架构：三层 MRS (Minimum Recovery Set)

### Tier 0：核心必需（MUST exist）

| 文件 | 职责 | 更新方式 |
|------|------|---------|
| `task_state.md` | 当前状态 source of truth，**Active Todos 在头部** | **原地修改**，禁止追加 |
| `plan.md` | 任务计划 + Plan Registry（仅 `docs/plans/*.md`） | 原地修改阶段状态 |
| `snapshot.md` | 最新检查点快照 | 事件触发**覆写整个文件**，不追加 |

**失败模式：** 缺少任何 Tier 0 文件 → **停止**，运行初始化向导

### Tier 1：重要上下文（SHOULD exist）

| 文件 | 职责 | 更新方式 |
|------|------|---------|
| `findings.md` | 关键发现与技术决策 | **仅追加** |
| `progress.md` | 会话执行日志 | **仅追加** |
| `architecture.md` | 架构说明（系统级任务用） | 按需更新 |

**失败模式：** 缺少 → **警告**，降级模式恢复

> **decisions.md**：当项目为多会话、多 agent 或 >10 phases 时，`decisions.md` 升级为 Tier 1 必需文件。它承接稳定结论和设计决策，防止 `task_state.md` 因追加决策历史而失控膨胀。

### Tier 2：可选增强（MAY exist）
- `blockers.md` — 当前阻塞问题
- 领域特定文件（`api_design.md`、`database_schema.md` 等）

**失败模式：** 缺少 → **无影响**，继续工作

---

## 文件权威性规则

这是防止"待办项遗忘"和"状态不一致"的关键规则：

### task_state.md vs progress.md

- **`task_state.md`** = Source of truth。每次状态变化都**原地修改已有字段**，不追加新的日期段落。
- **`progress.md`** = Append-only 日志。每次行动追加一条记录，永不覆写。
- **`snapshot.md`** = 最新快照。每次**覆写整个文件**，不追加新段落。覆写前先归档旧版本。
- **`decisions.md`** = 稳定结论/决策。Append-only。这是"Latest Stable Conclusions"的正确归档地，不要放在 task_state.md 中。
- **两者冲突时，`task_state.md` 优先。**

> ⚠️ 常见错误：在 `task_state.md` 末尾追加 `## 2026-02-25 状态更新` 段落。这会导致同一条待办项在文件里出现多次，状态互相矛盾，AI 报告时拿到的是最早出现的"未完成"记录而不是后来的"已完成"记录。

### task_state.md 长度限制

当 `task_state.md` 超过 **300 行**时，AI 可能在 recovery 时只读到文件前半部分，导致忽略较新的状态更新。应当执行"压缩"操作：将已完成阶段的详细内容归纳为一行摘要，详细内容保留在 `progress.md` 中。

---

## 待办项管理

`task_state.md` 头部维护两个固定区块，是待办项的**唯一权威来源**：

```markdown
## Active Todos    ← 必须在文件头部（Status 之后），确保 recovery 第一时间读到
- [ ] 实现认证模块 (added: 2026-02-10, source: plan Phase 2)
- [ ] 编写单元测试 (added: 2026-02-10, source: user request)

## Completed Items
- [x] 设计数据库 schema (completed: 2026-02-10)
- [x] 搭建项目脚手架 (completed: 2026-02-11)
```

**操作规则：**
- 完成一个待办项 = 从 `Active Todos` 中**删除**该条目 + 追加到 `Completed Items`
- 查询待办状态时，只从 `Active Todos` 读取待处理项，只从 `Completed Items` 读取已完成项
- 永远不从 `progress.md` 推断待办状态，只读 `task_state.md`
- **每条待办限单行**。详细上下文引用外部文件（如 `see decisions.md 2026-02-10`），不内嵌子列表

---

## 任务生命周期

`task_state.md` 中的 `status` 字段追踪任务状态：

```
active → paused → active → completed
           ↘ blocked → active
```

| 状态 | 含义 | skill 行为 |
|------|------|-----------|
| `active` | 进行中 | 正常 recovery |
| `paused` | 暂停，可恢复 | 正常 recovery |
| `blocked` | 等待外部解决 | 正常 recovery，提示 blockers.md |
| `completed` | 已完成 | 跳过 recovery，提示归档 MRS |

当 skill 检测到 `status: completed` 时：
```
ℹ️  task_state.md status=completed

此任务已标记完成。选项：
1. 归档 MRS 到 .task-state/archive/
2. 开始新任务（重新初始化）
3. 重新打开任务（设为 active）
```

---

## 多 Skill 协作：Plan Registry

在使用 `writing-plans` / `brainstorming` 等 skill 过程中，`docs/plans/` 下会持续产出计划文件。若不追踪，这些文件会成为"孤儿文件"，recovery 时丢失上下文。

`plan.md` 底部必须维护一个 **Plan Registry** 表：

```markdown
## Plan Registry (docs/plans)

| 文件 | 来源 Skill | 创建日期 | 状态 |
|------|-----------|---------|------|
| 2026-02-13-migration-implementation.md | writing-plans | 2026-02-13 | completed |
| 2026-02-17-feature-x-design.md | brainstorming | 2026-02-17 | completed |
| 2026-02-24-ui-portal-implementation.md | writing-plans | 2026-02-24 | in_progress |
```

**严格边界 — 仅注册 `docs/plans/*.md` 文件。** 不得注册：
- `CLAUDE.md` / `AGENTS.md`（agent 自动加载）
- `.task-state/*`（MRS 文件自身）
- `docs/runbooks/*`（运维手册，非计划）

**状态值：** `pending` / `in_progress`（同时只有一个）/ `completed` / `abandoned`

**Handoff 协议：** 每当其他 skill 产出新的 `docs/plans/` 文件时，立即：
1. 在 Plan Registry 中注册该文件（`status: pending`）
2. 更新 `task_state.md` 的 Current Phase 指向该文件（如果它成为当前执行目标）
3. 生成一次 snapshot（事件触发）

详细协议见 [`references/multi-skill-integration.md`](references/multi-skill-integration.md)

---

## 推荐工作流

```
brainstorming → docs/plans/YYYY-MM-DD-design.md
                  ↓ 注册到 Plan Registry
writing-plans → docs/plans/YYYY-MM-DD-implementation.md
                  ↓ 注册到 Plan Registry，status=in_progress
context-resilient-task (init) → MRS 创建
                  ↓ 执行
[writing-plans 产出新计划]
                  ↓ 注册 + snapshot
context-resilient-task (recover) → 无缝恢复
finishing-a-development-branch → 合并/PR/清理
                  ↓ 设置 status=completed，归档 MRS
```

### 多任务并行 / 中断切换

当一个项目内同时存在多个独立任务时（例如同 repo 多个独立模块、或正在做的 feature 被高优任务中断），可使用兄弟目录命名让多个 MRS 共存：

```
project/
  ├── .task-state/                  # 默认任务（保持向后兼容）
  ├── .task-state-auth-refactor/    # 长期重构任务
  └── .task-state-bugfix-x42/       # 中断进来的紧急任务
```

关键规则：
- 默认 `.task-state/` 行为不变，旧项目无需迁移
- 新增任务用 `.task-state-<slug>/` 命名（slug 用 kebab-case 短标识）
- skill 调用时从 CWD 向上找 `.task-state/` 和 `.task-state-<slug>/`，多个时询问用户恢复哪个
- mtime 最新的会被标记为推荐，但永远不自动选择

典型使用：

```bash
# 中断场景：A 还在做，B 紧急插队
python <skill-root>/scripts/init_mrs.py \
    --dir .task-state-bugfix-x42 \
    --goal "修复鉴权绕过" --complexity small

# 列出当前 repo 内所有 MRS（含状态、最近更新时间）
python <skill-root>/scripts/list_mrs.py

# 任务完成后归档（保留可追溯）
mkdir -p .task-state/archive
mv .task-state-bugfix-x42 .task-state/archive/bugfix-x42-completed
```

完整工作流（命名约定、切换协议、归档模式、反模式）见 [`references/multi-task-workflow.md`](references/multi-task-workflow.md)。

### 目录结构

```
project/
  ├── docs/plans/              # brainstorming + writing-plans 输出
  │   ├── 2026-02-13-design.md
  │   ├── 2026-02-13-implementation.md
  │   └── ...（所有计划文件均在 Plan Registry 中注册）
  │
  ├── .task-state/             # MRS 目录
  │   ├── task_state.md        # 当前状态（原地修改，含 Active Todos）
  │   ├── plan.md              # 任务计划 + Plan Registry
  │   ├── snapshot.md          # 最新快照
  │   ├── findings.md          # 发现（仅追加）
  │   ├── progress.md          # 执行日志（仅追加）
  │   ├── decisions.md         # 设计决策（可选）
  │   ├── blockers.md          # 阻塞项（可选）
  │   └── archive/             # 已完成任务的归档快照
  │
  ├── .task-state-<slug>/      # 可选：并行任务的兄弟 MRS（同结构）
  │
  └── src/
```

---

## 快照触发时机

快照由**事件触发**，不按时间间隔生成：

| 触发事件 | 说明 |
|---------|------|
| 阶段完成 | 一个 plan Phase 状态变为 `complete` |
| 遇到 blocker | 任何导致工作停止的问题 |
| 重要决策 | 影响后续方向的技术/设计决策 |
| 新计划文件注册 | 其他 skill 产出新 docs/plans 文件 |
| 会话结束前 | 主动生成以保留当前进度 |

---

## 辅助脚本

脚本位于本 skill 的 `scripts/` 目录下：

### 初始化 MRS

```bash
# CLI 模式（全自动）
python <skill-root>/scripts/init_mrs.py \
  --dir .task-state \
  --goal "构建支付服务" \
  --complexity medium \
  --requirements "Stripe 集成;3DS 处理;Webhook 校验"

# 交互模式（省略 --goal/--complexity 时自动进入向导）
python <skill-root>/scripts/init_mrs.py
```

行为：
- 自动从 `assets/` 渲染 `task_state.md` / `plan.md` / `snapshot.md`
- 同时创建空的 Tier 1 核心日志 `findings.md` / `progress.md`，初始化后即可通过基础校验
- 当 `--complexity large` / `--multi-agent` / 需求数 > 10 时，自动创建 `decisions.md`
- 目标目录非空时拒绝写入，需 `--force` 显式覆盖
- 末尾提示用户将 `references/agents-md-snippet.md` 复制到项目 `AGENTS.md`

### 验证 MRS

```bash
python <skill-root>/scripts/verify_mrs.py .task-state
python <skill-root>/scripts/verify_mrs.py --json .task-state   # 结构化输出供 agent 消费
```

检查 Tier 0/1/2 完整性、文件格式、禁止路径。退出码：
- `0` = 完整有效
- `1` = 缺少 Tier 0（无法恢复）
- `2` = 缺少 Tier 1（降级模式）
- `3` = 格式验证错误

### 列出 MRS

```bash
python <skill-root>/scripts/list_mrs.py
python <skill-root>/scripts/list_mrs.py --json   # 结构化输出供 agent 消费
```

从当前目录向上发现 `.task-state/` 和 `.task-state-<slug>/`。如果存在多个 MRS，输出会按最近更新时间排序并标记推荐项，但 agent 仍需询问用户后再恢复。

### 生成快照

```bash
python <skill-root>/scripts/generate_snapshot.py .task-state
python <skill-root>/scripts/generate_snapshot.py .task-state --project-root .   # 显式指定源码扫描根目录
python <skill-root>/scripts/generate_snapshot.py --archive .task-state   # 同时归档
```

> 所有脚本均从 `assets/` 读取模板，因此渲染出的 MRS 文件始终与文档化的 schema 保持一致。对 `.task-state` 或 `.task-state-<slug>` 生成快照时，默认扫描其父目录作为项目根目录；也可用 `--project-root` 显式指定。

---

## 自动 Hooks（自动上下文恢复）

前面的脚本都要"记得手动跑"。自动 hooks 让 agent 在**关键时刻自动**重建 / 落盘 / 自检 MRS,无需手动调用。三个脚本全部**只读、非阻塞(exit 0)、无 `.task-state/` 时静默**,所以一次全局安装对所有项目都安全。

| 触发时机 | 脚本 | 效果 |
|---------|------|------|
| 会话开始 / `/clear` 后 | `restore_context.py` | 打印 "Reconstructed Task State",让新上下文一开始就有状态 |
| 上下文压缩前 | `precompact_digest.py` | 打印生存摘要,供压缩摘要器保留要点(完整状态已在磁盘) |
| 回合结束(`Stop`) | `gate_check.py` | 工作区漂移超过上次快照时**提醒**补 `snapshot.md` / `progress.md`(从不拦截) |

### Claude Code —— 一键安装

```bash
SKILL=~/.claude/skills/context-resilient-task   # 换成你的实际安装路径

# 全局安装(推荐):写入 ~/.claude/settings.json,所有项目生效
python <skill-root>/scripts/install_hooks.py

# 项目级:写入 ./.claude/settings.json(可随仓库提交)
python <skill-root>/scripts/install_hooks.py --project

# 预览(不写入) / 卸载
python <skill-root>/scripts/install_hooks.py --dry-run
python <skill-root>/scripts/install_hooks.py --uninstall
```

安装器**合并**进现有 `settings.json`(保留你其他的 key 和 hook)、**幂等**(重复运行不重复)、**原子写入**、遇到非法 JSON **拒绝写入不覆盖**;卸载时只精确移除自己的条目(靠 `--tag crt-auto-hook:<Event>` 标记),即使与你的 hook 同组也只删自己那条。

> 移动或重装 skill 后请重跑安装器,让内嵌的绝对脚本路径指向新位置(重跑安全,会原地刷新)。

### Codex —— 一键安装

```bash
# 写入当前项目 ./.codex/hooks.json
python <skill-root>/scripts/install_hooks.py --codex

# 预览(不写入) / 卸载本 skill 安装的 hooks
python <skill-root>/scripts/install_hooks.py --codex --dry-run
python <skill-root>/scripts/install_hooks.py --codex --uninstall
```

安装器会合并现有 `.codex/hooks.json`、保持幂等、原子写入，并只卸载带
`crt-auto-hook:<Event>` 标记的自身条目。它安装 `SessionStart`、`PreCompact` 和
`Stop` 三个原生 hook；Codex 会在首次执行前要求信任/审核新增定义。

### 其他 Agent(Gemini 等)

它们通过指令文件接同一批脚本:把 [`references/agents-md-snippet.md`](references/agents-md-snippet.md) 里的**自动上下文恢复**段落复制进项目 `AGENTS.md`(或 `GEMINI.md`),指示 agent 在**会话开始**跑 `restore_context.py`、**结束前**跑 `gate_check.py`。Codex 请使用上面的原生安装器；**不要**用 `notify`(它只在回合结束后触发)。

### 跨平台

生成的命令**不含任何 shell 专用操作符**,同一条命令在所有 Claude Code 可能使用的 shell 下都能跑:

- **macOS / Linux**:`sh -c`
- **Windows**:优先 Git Bash(POSIX);无 Git Bash 时回退 PowerShell 也能跑(用裸启动器 `python` 作命令名 + 脚本路径作带引号参数)

要求:非交互 shell 的 PATH 里要有 `python3`(POSIX)/ `python`(Windows);脚本仅用标准库,任意 Python ≥ 3.8 均可。Windows 无 Git Bash 且 hook 异常时,装 Git for Windows 并在 `~/.claude/settings.json` 设 `CLAUDE_CODE_GIT_BASH_PATH`。

完整说明见 [`references/hooks-setup.md`](references/hooks-setup.md)。

---

## 安装

将 skill 目录复制到你的 agent skills 目录（各平台路径不同）：

| 平台 | 推荐路径 |
|------|---------|
| Cursor | `~/.cursor/skills/` |
| Claude Code / Codex | `~/.agents/skills/`（统一约定） |
| 自定义 | 任意路径，配置 skills 目录即可 |

---

## 多 Agent 兼容性（Codex 等）

如果你的项目同时使用 Claude Code 和 Codex（或其他 agent），初始化 MRS 时需要额外一步：

将 [`references/agents-md-snippet.md`](references/agents-md-snippet.md) 的内容复制到项目根目录的 `AGENTS.md` 中。这确保所有 agent 都遵守相同的 MRS 更新规则。

---

## 使用方法

### 启动新任务

```
/context-resilient-task

我需要从 0 到 1 构建一个 Dify 工作流，包括设计节点、编写 DSL、测试验证...
```

skill 自动检测目录中是否有 MRS，无则初始化，有则恢复。

### 恢复已有任务

```
/context-resilient-task

继续之前的测试用例生成工作
```

skill 读取 `task_state.md`，从 `Active Todos` 和 `Next Action` 中还原工作状态。

### 任务完成后

完成工作时，在 `task_state.md` 中将 `status` 改为 `completed`，下次调用 skill 时会提示归档 MRS。

---

## 最佳实践

**DO:**
- `task_state.md` 原地修改字段，Active Todos 保持在头部
- 稳定结论/决策追加到 `decisions.md`，不追加到 `task_state.md`
- 每次行动后追加一条记录到 `progress.md`
- `snapshot.md` 每次**覆写整个文件**，不追加段落
- 每当其他 skill 产出计划文件时，立即注册到 Plan Registry
- 完成待办项时从 Active Todos 移走，追加到 Completed Items
- `task_state.md` 超过 300 行时主动压缩

**DON'T:**
- 依赖对话记忆恢复状态
- 在 `task_state.md` 中追加"Latest Stable Conclusions"等开放式增长段落
- 在 `snapshot.md` 中追加新的 `## Context` 段（应覆写）
- 把已完成的待办项留在 Active Todos 里打勾
- 从 `progress.md` 推断待办状态
- 把非计划文件注册到 Plan Registry（CLAUDE.md, AGENTS.md, runbooks 等）
- 将 MRS 文件放在 `/.cursor/`、`/tmp/`、`/.cache/` 等临时目录
- 中途重命名 MRS 文件

---

## 故障排除

### 待办项状态被"遗忘"

**症状：** 明确完成过的任务，下次 AI 仍报告为未完成。

**原因：** `task_state.md` 已超过 300 行，AI 只读到文件前半段，找到的是早期的"未完成"记录，而后期的"已完成"更新被截断忽略。

**解决：**
1. 检查 `task_state.md` 是否有多处记录同一待办项
2. 将文件压缩至 300 行以内
3. 确保 Active Todos / Completed Items 是唯一的待办状态来源

### MRS 文件未找到

**症状：** `❌ MRS INCOMPLETE - Recovery impossible`

**解决：** 确认工作目录正确（应在包含 `.task-state/` 的项目根目录），重新运行 skill。

### 快照过旧警告

**症状：** `⚠️ snapshot.md is N days old`

**解决：** 在项目目录运行 `python <skill-root>/scripts/generate_snapshot.py .` 生成新快照。

---

## 参考文件

| 文件 | 内容 |
|------|------|
| [`references/artifact-standards.md`](references/artifact-standards.md) | 文件格式规范、待办项管理规则、验证规则 |
| [`references/minimum-recovery-set.md`](references/minimum-recovery-set.md) | MRS 三层完整定义 |
| [`references/output-template.md`](references/output-template.md) | 结构化输出模板规范 |
| [`references/recovery-workflow.md`](references/recovery-workflow.md) | 完整恢复流程 |
| [`references/multi-skill-integration.md`](references/multi-skill-integration.md) | Plan Registry 格式、跨 Skill Handoff 协议 |
| [`references/multi-task-workflow.md`](references/multi-task-workflow.md) | 多任务并行的命名、切换、归档协议 |
| [`references/agents-md-snippet.md`](references/agents-md-snippet.md) | 可嵌入 AGENTS.md 的精简版 MRS 规则（Codex 兼容 + 自动上下文恢复指令） |
| [`references/hooks-setup.md`](references/hooks-setup.md) | 自动 Hooks 的安装、跨平台与设计说明 |
| [`assets/task_state.template.md`](assets/task_state.template.md) | task_state.md 初始化模板（含字段说明） |
| [`assets/plan.template.md`](assets/plan.template.md) | plan.md 模板（含 Plan Registry / Reference Index 骨架） |
| [`assets/snapshot.template.md`](assets/snapshot.template.md) | snapshot.md 模板（覆写式） |
| [`assets/decisions.template.md`](assets/decisions.template.md) | decisions.md 模板（仅追加） |
| [`scripts/init_mrs.py`](scripts/init_mrs.py) | 初始化 MRS（CLI + 交互向导） |
| [`scripts/verify_mrs.py`](scripts/verify_mrs.py) | 验证 MRS 健康度（支持 `--json`） |
| [`scripts/list_mrs.py`](scripts/list_mrs.py) | 发现并列出当前 repo 内所有 MRS |
| [`scripts/generate_snapshot.py`](scripts/generate_snapshot.py) | 从当前状态生成 snapshot |
| [`scripts/restore_context.py`](scripts/restore_context.py) | 自动 hook:会话开始/`/clear` 后重建任务状态 |
| [`scripts/precompact_digest.py`](scripts/precompact_digest.py) | 自动 hook:压缩前打印生存摘要 |
| [`scripts/gate_check.py`](scripts/gate_check.py) | 自动 hook:结束前漂移提醒(非阻塞) |
| [`scripts/install_hooks.py`](scripts/install_hooks.py) | 安装 Claude Code 或 Codex 的上述 hook |

---

**设计理念：** Context is not input, it's output.
