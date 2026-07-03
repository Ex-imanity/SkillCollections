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

## 2026-07-01 18:47 — 新一轮优化立项：首次使用依赖安装与 MCP 配置

- 用户提出新目标：优化 case-lite 安装和依赖管理流程；当 feishu-docx-blocks / Banshan MCP 不满足要求时，不只是提示用户安装，而是在用户同意后自动配置
- 读取飞书文档 `Case-lite skill使用说明` 的“安装”章节，确认 Claude Code / Codex 的 MCP 配置方式、`uvx feishu-docx-blocks@latest`、Banshan 固定 URL、以及 Claude Code 配置路径新旧差异
- 解决本地 `lark-cli` 读取文档前的 `keychain Get failed: keychain not initialized`：执行 `lark-cli config keychain-downgrade` 成功，后续可在 Codex 中读取飞书文档
- 用户确认设计边界：
  - 主要支持 Claude Code 与 Codex，其他 Agent 仍给手动提示
  - 默认写全局 MCP 配置，但必须询问用户意见
  - 已有 feishu-docx-blocks 时默认询问升级
  - Banshan MCP URL 固定为 `https://tech.baijia.com/mcp-server/banshan/mcp`
  - 飞书授权沿用 feishu-docx-blocks 自带浏览器授权逻辑
  - `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 不明文写入 skill，默认值引导用户到内部文档自行获取
- 已将本轮 feature 的目标、边界、建议实现形态和 Review 重点写入 `findings.md`
- 已更新 `task_state.md` Active Todos，下一步进入 setup_mcp 诊断/修复流程设计与实现

## 2026-07-01 20:26 — 首次使用依赖安装与 MCP 配置优化完成

- 新增 `case-lite/scripts/setup_mcp.py`
  - 默认只输出诊断报告，不写配置
  - 支持 `--agent claude-code|codex`
  - 支持 `--fix` 在用户确认后写入全局 MCP 配置
  - Claude Code JSON 配置 merge `mcpServers`，保留已有配置
  - Codex TOML 配置 merge `mcp_servers.feishu-docx-blocks` 和 `mcp_servers.banshan`
  - 写配置前创建 `.bak.<timestamp>` 备份
  - `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 从环境变量或交互输入读取；报告中 secret 脱敏
  - 诊断报告包含 Python 和 uv/uvx 可用性
- 新增 `case-lite/references/install-mcp.md`
  - 按渐进式披露原则，仅在缺依赖或首次安装时读取
  - 说明 Claude Code / Codex 配置路径、自动配置流程、手动配置片段、Review checklist
  - 不包含默认 `FEISHU_APP_SECRET` 明文
- 更新 `case-lite/SKILL.md`
  - 环境要求改为轻量检查优先
  - 缺依赖时才进入首次使用依赖向导
  - 明确自动写全局 MCP 前必须用户同意
  - 明确不要在 skill 中写入默认凭证
- 更新 `case-lite/README.md`
  - 安装章节改为依赖诊断/自动配置优先
  - 指向内部文档获取默认凭证
- 新增/更新测试
  - `case-lite/tests/test_setup_mcp.py` 覆盖 Claude Code JSON merge、Codex TOML merge、备份创建、报告脱敏
  - `case-lite/tests/test_skill_contract.py` 覆盖渐进式披露、setup 脚本入口、凭证安全和安装参考文档存在
- 验证命令通过：`python -m unittest discover -s case-lite/tests`
- 使用临时 Codex config 验证 `setup_mcp.py --fix --yes --json` 可写入 MCP 配置、创建备份且诊断输出脱敏；未操作真实全局配置

## 2026-07-01 21:10 — Phase 6 Review 复核 + F1–F5 修复

- 用户要求基于 MRS + 最新改动 review codex 的 Phase 6，重点 Claude Code MCP 配置路径
- 用飞书 `安装` 章节（docx SpPsdDalSo7CU4xop1pc8OjSnM9, H4 ClaudeCode配置 pos 20-30）核对配置内容忠实还原；全仓库 grep 确认无真实 secret 泄漏，公开仓库不内嵌凭证决策正确
- 用户拍板：F1–F5 全修 + MRS 留痕，F6 维持现状
- 已修复（详见 findings.md 2026-07-01 review 表）：
  - F1 路径歧义：`detect_claude_code_config` 返回歧义信息，两路径同存拒绝盲写
  - F2 no-clobber：merge/apply 加 write_feishu/write_banshan，已有 feishu 默认保留，需 --replace-feishu
  - F3 写入加固：原子写 + chmod 0o600 + 退出 CC 提示 + claude mcp add-json 文档
  - F4 凭证来源：resolve_creds 优先 env、其次现有配置，消除误报
  - F5 覆盖：tomllib 读 Codex、补路径/凭证/no-clobber 测试、修弱断言、补连通性说明
- 改动文件：`case-lite/scripts/setup_mcp.py`、`tests/test_setup_mcp.py`、`tests/test_skill_contract.py`、`SKILL.md`、`references/install-mcp.md`
- 验证：`python -m unittest discover -s case-lite/tests` 全绿；/tmp 烟测确认 no-clobber 与 ambiguity 拒写
- 下一步：交 codex 复核（重点见 findings.md 末尾三条）

## 2026-07-02 16:30 — codex 复核后修复 Codex TOML inline comment 边界

- 基于 MRS 与文件现状复核 Claude Code Review 后的改动，确认主流程方向合理：显式确认、默认全局 MCP、no-clobber、路径歧义拒写、凭证不入仓均符合用户约束
- 发现 Codex 写侧 `_strip_toml_table` 对合法 TOML 表头行尾注释不兼容：如 `[mcp_servers.feishu-docx-blocks] # user note`，`--replace-feishu` 会保留旧表并追加新表，导致重复声明、TOML 解析失败
- 按 TDD 修复：
  - 新增 `test_merge_codex_config_replaces_table_with_inline_comment`，先确认失败
  - 新增 `_toml_header_name`，识别表头时忽略字符串外的 `#` 行尾注释，并要求表头后只允许空白或注释
  - `_strip_toml_table` 改用解析出的 header name 判断目标表和子表
- 验证：定向测试通过；`python -m unittest discover -s case-lite/tests` 全绿（22 用例）；/tmp 烟测确认 inline comment 场景写回后 `tomllib` 可解析

## 2026-07-02 16:45 — 复用已有凭证完成旧配置升级

- 用户确认旧配置升级场景应复用已有凭证，不应要求用户重新配置
- 新增 CLI 回归测试 `test_replace_feishu_reuses_existing_creds_when_env_missing`：已有旧版 feishu 配置且含 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，无环境变量时执行 `--replace-feishu --yes` 应直接成功
- 修复 `setup_mcp.py`：写入 feishu 时优先复用诊断阶段 `resolve_creds` 读到的凭证，只在缺字段时再读环境变量/交互输入
- 同步修复 Claude Code 路径歧义交互选择后未重新读取所选路径凭证的问题
- 验证：新增测试先失败后通过；`python -m unittest discover -s case-lite/tests` 全绿（23 用例）；/tmp 烟测确认无环境变量时旧凭证被保留、feishu 升级为 `feishu-docx-blocks@latest`、Banshan 被补齐
