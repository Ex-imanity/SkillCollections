# Context-Resilient Task - 上下文弹性任务管理

一个专为解决 AI vibe coding 中**上下文窗口限制**和**幻觉问题**而设计的 Claude Code skill。

## 🎯 解决的核心问题

在使用 AI 进行复杂的多阶段开发任务时，你是否遇到过：

- 🔄 **上下文丢失**：会话中断、`/clear` 后无法继续之前的任务
- 🧠 **记忆依赖**：依赖对话历史，无法跨 IDE 或跨会话恢复工作
- 💭 **AI 幻觉**：AI 编造不存在的文件、函数或配置
- 📂 **状态混乱**：任务进度只存在于对话中，切换会话后从头开始

**本 skill 的解决方案：将上下文从输入变为输出。**

> **核心原则：Context is not input, it's output.**
> 永远不依赖对话记忆，始终从磁盘上的 artifacts 重建任务状态。

## 🏗️ 核心架构：三层 MRS (Minimum Recovery Set)

### Tier 0: 核心必需（必须存在）
- `task_state.md` - 当前任务状态快照
- `plan.md` - 完整的任务计划与阶段
- `snapshot.md` - 最新的时间戳快照

**失败模式：** 缺少任何 Tier 0 文件 → **停止**，运行初始化向导

### Tier 1: 重要上下文（建议存在）
- `findings.md` - 关键发现和技术决策
- `progress.md` - 详细的进度跟踪
- `architecture.md` - 架构说明

**失败模式：** 缺少 Tier 1 文件 → **警告**，降级模式恢复

### Tier 2: 可选增强（可选）
- `decisions.md` - 设计决策记录
- `blockers.md` - 阻塞问题追踪
- 领域特定文件（如 `api_design.md`、`database_schema.md`）

**失败模式：** 缺少 Tier 2 文件 → **无影响**，继续工作

## 📦 安装

### 方法 1：从打包文件安装（推荐）

1. 获取打包文件：`~/Downloads/context-resilient-task.skill`
2. 复制到 skills 目录：
   ```bash
   cp ~/Downloads/context-resilient-task.skill ~/.claude/skills/
   ```
3. 解压并重启 Claude Code（如需要）

### 方法 2：手动安装

将整个 skill 目录复制到 `~/.claude/skills/`:
```bash
cp -r ~/.claude/skills/context-resilient-task ~/.claude/skills/
```

### 验证安装

检查 skill 是否可用：
```bash
# 列出已安装的 skills（在 Claude Code 中输入）
/help

# 应该能看到 context-resilient-task 出现在 skills 列表中
```

## 🚀 使用方法

### 启动新任务

当你开始一个复杂的多阶段任务时：

```
/context-resilient-task

我需要从0到1构建一个 Dify 工作流，包括设计节点、编写 DSL、测试验证...
```

**Skill 会自动：**
1. 检测当前目录是否有 MRS 文件
2. 如果没有 → 进入初始化模式，创建 Tier 0 文件
3. 如果有 → 进入恢复模式，从 artifacts 重建状态

### 恢复已有任务

在新会话或新 IDE 中继续之前的任务：

```
/context-resilient-task

继续之前的测试用例生成工作
```

**Skill 会：**
1. 读取 `task_state.md`、`plan.md`、`snapshot.md`
2. 验证 MRS 完整性
3. 输出结构化的状态报告
4. 继续执行下一步

### 中断后恢复

如果会话中断（网络断开、IDE 崩溃、手动 `/clear`）：

```
/context-resilient-task

# 无需提供任何上下文，skill 会自动从 MRS 恢复
```

## 📋 典型工作流程

### 场景 1：首次使用（初始化模式）

```bash
# 1. 创建工作目录
mkdir ~/my-complex-task && cd ~/my-complex-task

# 2. 在 Claude Code 中启动
/context-resilient-task
我需要实现一个后端 API 模块，包括...

# 3. Skill 会创建初始 MRS
task_state.md  # 任务状态
plan.md        # 实施计划
snapshot.md    # 初始快照
```

### 场景 2：跨会话恢复（恢复模式）

```bash
# 第二天打开新的 Claude Code 会话
cd ~/my-complex-task

# 直接启动 skill
/context-resilient-task

# Skill 自动检测并恢复：
# ✅ 读取 task_state.md - 当前阶段：Phase 2
# ✅ 读取 plan.md - 下一步：实现认证模块
# ✅ 读取 snapshot.md - 昨天完成：数据库设计
# → 继续工作，无缝衔接
```

### 场景 3：降级模式（部分 MRS 缺失）

```bash
# 如果不小心删除了 progress.md
/context-resilient-task

# Skill 输出：
# ⚠️  MRS DEGRADED - 缺少 progress.md（Tier 1）
# ✅ 可以继续工作，但建议补充 progress.md
```

## 🛠️ 辅助脚本

### 1. MRS 验证脚本 (`verify_mrs.py`)

验证当前目录的 MRS 完整性：

```bash
# 进入任务目录
cd ~/my-task

# 运行验证
python3 ~/.claude/skills/context-resilient-task/scripts/verify_mrs.py .
```

**输出示例：**
```
============================================================
MRS VERIFICATION REPORT
============================================================

📋 TIER 0 (REQUIRED):
  ✅ Present: task_state.md, plan.md, snapshot.md

📚 TIER 1 (IMPORTANT):
  ✅ Present: findings.md, progress.md
  ⚠️  Missing: architecture.md

📝 TIER 2 (OPTIONAL):
  ℹ️  Not present: decisions.md, blockers.md

============================================================
⚠️  MRS DEGRADED - Recovery possible with warnings
============================================================
```

**退出码：**
- `0` = MRS 完整有效
- `1` = 缺少 Tier 0（无法恢复）
- `2` = 缺少 Tier 1（降级模式）
- `3` = 验证错误（格式问题）

### 2. 快照生成脚本 (`generate_snapshot.py`)

生成当前任务状态的快照：

```bash
# 在任务目录中运行
python3 ~/.claude/skills/context-resilient-task/scripts/generate_snapshot.py .

# 查看生成的快照
cat snapshot.md
```

**自动提取的信息：**
- 从 `task_state.md` 读取：目标、当前阶段、下一步行动
- 从 `progress.md` 读取：最近进展
- 检测最近 24 小时修改的文件
- 生成时间戳快照

**高级用法：**
```bash
# 生成归档快照（保留到 snapshots/ 目录）
python3 ~/.claude/skills/context-resilient-task/scripts/generate_snapshot.py . --archive
```

## 🎓 最佳实践

### ✅ 推荐做法

1. **任务开始时立即使用**
   ```
   /context-resilient-task
   我需要实现一个...
   ```

2. **在关键检查点更新快照**
   - 完成一个阶段后
   - 发现重要技术决策后
   - 遇到阻塞问题后

3. **保持 Tier 0 文件同步**
   - 每次完成子任务后更新 `task_state.md`
   - 阶段变化时更新 `plan.md`
   - 会话结束前生成新快照

4. **为领域任务添加 Tier 2 文件**
   - 后端开发：`api_design.md`, `database_schema.md`
   - 前端开发：`components.md`, `state_management.md`
   - 数据工程：`data_flow.md`, `transformations.md`

### ❌ 避免做法

1. **不要依赖对话历史**
   ```
   ❌ "继续之前的工作"（依赖记忆）
   ✅ /context-resilient-task（从 MRS 恢复）
   ```

2. **不要在禁止路径下创建 MRS**
   - ❌ `/.cursor/` - 临时目录
   - ❌ `/tmp/` - 会被清理
   - ❌ `/agent-tools/` - 工具目录
   - ✅ 使用项目根目录或专用任务目录

3. **不要跳过 MRS 验证**
   - 定期运行 `verify_mrs.py` 检查完整性
   - 发现问题立即修复，避免累积

4. **不要中途重命名 MRS 文件**
   - 保持标准文件名（`task_state.md`、`plan.md` 等）
   - 如需归档，使用 `--archive` 选项

## 🔍 防幻觉机制

Skill 内置多项防幻觉措施：

### 1. 强制来源标注
每个信息必须标注来源：
```markdown
✅ From task_state.md: Current phase is "Phase 2 - Implementation"
❌ I think we're in Phase 2
```

### 2. 显式未知标记
不确定的信息必须标记：
```markdown
✅ Unknown: Database schema not documented yet
❌ （编造不存在的 schema）
```

### 3. 禁止推测
只能使用 MRS 中存在的信息，不能推测：
```markdown
✅ Next action from plan.md: "Implement auth module"
❌ We should probably implement auth next
```

### 4. 单一下一步
每次只输出一个明确的下一步行动：
```markdown
✅ Next: Read backend/auth.py to understand current implementation
❌ Next: Review code, refactor, add tests, update docs...
```

## 🔧 故障排除

### 问题 1：Skill 未找到 MRS 文件

**症状：**
```
❌ MRS INCOMPLETE - Recovery impossible (missing Tier 0)
```

**解决：**
```bash
# 1. 检查当前目录
pwd

# 2. 确认工作目录正确
cd ~/my-task

# 3. 重新运行 skill
/context-resilient-task
```

### 问题 2：MRS 验证失败

**症状：**
```
⚠️  INVALID: task_state.md: Missing Last Updated timestamp
```

**解决：**
```bash
# 1. 运行验证查看具体问题
python3 ~/.claude/skills/context-resilient-task/scripts/verify_mrs.py .

# 2. 根据报告修复文件格式
# 例如：在 task_state.md 中添加
**Last Updated:** 2026-02-10 10:00
```

### 问题 3：快照时间戳过旧

**症状：**
```
⚠️  Snapshot is 8 days old (stale)
```

**解决：**
```bash
# 生成新快照
python3 ~/.claude/skills/context-resilient-task/scripts/generate_snapshot.py .

# 验证
python3 ~/.claude/skills/context-resilient-task/scripts/verify_mrs.py .
```

### 问题 4：在 /tmp 目录下无法恢复

**症状：**
```
Warning: Working in forbidden path /tmp/
```

**解决：**
```bash
# 将任务目录移到持久位置
mv /tmp/my-task ~/projects/my-task
cd ~/projects/my-task

# 重新运行 skill
/context-resilient-task
```

## 📚 与 planning-with-files 的对比

| 特性 | planning-with-files | context-resilient-task |
|------|---------------------|------------------------|
| **MRS 层级** | 单层（所有文件同等重要） | 三层（渐进式要求） |
| **自动检测** | ❌ 需要手动指定目录 | ✅ 自动检测 MRS 存在 |
| **降级模式** | ❌ 缺文件就失败 | ✅ 根据层级降级处理 |
| **防幻觉** | ⚠️  基础指导 | ✅ 强制来源标注、显式未知 |
| **验证脚本** | ❌ 无 | ✅ verify_mrs.py + 退出码 |
| **快照生成** | ❌ 手动 | ✅ generate_snapshot.py |
| **跨会话恢复** | ⚠️  依赖对话上下文 | ✅ 完全无状态恢复 |
| **禁止路径检查** | ❌ 无 | ✅ 检测临时目录警告 |

## 🎯 适用场景

### ✅ 最适合的场景

1. **多阶段复杂任务**
   - 从 0 到 1 构建系统（Dify 工作流、测试框架、API 服务）
   - 需要跨多天、多会话完成

2. **跨 IDE/跨环境工作**
   - 在 VSCode 开始，Cursor 继续
   - 本地开发，远程部署

3. **高中断风险场景**
   - 随时可能被打断的任务
   - 网络不稳定环境

4. **需要交接的任务**
   - 团队协作，需要任务交接
   - 文档化任务状态供他人继续

### ⚠️  不太适合的场景

1. **简单的单步任务**
   - "修改一个函数"、"添加一行配置"
   - 使用标准工作流即可

2. **纯探索性任务**
   - "看看代码库结构"
   - 使用 `/explore` 或 Grep/Glob 工具

3. **实时调试**
   - "为什么这个测试失败？"
   - 使用 `/systematic-debugging`

## 📖 更多资源

- **完整规范**：`~/.claude/skills/context-resilient-task/references/`
  - `minimum-recovery-set.md` - MRS 三层定义
  - `output-template.md` - 结构化输出模板
  - `recovery-workflow.md` - 完整恢复流程
  - `artifact-standards.md` - 文件标准和验证规则

- **实施计划**：`~/.claude/skills/context-resilient-task/docs/plans/2026-02-10-context-resilient-task-implementation.md`

- **模板文件**：`~/.claude/skills/context-resilient-task/assets/`
  - `task_state.template.md` - 任务状态模板
  - `snapshot.template.md` - 快照模板

## 🤝 贡献与反馈

如果在使用中遇到问题或有改进建议，欢迎：
1. 记录具体使用场景和问题
2. 提供 MRS 文件示例
3. 分享最佳实践和经验

---

**版本：** 1.0.0
**创建日期：** 2026-02-10
**设计理念：** Context is not input, it's output.
