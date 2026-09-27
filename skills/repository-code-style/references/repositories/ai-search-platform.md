# ai-search-platform：条件范例

## 取样范围

- 仓库：`ai-search-platform`，源码路径均相对于该仓库根目录。
- 2026-09-26 checkout：`feature-0812-iterator`，HEAD
  `9685926ee837e939d13a5f808201f194abb3869f`；未 fetch。
- 按 `gaoxue02@gaotu.cn` 取样非合并业务提交，深读至少 4 个差异及相关上下文。
  主要涉及热点词、问问、搜索消息与缓存，不能代表整个仓库或最新远端。
- 已核对仓库跟踪的 README 和 `.cursorrules`；未发现跟踪的 `AGENTS.md`。
  README 描述 domain/app/infrastructure 多模块分层；应用前核对实际模块。

以下业务提交是**样本归纳**，显式规则另列。复查方式：在此仓库执行
`git show <commit> -- <file>`，再读相关调用方和当前版本。

## AS0. 仓库显式规则优先

- 来源：被版本控制跟踪的 `.cursorrules`；规则 commit
  `50b2b7627047adbe5111c2a80f52cbf8a9fe54ef`，2026-03-10，gaoxue02。
- 强制规则：对象判空使用 Objects.isNull/nonNull；字符串、集合使用对应空白/空集合
  工具；魔法值用常量表达，数值转换/默认值使用 NumberUtils；异常日志带异常对象，
  关键业务参数按日志规则记录；禁止空 catch 和捕获 Throwable/Error。
- Lombok 注解整体为推荐；日志使用 Slf4j，禁止手动创建 Logger。具体规则和其
  强制/推荐等级以目标版本 `.cursorrules` 为准，不向其他仓库推广。依赖注入也是
  推荐项，当前规则优先字段注入并使用 Resource/Autowired；应用前核对目标版本。
- 冲突证据：AS4 的 `57b094db...` 仍含字面量 30；规则文件的一些示例也保留数字、
  字符串甚至直接 null 比较。按明确条款处理本次新增代码；不把不一致示例升级为
  例外，不借机批量改历史代码。若条款本身有矛盾并影响任务，再澄清。

## AS1. 关联结果用小 DTO，边界保持原结构

- Commit：`a20082605a2ca2dd6ad60e00897f75f9309b689d`。
- 文件根：`ai-search-platform-app/src/main/java/com/gaotu/aisearch/app/service/`。
- 证据：`model/dto/EveryAskingQuestionsDTO.java` 新增 `questionList/totalCount`；
  `hotword/EveryAskingApplicationService.java:listDefaultHotQuestions` 及策略传递同一
  DTO。`mainsearch/message/MessageApplicationService.java:buildGreetingMessageEntity`
  新增 totalCount 的 extData，以 `singletonMap("totalCount", ...)` 构造，content
  继续仅序列化列表。
  `ai-search-platform-task/src/main/java/com/gaotu/aisearch/task/adapter/controller/hotword/HotWordController.java`
  通过 `getQuestionList()` 保留原列表响应。
- 采用：稳定、一起流转的字段可封装；外部已有结构在边界适配。
- 限定：不支持禁用 Map、不支持所有结果包 DTO。新增 DTO 的注释作者与提交作者
  不同，不能从提交推断整类的原创归属。

## AS2. 新维度沿已有模型和数据链路扩展

- Commit：`ddf7cc7e27b1ea862a723d660e78a707b2616de6`。
- 证据文件：
  `ai-search-platform-domain/src/main/java/com/gaotu/aisearch/domain/hotword/value/HotWordDimension.java`
  增加 appVersion；同模块 `entity/HotWordEntity.java` 增加 minVersion/maxVersion。
  `ai-search-platform-app/src/main/java/com/gaotu/aisearch/app/service/hotword/HotWordApplicationService.java`
  在 `getPublishedHotWords` 中加入过滤，通过私有方法拆分局部规则；同目录
  `strategy/HotWordEveryAskingStrategy.java` 延续已有 dimension builder。
  `ai-search-platform-infrastructure/src/main/resources/mapper/hotword/HotWordMapper.xml`
  同步映射及读写列。
- 采用：沿已有对象、层次和完整持久化链路增加维度；局部规则可用具名私有方法。
- 限定：该提交手写版本解析，不据此规定版本比较必须自行实现；不将 HotWord 的
  repository/XML 查询强行迁移成另一模块的查询模式。

## AS3. 局部算法保持清晰、克制抽象

- Commit：`f88f625c67913f0fdbc688b3234afcff1a091ec0`。
- 文件：`ai-search-platform-app/src/main/java/com/gaotu/aisearch/app/service/hotword/strategy/HotWordEveryAskingStrategy.java`。
- 证据：`processChangeLogic` 将多个 subList 分支改为 size/startIndex/count 和
  显式循环，新增 `indexOfId`；空集合提前返回，用模运算表达回绕。
- 采用：局部算法选择能清楚表达边界的实现，不为一次取数建立新策略框架。
- 限定：不支持所有 Stream 改循环，也不支持所有分支必须加注释。

## AS4. 在已有服务封装基础设施动作

- Commit：`57b094db5715e8e3fc6080e8854fc58cefbbc468`。
- 文件：
  `ai-search-platform-app/src/main/java/com/gaotu/aisearch/app/service/mainsearch/processors/after/SearchRecordMainSearchPostProcessor.java`；
  `ai-search-platform-infrastructure/src/main/java/com/gaotu/aisearch/infrastructure/acl/session/SessionContextCacheService.java`。
- 证据：调用方构造 PipelineSessionTurn 后调用 `appendSessionTurns`；缓存服务
  处理已有 RedisKeyUtil、裁剪、TTL、JSON 与写入。日志附 questionId/sessionId 和异常。
- 采用：业务调用语义方法，缓存细节留在已有责任明确的服务中。
- 限定：样本仍有重复和宽捕获；不能推断 read-modify-write 并发安全，也不能要求
  所有写操作捕获异常后降级。

## 使用边界

判空、魔法值、Lombok 和日志以 AS0 的显式规则为准。业务样本不能覆盖或取消
这些规则；注入方式按 `.cursorrules` 的推荐等级处理，本批样本不足以另设统一的
import 偏好。选择 Stream/for
时也先核对显式条款及任务清晰度。保留协议名和数值语义，按规范调整表达位置。
