---
name: repository-code-style
version: 1.1.0
description: Use when implementing, fixing, refactoring, or reviewing code in an existing repository, especially when code must follow historical conventions, a leader's Review comments, or Gaotu Java backend, C-end H5 and B-end web practices. Also use for requests to match repository coding style, reduce hardcoding, preserve frontend request and state conventions, or improve business object encapsulation.
---

# Repository Code Style

让本次改动贴合目标模块已有的代码。先找贴近任务的范例，再实现，最后对照 diff
检查。功能正确性、接口兼容性和明确需求始终是前提；历史代码是证据，不是自动生效的规范。

## 1. 确定范围与证据

- 确认目标仓库、分支、HEAD、工作区已有改动和实际修改模块。发现适用的
  `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、`.cursor/rules/`、CONTRIBUTING、README、
  模块文档，以及已有 editorconfig、格式器和静态检查配置。用 `git ls-files` 检查
  跟踪文件；必要时用限定范围的 `rg --files --hidden` 查隐藏规则及模块子目录。
  按规则的目录、glob 和适用条件读取，不执行文档中无关的操作。
- 当前会话适用的指令始终按其优先级遵守。提炼供团队分发的规范时，另核对文件
  是否被仓库跟踪（`git ls-files`）或已明确确认为团队约定；被忽略的个人文件不能
  作为团队规范，不能要求其他成员复制其配置。Review 转述保留来源与适用范围。
- 阅读目标文件及直接相关的调用方、对象、测试。通过 `rg` 找同模块的同类实现，
  优先选择业务职责、数据形态、调用方式相近的代码，而非只按作者或类名匹配。
- 普通改动选 2~3 个范例，简单的一行修改选 1 个明确范例即可。阅读相关方法的
  上下文；判断历史选择时用 `git show` 看增删差异，需要时再查后续修正或 blame。
  提交作者只证明其提交的差异，不能证明整份文件都是其设计。
- 开始编辑前形成简短的“风格依据”：范例定位、准备复用的写法、需要保持的契约、
  已发现的冲突。可记录在现有任务笔记或简短进度说明中，无需新增业务仓库文档。
  引用当前文件的路径和方法；引用历史代码时加 commit。不要编造文件或确认状态。

## 2. 按需读取领域资料

| 当前任务 | 读取资料 |
| --- | --- |
| 后端 Java 实现或评审 | [backend-java.md](references/backend-java.md) |
| ai-search-platform | [ai-search-platform.md](references/repositories/ai-search-platform.md) |
| user-experience | [user-experience.md](references/repositories/user-experience.md) |
| linglong | [linglong.md](references/repositories/linglong.md) |
| gaotu-community | [gaotu-community.md](references/repositories/gaotu-community.md) |
| 前端 Web 实现或评审 | [frontend-web.md](references/frontend-web.md) |
| community（C 端 H5，与后端 gaotu-community 不同） | [community.md](references/repositories/community.md) |
| mweb（多产品 C 端 H5） | [mweb.md](references/repositories/mweb.md) |
| internal-ad（B 端；用户称 ad-internal，本次核实的仓库名为 internal-ad） | [internal-ad.md](references/repositories/internal-ad.md) |
| 提炼新规范、补充作者样本或扩展平台 | [evidence-and-extension.md](references/evidence-and-extension.md) |

只读当前任务适用的资料。仓库资料是 2026-09-26 的本地历史样本，使用前核对目标
checkout 是否仍适用。只核对当前任务相关的仓库和模块。

文档链接相对于本 skill；业务源码路径相对于对应仓库根目录。通过当前工作区或
调用者提供的位置确定根目录，不假定作者机器的目录结构或要求所有样本仓库都存在。
历史 commit 不可用时，只把其说明作为参考，依据当前模块规范和同类实现继续，
不声称已复查该历史证据。只有任务确实依赖缺失源码时才请求其位置或内容。

客户端尚无整理过的领域规范：仍执行通用流程，依照目标模块现有实现完成任务。
不要把 Java 的对象、依赖注入或分层写法套到前端或客户端；没有对应仓库资料时，
依据当前模块范例继续，不虚构平台规范。

## 3. 处理冲突与实现

- 按当前指令层级遵守用户要求和适用规范。明确 Review 结论应限定到其适用范围。
  在不违反当前指令和正确性/兼容性的前提下，仓库显式规范优先，再采用当前领域
  reference 的适用条件偏好，随后参考目标模块同类实现和跨仓库样本。
  条件偏好只影响本次新增或修改的代码，不要求迁移未涉及的存量实现。
- 相同作者也可能有新旧写法或缺陷。历史模式与当前契约、业务语义或正确性冲突时，
  保留正确行为并说明选择依据。只有需求或兼容要求确实不明确时才询问用户。
- 沿用目标模块的命名、目录、注解、对象类型、工具、异常与日志方式、格式和测试习惯。
  先复用现有能力；新增抽象要能减少本次改动中的具体复杂度或重复。
- 对每处新增或重复的业务字面量，判断它属于业务标识、存储字段、协议字段、展示文案
  还是局部算法值。优先复用对应的类型或映射；协议键可以保留在明确的边界层。
- 不为了“更像作者”修改无关代码、统一整个仓库、引入新框架、改变业务映射或扩大
  公共 API。样本没有涉及的规则不宣称为仓库惯例。

## 4. 完成前检查本次 diff

使用目标仓库已有的格式、静态检查和测试命令；按风险选择最小有意义的验证。
单纯格式修改不需要新增测试。不要为一个风格改动运行无关的大范围验证。
先核对命令的实际覆盖路径、配置文件名和可用依赖；旧脚本名称不能证明检查有效。
格式器限定本次文件，不因工具配置问题顺带修复全仓配置或执行全仓 --fix。

对本次 diff 做独立的一轮风格检查，逐项回答：

1. 是否存在可复用却重新定义的对象、枚举、业务映射、工具或查询写法？
2. 存储字段或业务值是否重复散落？封装是否包含了职责，而非只把字符串搬到常量类？
3. 新对象或 helper 的作用是否明确，是否比已有局部写法更复杂？
4. 命名、分层、异常、日志、格式和测试是否与选定范例一致？偏离是否有具体理由？
5. 外部字段、类型、空值、序列化、枚举数值、计数口径和副作用是否保持？
6. 是否有无关改动，或把旧代码中的缺陷当成风格复制？

修复确认的问题，再检查受影响部分。不要把自审当成用户要求的独立 reviewer；本
skill 不自动发起外部评审、安装检查器或修改仓库规范。

## 5. 简洁交付

沿用主任务的交付格式，必要时补充一句采用的本地范例、合理偏离和验证结果。
有 Review findings 时引用具体文件位置和依据。区分“符合已检查的范例”与
“经过 leader 审核”；没有执行的验证明确标出。
