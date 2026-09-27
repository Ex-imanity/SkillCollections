# AI 编码工作流 Skills 对比与选型建议

> 对比对象：OpenSpec、Superpowers、Mattpocock/skills（productivity）、planning-with-files、context-resilient-task
> 你当前的工作流：**superpowers + context-resilient-task（自定义）**
> 生成日期：2026-07-19

---

## 0. 结论先行（TL;DR）

1. **你现在的组合是对的，继续用。** superpowers（流程纪律）+ context-resilient-task（跨会话状态）刚好补足彼此最大的短板，且两者通过 `docs/plans/` 天然咬合。
2. **不要再加 planning-with-files。** 它和 context-resilient-task 是同一类东西，而你的 context-resilient-task 是它的"超集"（更严格、更结构化）。加了只会重复。
3. **可以补一个 grill-me/grilling（mattpocock）。** 它和 brainstorming 不是竞品而是互补——brainstorming 负责"发散生成方案"，grill-me 负责"收敛拷问方案"。成本极低，收益明确。
4. **OpenSpec 只在特定场景才换。** 它是 superpowers 前半段的"替代品"而非"补充"。只有当你开始做**团队协作 / 跨仓库需求 / 需要 spec 作为长期活文档留在仓库里**时才值得切过去。个人单仓开发，你现有的栈已经够。
5. **可以偷师一个点：** planning-with-files 唯一强过 context-resilient-task 的地方是**自动 hooks**（/clear 恢复、PreCompact 注入、Stop 门禁）。如果"上下文丢失"是你真实的痛点，把这套 hook 机制移植到 context-resilient-task 上，是性价比最高的升级。

---

## 1. 三个仓库速览

| 仓库 | 本质 | 交付形态 | 定位 |
|---|---|---|---|
| **Fission-AI/OpenSpec** | 规范驱动开发（spec-driven）**工具** | npm CLI + `/opsx:*` 斜杠命令 + `openspec/` 目录 | 让人和 AI 在写代码前先对齐"要建什么"，spec 作为活文档长期留存 |
| **obra/superpowers** | 一整套软件开发**方法论**（skill 库） | 十几个互相引用的 skill（无外部工具） | 把"头脑风暴→写计划→TDD 执行→评审→验收→收尾"的纪律编码成 skill |
| **mattpocock/skills** | 个人 skill **合集**（工程 + 效率） | 分类 skill（engineering/productivity/…） | 单点工具箱，可按需取用（grill-me、handoff、to-spec、tdd…） |

补充：**planning-with-files（OthmanAdi）** 与 **context-resilient-task（你的自定义）** 都不属于上面三个仓库，但它们是"任务状态持久化"这一类的两个代表实现，一并纳入对比。

---

## 2. 先分类：这些东西其实不在同一层

把它们混在一起比会很乱。它们分属**三个不同的层**：

```
┌─ 第一层：想法澄清（写代码之前）───────────────┐
│  brainstorming（发散/生成）  grill-me（收敛/拷问）  │
└──────────────────────────────────────────────┘
┌─ 第二层：全流程编排（怎么把活干完）──────────┐
│  OpenSpec        superpowers                      │
└──────────────────────────────────────────────┘
┌─ 第三层：状态持久化（别把活干丢了）──────────┐
│  planning-with-files      context-resilient-task  │
└──────────────────────────────────────────────┘
```

- **第一层**解决"想清楚没有"。
- **第二层**解决"流程走对没有"。
- **第三层**解决"/clear、崩溃、跨会话之后活还在不在"。

一个完整工作流通常需要三层各挑一个。你现在的组合正是：brainstorming（一层）+ superpowers 流程（二层）+ context-resilient-task（三层）。

---

## 3. 对比一：brainstorming vs grill-me

两者都在"写代码前把想法磨清楚"，但**气质完全相反**，是互补关系。

| 维度 | **brainstorming**（superpowers/obra） | **grill-me / grilling**（mattpocock） |
|---|---|---|
| 核心动作 | 协作对话，帮你把模糊想法变成设计/spec | 相亲式盘问，把你已有的计划/决策逐个逼问到底 |
| 气质 | 发散、生成、温和（"我们一起想"） | 收敛、对抗、犀利（"我来挑你毛病"） |
| 提问方式 | 一次一个问题，优先给选择题；提出 2-3 个方案+推荐 | 一次一个问题，**每个都给出它推荐的答案**；沿决策树逐支解决依赖 |
| 事实 vs 决策 | 先看项目现状再问 | **事实自己去查（文件/工具），只把"决策"抛给你** |
| 产出 | 分段（200-300 字）呈现设计→通过后写入 `docs/plans/YYYY-MM-DD-*-design.md` | 达成"共识"为止，**不产出固定文档**，达成共识前不动手 |
| 硬约束 | HARD-GATE：设计未获批准前禁止写任何代码 | 未确认达成共识前不 act |
| 触发方式 | 模型可自动触发（创造性工作前必用） | **用户显式调用**（`disable-model-invocation: true`） |
| 适用时机 | 从 0 到 1：还不知道要建什么、要探索方案 | 从 1 到 1.5：已经有草案，想压力测试有没有漏洞 |

**一句话：** 想法还是一团雾 → brainstorming；想法已成形但你心里发虚 → grill-me。
最佳用法是**串联**：先 brainstorming 生成设计草案，再 grill-me 把草案拷问一遍，最后才进入写计划。

> 注：mattpocock 里还有 `grilling`（模型可触发版）和工程区的 `grill-with-docs`（带文档的拷问）。`grill-me` 只是 `grilling` 的用户手动入口。

---

## 4. 对比二:OpenSpec / Superpowers / planning-with-files / context-resilient-task

这四个常被放一起比，但**其实是两两分组**（见第 2 节）：OpenSpec vs Superpowers 是"全流程编排"之争；planning-with-files vs context-resilient-task 是"状态持久化"之争。

### 4.1 全景对比表

| 维度 | **OpenSpec** | **Superpowers** | **planning-with-files** | **context-resilient-task** |
|---|---|---|---|---|
| 层级 | 全流程编排 | 全流程编排 | 状态持久化 | 状态持久化 |
| 形态 | 外部 CLI + 斜杠命令 | 纯 skill 方法论 | skill + **自动 hooks** | skill + Python 脚本 |
| 核心产物 | `openspec/changes/<name>/`：proposal.md、specs/、design.md、tasks.md | `docs/plans/*.md`（计划文档） | `task_plan.md`+`findings.md`+`progress.md`（项目根目录） | `.task-state/` MRS：分层文件（task_state/plan/snapshot + findings/progress/decisions） |
| spec 表达 | 需求+场景（WHEN/THEN），纯 Markdown | 无强制 spec 格式 | 无 spec 概念 | 无 spec 概念 |
| 流程 | explore→propose→apply→archive | brainstorm→writing-plans→executing/subagent→review→verify→finish | 建计划→做→回读→更新（循环） | 检测 MRS→重建状态→从检查点继续 |
| 纪律强项 | 结构由工具强制；spec 成为长期活文档 | **TDD + 代码评审 + 子代理执行**纪律最强 | 2-动作规则、3-击错误协议、错误不重复 | **防幻觉**（来源标注/显式未知/单步推进）、文件权限（in-place/append/overwrite 分明） |
| 跨会话/抗 /clear | 靠 spec 落盘（被动） | **弱**：计划是静态文档，无状态重建机制 | **强**：hooks 自动注入+/clear 后 session-catchup 恢复 | **强**：On-Invoke 主动重建"Reconstructed Task State" |
| 团队/跨仓库 | **强**：Stores（beta）把规划放独立仓库共享 | 弱（面向单人单仓） | 弱 | 有多任务/多代理（AGENTS.md 兼容）但非为团队设计 |
| 自动化程度 | 命令驱动（你敲命令） | 靠模型遵守 skill 纪律 | **hooks 自动触发+自动恢复** | 靠 skill 被调用（手动/触发词） |
| 上手成本 | 需装 npm 包、`openspec init` | 装 skill 即用 | 装 skill 即用，含 hooks | 已是你的自定义，零成本 |
| 最适合 | 需求先行、brownfield、团队协作、要留活文档 | 个人在 Claude Code 里做高纪律 SDLC | 长任务里"别把上下文搞丢" | 同上，且要更强结构+防幻觉+与其他 skill 咬合 |

### 4.2 OpenSpec vs Superpowers：两种哲学

- **OpenSpec = 工具强制结构 + spec 是一等公民。**
  spec/proposal/tasks 是实打实的文件，`archive` 后 spec 更新进 `openspec/specs/`，**成为仓库里长期演进的"真相源"**。优点：不依赖 AI 是否"守规矩"，结构由 CLI 保证；proposal 审批、跨仓库 Stores、brownfield 友好。代价：多一个外部工具和一套命令，前半段工作流被 opsx 接管。
  官方还给了对比定位：比 GitHub Spec Kit 更轻（无 Python、无刚性阶段门），比 AWS Kiro 更自由（不锁 IDE/模型）。

- **Superpowers = 方法论内化成 skill + 计划是过程产物。**
  没有外部工具，靠一串 skill 把 SDLC 纪律灌进来，**最大亮点是 TDD、代码评审（requesting/receiving）、子代理执行、验收前核查**这些"执行质量"环节，OpenSpec 反而较弱。代价：计划是一份静态 `docs/plans/*.md`，**没有跨会话状态重建**——这正是你要配 context-resilient-task 的原因。

### 4.3 planning-with-files vs context-resilient-task：同类，但你的更强

这俩是**同一物种**（文件系统当记忆：Context=RAM，Filesystem=Disk）。差异：

| | planning-with-files | context-resilient-task（你的） |
|---|---|---|
| 文件模型 | 3 文件平铺（task_plan/findings/progress） | **分层 MRS**（Tier 0 必须 / Tier 1 应有 / Tier 2 可选），职责更细 |
| 写入纪律 | 更新即可 | **文件权限分明**：task_state 就地改、progress 只追加、snapshot 整体覆盖、decisions 只追加；冲突时 task_state 为准 |
| 防幻觉 | 3-击错误协议、错误不重复 | **系统化防幻觉**：每条事实标来源、无信息标"Unknown"、不臆测、每次只推进一步 |
| 与其他 skill 集成 | 无 | **Plan Registry** 显式登记 `docs/plans/*.md`（正好接住 superpowers 的产物） |
| 多任务 | 单计划为主 | 支持一个项目多 MRS（并行/中断任务）+ 询问恢复哪个 |
| 工具化 | 脚本 + 模板 | init/verify/snapshot/list 等 Python 脚本 + 模板 |
| **自动 hooks** | **有且是杀手锏**：UserPromptSubmit / PreToolUse / PostToolUse / Stop / **PreCompact** 注入 + `session-catchup.py` 自动恢复 | **无**：靠 skill 被调用（这是你唯一的短板） |

**结论：** 结构、纪律、防幻觉、可组合性上，context-resilient-task 全面≥ planning-with-files；唯一被反超的是**自动化触发/恢复**。所以别替换，而是**把 planning-with-files 的 hook 思路移植过来**。

---

## 5. 针对你的建议

### 5.1 你现有的栈为什么是好搭配

- superpowers 的 `brainstorming` 和 `writing-plans` 都把产物写进 **`docs/plans/`**；
- context-resilient-task 的 **Plan Registry 恰好登记 `docs/plans/*.md`**，并在其上维护活状态与恢复。
- superpowers 最缺的就是**跨会话状态重建**，而这正是 context-resilient-task 的看家本领。

也就是说：**superpowers 管"怎么把活干对"，context-resilient-task 管"活别丢、随时能接上"**，二者几乎零重叠、天然互补。这个组合本身就很成熟，不用动大手术。

### 5.2 具体动作建议（按性价比排序）

1. **保持 superpowers + context-resilient-task 作为主干。** 无需替换。
2. **补 grill-me / grilling（mattpocock）。** 插在 `brainstorming` 之后、`writing-plans` 之前，用来拷问设计草案；也可用来压力测试 context-resilient-task 里的 `plan.md`。用户手动触发、零副作用，收益直接。
3. **给 context-resilient-task 加自动 hooks（偷师 planning-with-files）。** 如果你真实痛点是"/clear 或 compaction 后丢上下文"，加 `PreCompact` 注入 + `Stop` 门禁 + 会话追赶脚本，把"手动调用才恢复"变成"自动恢复"。这是对你自定义 skill 最值钱的一次升级。
4. **不要引入 planning-with-files。** 与 (3) 二选一——要么用它，要么把它的 hook 移植进你自己的 skill；两个同类 skill 并存会互相打架。
5. **OpenSpec 先观望、按项目试点。** 现在不用切。出现以下任一信号时再引入：
   - 开始**多人协作 / 跨仓库**做同一个需求；
   - 需要 spec 作为**长期活文档**留在仓库、可审阅可演进（而不是一次性计划）；
   - 发现 Claude 老是**不守 skill 纪律**、想要工具层强制结构。
   引入方式建议：挑一个"需求重、结构清"的项目单独试 `/opsx:explore → propose → apply → archive`，与主干并行评估，别一次性全量迁移。

### 5.3 什么时候该"换赛道"到 OpenSpec

| 你的处境 | 建议 |
|---|---|
| 个人、单仓、Claude Code 内高纪律开发 | **维持现状**（superpowers + context-resilient-task），最多加 grill-me |
| 团队协作 / 一个需求横跨多个仓库 | **认真评估 OpenSpec**（尤其 Stores），它的结构强制和共享 spec 是你现有栈给不了的 |
| 需求频繁变更、要可审阅的活规范 | **OpenSpec**，spec 作为真相源的模型更合适 |
| 痛点主要是"上下文老丢" | 不是换 OpenSpec，而是**强化 context-resilient-task 的 hooks** |

---

## 6. 建议的组合工作流（把上面拼起来）

```
① brainstorming（superpowers）          发散：把想法变成设计草案 → docs/plans/*-design.md
        ↓
② grill-me / grilling（mattpocock）      收敛：逐支拷问草案，堵漏洞（可选但推荐）
        ↓
③ writing-plans（superpowers）           把设计拆成 bite-sized 任务 → docs/plans/*.md
        ↓
④ context-resilient-task 登记 & 建 MRS   Plan Registry 收录上面产物 + 维护 .task-state/ 活状态
        ↓
⑤ executing-plans / subagent-driven      逐任务执行（superpowers，TDD + 频繁提交）
   （执行中：context-resilient-task 持续更新 progress/snapshot，/clear 后可重建）
        ↓
⑥ requesting/receiving code-review       评审（superpowers，作者与评审分离）
        ↓
⑦ verification-before-completion         验收核查（superpowers）
        ↓
⑧ finishing-a-development-branch         合并/PR/收尾（superpowers）
```

- **第 ②、③ 步之间**是最值得补 grill-me 的地方。
- **第 ④ 步贯穿全程**：它是你抗 /clear、跨会话的底座，若加了 hooks 则自动运转。
- 若某项目切到 **OpenSpec**：①②③ 由 `/opsx:explore → propose` 接管，⑤ 由 `/opsx:apply`，收尾由 `/opsx:archive`；⑥⑦⑧ 仍可保留 superpowers 的评审/验收纪律。

---

## 来源

- [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [obra/superpowers](https://github.com/obra/superpowers)
- [mattpocock/skills — productivity](https://github.com/mattpocock/skills/tree/main/skills/productivity)
- [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files)
- context-resilient-task：本地自定义 skill（`~/.claude/skills/context-resilient-task/`）
