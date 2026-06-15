# Progress

<!-- Append chronological execution log entries below this line. -->

## 2026-05-19 09:10 — MRS 初始化

- 创建 `.task-state-case-lite-optimize/`，Tier 0+1 文件全部就绪
- 目标：优化 case-lite skill，提升用例生成质量与稳定性

## 2026-05-19 09:20 — Session 分析完成（Phase 1 结束）

- 读取 testCases 项目最新 session（61a2bfdb，5.5MB，2026-05-19）
- 提取 assistant thinking 和用户反馈，识别出 5 个问题
- 用户明确指出的主要问题：corpus 阶段模型擅自改写/省略飞书文档原文
- Thinking 分析发现额外问题：落盘时机晚、图片关联逻辑不完整、选章记录格式缺失、3b/3c 检查点缺失
- 发现写入 findings.md
- 下一步：对 SKILL.md 进行 darwin 基线评分

## 2026-05-19 09:30 — darwin Round 1 完成（Phase 3 完成）

- 基线评分：62.3/100（基于 session 实测证据，corpus P0 问题拉低 dim8）
- 改动：`case-lite/SKILL.md` Step 3b 段落重写
  - 新增 ⛔ 严禁改写 约束块（禁止摘要/精简/改写）
  - 落盘时机改为每章立即追加写入（Step 3b-3）
  - 图片下载新增成功/失败两种格式规范
  - 新增 Step 3b→3c 完成检查点
- 重评分：75.0/100（+12.7）→ keep
- darwin results.tsv 已追加记录
- 备份：/Users/gaotu/.claude/skills/case-lite/SKILL.md.bak.20260519-0928
- 剩余未修复：P2 选章记录无标准格式（findings.md 问题4）

## 2026-05-29 11:54 — 状态恢复检查

- 使用 context-resilient-task 恢复 `.task-state-case-lite-optimize/`
- MRS Tier 0 校验通过；Tier 1 缺少 `architecture.md`、`decisions.md`
- `task_state.md` 为权威源，显示 Round 2 已完成、Active Todos 为空、下一步仍为 darwin 基线评分文案
- 实际 `case-lite/SKILL.md` 与 `/Users/gaotu/.cc-switch/skills/case-lite/SKILL.md` 内容一致，已包含 Step 2 选章记录格式和 Step 3b corpus 原文/立即落盘/图片/检查点约束
- 当前源码工作区 `git status --short` 为空

## 2026-05-29 12:06 — 写回脚本 bullet 解析缺陷确认

- 读取 `/Users/gaotu/Projects/testCases/case-lite-output/gaokao-ai-qa-restriction/full.md`，确认执行步骤区域存在 20 行 `- ` bullet
- 读取对应 `writeback/node-tree.json`，确认执行步骤节点不包含 bullet，也不包含样本文案“今年高考有哪些采分点”“第一次：2026年6月8日10:00”
- 定位根因：`/Users/gaotu/.cc-switch/skills/case-lite/scripts/writeback.py` 第 138-142 行只收集编号步骤，预期结果解析第 144-148 行才支持 bullet
- 已将该问题记录到 `findings.md`，并把 `task_state.md` Active Todos 更新为写回脚本缺陷修复

## 2026-05-29 12:12 — 写回脚本 bullet 解析修复完成

- 仅修改当前仓库 `case-lite/scripts/writeback.py`，未修改 `.cc-switch` 安装目录
- 新增 `case-lite/tests/test_writeback.py`，覆盖执行步骤中编号行后包含 `- ` bullet 的解析
- 先运行新增测试确认失败，再将执行步骤收集条件改为支持编号列表或 `- ` bullet
- 验证新增测试和 `case-lite/tests` discovery 通过
- 使用真实样本 `/Users/gaotu/Projects/testCases/case-lite-output/gaokao-ai-qa-restriction/full.md` dry-run 验证，解析后执行步骤包含 20 行 bullet，且包含样本文案“今年高考有哪些采分点”“第一次：2026年6月8日10:00”
- `context-resilient-task/tests` discovery 有 1 个既有环境相关失败：仓库根目录存在 `.task-state-case-lite-optimize`，导致 `test_returns_empty_when_none_exist` 不满足“无 MRS”假设；与本次 writeback 改动无关

## 2026-06-15 20:25 — wiki 子文档递归发现流程接入完成

- 参考 `/Users/gaotu/PycharmProjects/CaseMCP/FeishuMCP` 最新提交 `dfe7a9c5246cca569c49af9577a51d6fc4af19ea`，确认新工具 `get_child_documents` 的参数和返回字段
- 更新 `case-lite/SKILL.md`：新增 Step 1a，要求在章节浏览前对用户原始飞书链接调用 `get_child_documents(fetch_all=true, include_non_docx=false)`，对 `has_child == true` 的子文档递归展开
- 明确新流程只收集子文档元数据，不读取正文；必须展示发现树并等待用户确认纳入后，才作为同类文档进入 Step 2
- 更新 `case-lite/references/feishu-tools-guide.md`：补充 `get_child_documents` 使用方法、递归规则、去重规则和普通 docx 降级说明
- 更新 `case-lite/README.md`：用户侧流程说明会自动发现知识库子文档并询问是否纳入
- 新增 `case-lite/tests/test_skill_contract.py` 作为文档契约测试，防止递归子文档发现流程被误删
- 验证 `python -m unittest case-lite/tests/test_skill_contract.py` 和 `python -m unittest discover -s case-lite/tests` 均通过
