# repository-code-style

让 agent 的实现更贴合目标仓库已有代码。当前包含通用流程、后端 Java 和前端 Web
参考，依据目标仓库显式规范、代表性历史提交及转述的 Review 建立资料。
后端取样 gaoxue02；前端取样 liyunbo02、lichen03、dengyong、wangdi08 的可用提交。
作者覆盖因仓库而异，样本不能替代目标模块规范或代表全部团队代码。

## 一个 skill，按需读取参考资料

主入口负责选范例、处理冲突、实施和自审；后端与各仓库的证据分别放在
`references/`。前端分 C 端 H5 与 B 端场景，客户端后续补充领域和仓库资料。
当某个平台有独立工具流程或交付格式时，再考虑拆成独立 skill。

## 使用

在修改或评审已有仓库代码时触发，也可以明确指定：

```text
使用 repository-code-style，实现这个需求；先找同模块的同类代码，
沿用本地惯例，并在完成前检查本次 diff 的硬编码、对象职责和契约兼容性。
```

源文件入口：[SKILL.md](SKILL.md)。运行时只读当前任务适用资料。
没有已整理的平台规则时，仍可以按本地范例完成任务。

## 资料

- [后端 Java](references/backend-java.md)：条件偏好、适用边界和 UE Review 修正案例。
- [ai-search-platform](references/repositories/ai-search-platform.md)。
- [user-experience](references/repositories/user-experience.md)。
- [linglong](references/repositories/linglong.md)。
- [gaotu-community](references/repositories/gaotu-community.md)。
- [前端 Web](references/frontend-web.md)：请求契约、共享边界、状态、样式与验证。
- [community](references/repositories/community.md)：C 端 H5，区别于后端 gaotu-community。
- [mweb](references/repositories/mweb.md)：多产品 H5 与共享业务层。
- [internal-ad](references/repositories/internal-ad.md)：B 端后台；用户称 ad-internal，核实的仓库名为 internal-ad。
- [证据维护与扩展](references/evidence-and-extension.md)：新规则的取样和升级方式。
- [场景评估](evals/evals.json)与[验证记录](evals/validation.md)。

## 路径与依赖

skill 内文档链接和评估输入均相对于 skill 目录；业务源码定位采用“仓库名称 +
commit + 仓库内相对路径”。从当前工作区或调用者提供的位置确定业务仓库根目录，
不要求固定的磁盘目录，也不要求预先拥有全部样本仓库或私人任务记录。

历史 commit 不在当前克隆中时，将该样本视为参考说明，依据当前模块的规范和同类
实现继续；确需核对历史证据时再获取对应仓库资料。评估中的 `fixture/` 路径是
随包提供的合成场景定位，不是需要额外准备的源码文件。

## 约束的落点

用户级指令保留跨仓库底线，仓库/模块级规则文件（AGENTS.md、CLAUDE.md、Cursor
规则等）定义本地规范，skill 负责执行流程。可以在适用的规范里加入以下提醒来加强触发：

```text
实现、修复、重构或评审现有代码时使用 repository-code-style。
编辑前选同模块的同类范例，完成前对本次 diff 做风格检查；
保持外部契约与业务映射，说明有理由的偏离。
```

此提醒尚未写入任何业务仓库或用户级规范。skill 的自动触发仍依赖 agent 的选择，
不能代替明确指令或已有格式/静态检查。

本轮样本是本地 git 的历史证据，不能代表所有代码或最新远端分支。作者样本中的
硬编码、弱日志等不自动升级为规范；生成的修正也不宣称已经过 leader 审核。
