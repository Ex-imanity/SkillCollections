# repository-code-style

让 agent 的实现更贴合目标仓库当前的组织、职责和代码。开工前先探索并维护本地档案，
Review 先查文件/类的必要性、目录分层和能力复用，再查内部表达。当前包含通用流程、后端 Java、前端 Web 和客户端
参考，依据目标仓库显式规范、代表性历史提交及转述的 Review 建立资料。
后端取样 gaoxue02；前端取样 liyunbo02、lichen03、dengyong、wangdi08 的可用提交。
作者覆盖因仓库而异，样本不能替代目标模块规范或代表全部团队代码。
客户端取样 zhaodexi、zhenqiang、tangaoyang，以及本地匹配的 zhangyu118 候选；
不混合其他同名 zhangyu 作者，具体身份与覆盖限制见各端资料。

## 一个 skill，按需读取参考资料

主入口负责编辑前取证、处理冲突、实施、自审和独立 Review；后端与各仓库的证据分别放在
`references/`。前端分 C 端 H5 与 B 端场景，客户端按 RN、Android、iOS、HarmonyOS
拆分参考资料；通用检查流程相同，当前无需拆成四个重复流程的 skill。
当某个平台有独立工具流程或交付格式时，再考虑拆成独立 skill。

## 使用

在修改或评审已有仓库代码时触发，也可以明确指定：

```text
使用 repository-code-style，实现这个需求；先找同模块的同类代码，
优先核对近半年实质改动和后续 CR，第一次编辑前建立/刷新本地风格档案，列清
目录与各层职责、已有能力和本次文件落点。完成前对实际修改和新增文件独立检查
结构必要性、复用语义、内部表达及契约兼容性。
如有人工 CR 输入，逐项关联实际处理与验证，保留未闭环项；复用工具核对具体 API、
有效版本和语义证据，并检查业务说明在重构后是否仍准确。
```

源文件入口：[SKILL.md](SKILL.md)。运行时只读当前任务适用资料。
没有已整理的平台规则时，仍可以按本地范例完成任务。

## 资料

- [后端 Java](references/backend-java.md)：条件偏好、适用边界和 UE Review 修正案例。
- [风格依据与 Review 契约](references/style-evidence.md)：编辑前记录、自审、reviewer 独立对照和跨 agent 交接。
- [仓库探索与本地档案](references/repository-profile.md)：近半年优先取样、冲突/旧例回退、目录/能力盘点和增量刷新。
- [本地档案模板](assets/local-style-profile.template.md)：任务中生成本地证据索引使用，不是评估夹具。
- [ai-search-platform](references/repositories/ai-search-platform.md)。
- [user-experience](references/repositories/user-experience.md)。
- [linglong](references/repositories/linglong.md)。
- [gaotu-community](references/repositories/gaotu-community.md)。
- [前端 Web](references/frontend-web.md)：请求契约、共享边界、状态、样式与验证。
- [community](references/repositories/community.md)：C 端 H5，区别于后端 gaotu-community。
- [mweb](references/repositories/mweb.md)：多产品 H5 与共享业务层。
- [internal-ad](references/repositories/internal-ad.md)：B 端后台；用户称 ad-internal，核实的仓库名为 internal-ad。
- [客户端](references/client-mobile.md)：跨端契约、生命周期、模型与验证边界。
- [RN](references/repositories/rnsuperhigh.md)、[Android](references/repositories/android-super-class.md)、
  [iOS](references/repositories/ios-2.md)、[HarmonyOS](references/repositories/harmony-super-high.md)。
- [历史源码取样](references/evidence-and-extension.md)：新仓库与作者样本的取样方法和证据分类。

## 路径与依赖

skill 内文档链接相对于 skill 目录；业务源码定位采用“仓库名称 +
commit + 仓库内相对路径”。从当前工作区或调用者提供的位置确定业务仓库根目录，
不要求固定的磁盘目录，也不要求预先拥有全部样本仓库或私人任务记录。

历史 commit 不在当前克隆中时，将该样本视为参考说明，依据当前模块的规范和同类
实现继续；确需核对历史证据时再获取对应仓库资料。业务风格依据只取目标业务仓库
真实源码；Skill 的合成评估场景、测试夹具和故意错误样例不属于业务源码证据。

已有仓库 reference 是历史定位资料。默认本地档案位置为
`.repository-code-style/profile.md`，写前验证本地忽略规则；可复用已忽略的现有位置。
换分支、相关源码/工作区变化或新 CR 后增量复查，不把缓存当当前规范。六个月是
优先检索窗口，旧实现经核对仍有效时可保留；近期机械修改也不能刷新旧设计的资格。

有 CR 会议/评论时在本地逐项核销，区分要求、建议和延期，以及“已改”和“已验证”。
实际采用能力要有具体方法、有效版本、调用方及相关语义证据；新增层比较删除/
合并后的调用链。审查和验证注明对应的工作区、暂存、commit 或 PR 快照，避免将
工作区通过误当作交付版本通过。业务说明检查内容及真实性，不只检查语言和格式。

## 源码维护与验证

开发评估场景与验证记录位于源码仓库的 `evals/repository-code-style/`，维护流程在
`docs/maintainers/repository-code-style.md`。这些资料不随 Skill 安装，也不是业务风格
取证时需要补齐的依赖。维护时在源码仓库根目录执行：

```bash
python tools/run_tests.py
```

## 约束的落点

用户级指令保留跨仓库底线，仓库/模块级规则文件（AGENTS.md、CLAUDE.md、Cursor
规则等）定义本地规范，skill 负责执行流程。可以在适用的规范里加入以下提醒来加强触发：

```text
实现、修复、重构或评审现有代码时使用 repository-code-style。
第一次编辑前核对当前本地风格档案、近期同职责实质范例、已有能力和文件落点；扩大范围先补查。
完成前对实际修改及新增/未跟踪源码做风格对照，保持外部契约与业务映射。
Review 独立核实范例并单独给出风格结论；证据不足不得声称检查通过。
```

此提醒尚未写入任何业务仓库或用户级规范。这里的前置要求是执行契约，不是工具
拦截器；skill 的自动触发仍依赖 agent 的选择，不能保证阻止违规写入。测试、格式
或 verdict 检查也不能证明历史风格符合性。

已授权跨 agent Review 时，将仓库/比较基准、实际改动、风格依据与合理偏离带入
交接；reviewer 没有安装本 skill 时也要收到必要步骤和可读的来源定位。普通 Review
直接执行 reviewer 契约，不需要为此启动其他 CLI。细节见上面的风格依据 reference。

本轮样本是本地 git 的历史证据，不能代表所有代码或最新远端分支。作者样本中的
硬编码、弱日志等不自动升级为规范；生成的修正也不宣称已经过 leader 审核。
