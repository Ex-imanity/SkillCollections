# 验证记录

日期：2026-09-26。

## 1.2.0 客户端扩展

- 只读研究 RNSuperHigh、AndroidSuperClass、iOS_2、HarmonySuperHigh，分别深读
  至少 8、10、6、9 个业务差异/修正及相关上下文；各端 profile 记录 branch/HEAD、
  作者邮箱、完整 commit、方法、适用条件、反例和当前规范。
- 本地 zhangyu 查询命中 zhangyu118，按候选身份单独归因；iOS 未找到 zhenqiang，
  Android 的 zhangyu118/tangaoyang 样本有限。重复 cherry-pick、AI 协作与生成物
  修正不冒充独立个人风格证据，不用提交数量推导团队标准。
- 保留一个 skill，加客户端条件参考和四端仓库资料；仅按当前端加载，跨端桥接
  增加直接相关的契约资料。核对各端 tracked 规则/格式器，记录冲突，不强设统一格式。
- 独立 agent 核对四份 profile 共 44 个提交引用（含 HEAD）：完整 hash 存在，
  作者和主要路径匹配；抽核 22 个关键符号存在。续审主流程/领域路由、条件边界和
  文档链接未发现确认问题。此审核是本地 agent，未调用 Claude Code 付费评审。
- 两名评估者分别使用旧版 1.1.0 与新版 1.2.0 执行 S10-S12；未读取对方结果或
  期望，但曾参加 Android/RN 研究，不是完全盲测。两版均符合预期，没有测得增益；
  结果摘要见 [client-comparison.md](outputs/client-comparison.md)。输入强提示契约，
  不能证明实际代码风格、自动触发或 Review 返工改善。
- 未修改业务源码、安装依赖、生成签名/工程/bundle/codegen、运行客户端构建或
  设备测试。研究保留已有未提交变更；任何原提交的构建说明都不算本次验证。
- 8 项仓库约定测试、git diff 空白检查通过；另检查全部 33 个包内文件的空白与
  机器路径/私人链接，46 个内部链接和 12 个评估输入均存在且位于包内。版本、
  CHANGELOG、根 README 一致；业务仓库状态仍与研究时记录一致。

## 1.1.0 前端扩展

- 只读研究 community、mweb、internal-ad，分别深读 8、13、8 个实质业务差异及
  相关上下文；保留 checkout、完整 commit、作者邮箱、适用条件与反例。community
  本地 refs 未找到 liyunbo02；mweb 此作者样本较少，不宣称四人共同标准。
- 新增前端领域资料和三份仓库资料；区分 C 端 H5/B 端场景、显式规范与样本归纳。
  核实本次 B 端对象为 internal-ad，没有将另一个 ad-internal 远端视为已确认。
- 两个独立 agent 对同一 S7-S9 合成输入分别读取旧版 1.0.2 与新版 1.1.0，未读取
  对方结果或评估期望；均产出正确契约草图，未测得基本结果改善。摘要见
  [frontend-comparison.md](outputs/frontend-comparison.md)。输入提供了规范、契约
  和反例，不是保留真实任务，不证明独立发现能力或 leader Review 效果。
- 没有修改业务源码、安装依赖、执行前端构建、类型检查或浏览器测试。
- 独立 agent 审查领域路由、条件规则与证据，核对三份前端资料共 34 个唯一 commit
  存在、完整 hash 与作者/主要路径，抽核关键符号。发现后台证据编号 A*/IA* 不一致，
  已统一为 IA*；没有其他确认的阻塞问题。这是本地 agent 审查。
- 8 项仓库约定测试通过；26 个包内文件的机器路径/私人链接、30 个内部文档链接、
  9 个评估输入以及全部文件空白检查通过。版本、CHANGELOG 和根 README 一致。
- 1.0.2 的 Claude Code 评审不覆盖本次前端扩展；本次未调用付费外部评审。

## 1.0.2 评审修正与定向回归

- Claude Code 首轮独立评审指出规则文件发现不全，以及 linglong 个人文件不应
  归为团队规范；已核实并修正。转述反馈、条件偏好和显式规范的分类与优先级也已明确。
- 用 `git ls-files` 核对四个仓库资料所引用的团队规范：四份 README，搜索仓库的
  `.cursorrules`，UE 的 `CLAUDE.md` 及 `.cursor/rules/commit-message-chinese.mdc`
  均被跟踪。linglong 的个人 AGENTS.md 被忽略，已明确排除为团队依据。
- 新增 S4-S6，以随包的 discovery 目录复制出一次性 Git 仓库并暂存，交给一个
  独立 agent 读取 skill 和任务 README。没有预先提供规则文件或枚举答案路径，
  agent 自行检查隐藏规则、跟踪状态、源码定义及序列化文档。
- 结果：发现 `.cursorrules`，新方法使用 Objects.nonNull 且未迁移旧方法；选择
  code=17 的枚举而非名字相近的 code=14；内部统计对象保留 Map 边界及数字类型。
  草案见 [regression.md](outputs/regression.md)。没有修改 fixture、编译或执行
  序列化器，没有新的无 skill 对照，不能据此宣称实际 Review 问题减少。
- 仓库约定测试 8 项通过，仍需在真实任务中验证规则发现与风格对齐效果。
- Claude Code 复审 1.0.2 返回 APPROVE WITH NITS：首轮 2 项 P1 和 4 项 P2 全部
  关闭，没有必须修改的问题。随后补充三处文案（字段注入推荐、条件偏好称呼、
  README 规则文件范围）；这些小修正未再次调用 Claude Code。
- 复审也指出 discovery 的规则文件直接提示“保持业务数值和 JSON 契约”，会降低
  S5/S6 的区分度。保留该输入以便复现已执行的回归，明确这是有提示的场景，不能
  用于证明 skill 独自促成了这些判断。后续效果评估应增加无提示的保留任务。

## 1.0.1 团队分发检查

- 移除 README 与验证记录的作者机器安装信息、五处仓库绝对路径及私人任务 ID。
- 内部文档链接和评估输入保持相对路径；历史源码保留仓库名、commit 和仓库内路径。
- 明确仓库根目录由工作区或调用者提供的位置确定；缺少历史仓库/commit 时可采用
  当前模块范例，不依赖作者机器、私人任务记录或用户级配置。
- 分发检查通过：14 个文件未发现本机路径、私人任务 ID 或包外文件依赖；17 个
  内部链接和三个评估输入均存在且位于 skill 包内。8 项仓库约定测试与
  `git diff --check` 通过。

## 1.0.0 初始验证

## 已完成

1. 只读研究四个本地后端仓库的代表性 gaoxue02 提交及上下文；每仓库至少深读
   4 个业务差异，linglong/community 各 7 个。参考文档记录 checkout 范围、完整
   commit 和适用条件，未 fetch，不宣称覆盖最新远端或所有模块。
2. 复核实际 UE Review 修正 commit；明确该修正作者是 zhoupan05，未声称 leader
   已接受。该案例与 leader 提交样本分开标注。
3. 独立 agent 审查主流程、Java 规则及扩展边界，发现“DTO 必须包含职责方法”的
   过度泛化；已改为统计/映射对象封装相应职责，纯传输 DTO 可只有字段和访问方法。
4. 两个独立 agent 对同一套三个合成场景分别生成无 skill / 有 skill 的实现草案。
   无 skill 的基线先执行，有 skill 的运行在初稿完成后执行，两者没有读取对方结果。
   该轮未要求修改真实源码或运行编译，不是实际仓库集成测试。
5. `python3 -m unittest discover -s tests -p test_repo_conventions.py -v`：8 项
   仓库约定测试通过，包含严格 YAML、版本号、CHANGELOG 和 README 总览一致性。
6. 独立 agent 逐条核对四份资料的 git 证据，确认 commit 存在、作者归因和反例。
   修正 linglong 一处文件路径，以及 AS1 的 extData 实为新增字段的措辞；另由主代理
   校正三处反例定位。没有把新增协议字段误标成仅内部重构。
7. 检查全部 14 个文件的空白、17 个内部文档链接、三个场景输入及仓库资料中的
   28 个 commit 引用（含 checkout HEAD）；全部存在。`git diff --check` 通过。

## 场景结果

| 场景 | 无 skill 基线 | 使用 skill | 结论 |
| --- | --- | --- | --- |
| S1 回填对象和稳定响应 | 具名字段/方法，原 Map 六个键，保留计数与游标位置 | 服务内部 BackfillStats，原 Map 六个键，明确类型/顺序/更新位置 | 两者都符合预期，没有测得改善 |
| S2 旧作者样本冲突 | 用当前 enum/fromCode，拒绝旧 primitive-int 写法 | 同样选择当前 enum，另加显式 null guard | 两者都符合预期；null guard 并非必须，也不据此给技能加分 |
| S3 前端资料未整理 | 依据近邻添加一行 nullish fallback | 同样采用本地范例，未套用 Java 对象 | 两者都符合预期，未因资料缺失阻塞 |

草案原文见 [baseline.md](outputs/baseline.md) 和 [with-skill.md](outputs/with-skill.md)。
人工对照 `evals.json` 的期望检查，未使用自动风格评分。两者都明确未执行编译或
集成测试。输入提供了正例和规范，容易得到正确判断，不能证明真实任务中的触发率
或独立查找范例能力。

## 尚未证明的效果

- 未在真实需求中比较有/无 skill 的完整代码变更、leader Review 问题数量和返工成本。
- 原始 Review 是一个已发生的偏离案例；它不是本轮可复现的完整无 skill 对照实验。
- 1.0.x 的 frontend 场景只验证通用流程没有强套 Java；1.1.0 补充领域资料和合成
  契约场景，仍未在真实业务需求中验证效果。
- 安装不代表每次必定自动触发。建议在后续实际需求中明确调用，再结合 Review
  反馈改进触发说明和领域资料。
