# user-experience：条件范例

## 取样范围

- 仓库：`user-experience`，源码路径均相对于该仓库根目录。
- 2026-09-26 checkout：`feature-feedback-category-20260922`，HEAD
  `8ec21019f4aea7425b9299c85e8704cf0a3f319f`；未 fetch。
- 深读至少 4 个 `gaoxue02@gaotu.cn` 非合并业务差异及修正，主要涉及课程跳转、
  IM、配置和接口适配，不代表所有模块。
- 已核对仓库跟踪的 README、`CLAUDE.md`、`.cursor/rules/commit-message-chinese.mdc`，
  未发现跟踪的 `AGENTS.md`。该服务使用 facade/app/infrastucture 等路径；保留
  仓库已有 `infrastucture` 拼写。

以下为**样本归纳**。在此仓库用 `git show <commit> -- <file>` 复查历史差异，
并阅读目标 checkout 的同类代码。回填 Review 案例 UE-R1 单列在 backend-java.md，
其修正作者为 zhoupan05，不能混入 leader 作者样本。

## UE0. 仓库显式约定

- `CLAUDE.md`：跟踪的规范文件；commit
  `7099d79755e8f6099f1c28aa75d66992a8c12de2`，作者 bushenglei，并非 leader 样本。
  规定现有分层、提交前格式化、线程池的 TTL 包装、DAO 生成方式及测试基类
  BaseTestConfiguration 等。仅在对应任务需要时采用，不自动执行生成/提交操作。
- `.cursor/rules/commit-message-chinese.mdc`：跟踪的提交信息规则；commit
  `b4c89a55be62b5bc8722fd0ae6b52a1af1ad5319`，作者 bushenglei。类型英文、描述中文，
  适用于生成提交说明，不扩大为代码命名语言要求。
- 这些显式来源与下列业务提交分开分类，使用前核对目标 checkout 的实际内容。

## UE1. 配置对象承载复用的回退规则

- Commit：`ace01fb90a0bdf61159e1d875898bde03199ea04`。
- 文件根：`user-experience-service/src/main/java/com/gaotu/userexperience/`。
- 证据：`commons/apollo/ContactAvatarConfig.java` 内部保持 `Map<String,String>`，
  `getAvatarUrl(ContactEnum)` 和 `getAvatarUrl(ContactMergeEnum)` 处理空参数、
  未配置和空 URL 的枚举默认回退。`app/service/impl/ImMsgServiceImpl.java` 复用这些
  方法，保留已有 messageTipIconMap 优先级；复杂标题解析拆到 `resolveAiLastMsgTitle`。
- 采用：复用规则有稳定职责时，由小配置对象承载，调用方不重复理解 key 和回退。
- 限定：动态配置 Map 合理；不为两个重载强行新增泛型接口。

## UE2. 新分支复用已有枚举、配置和公共动作

- Commit：`825f8184d1ca1489b8f7fe59b5a6da5a0156bdc6`。
- 证据文件：
  `user-experience-service/src/main/java/com/gaotu/userexperience/app/service/impl/CourseServiceImpl.java:getJumpAction`
  使用 `JumpSourceSceneEnum.AI_SEARCH_SCENE`、`ClientJumpActionVo.Action.H5`，
  复用 `reportJumpData/initToastMessage` 后提前返回；
  `user-experience-service/src/main/java/com/gaotu/userexperience/commons/apollo/ApolloCourseConfig.java`
  承载新增 URL 模板；
  `user-experience-service/src/main/java/com/gaotu/userexperience/facade/api/model/course/ClientJumpQueryRequest.java`
  新增 scene 并引用枚举说明。
- 采用：沿现有业务模型和流程增加分支，减少裸数值和重复动作。
- 限定：不为一次分支另建分发框架；保留外部 scene code、动作和调用顺序。

## UE3. 配置消费类型也属于兼容性

- Commits：初始 `f3d66537e3c0e43b4081eb294115b92c556062b0`；修正
  `aae8e34c876bcfb9cc66fe820b9acd626edfdbf6`；后续使用
  `127786949544a408e8cb8afe3667d9c978adf4eb`。
- 文件：`user-experience-service/src/main/java/com/gaotu/userexperience/app/service/impl/PageModuleServiceImpl.java`、
  同目录 `ImMsgServiceImpl.java:buildAIEntranceMessage`。
- 证据：业务白名单沿已有 ApolloJsonValue 方式增加，最初 List<Long> 与消费的
  Integer 不一致，紧邻提交修为 List<Integer>；IM 后续用该类型并入已有 guard。
- 采用：可调整的范围沿本地配置方式表达，核对配置与消费类型并维持原响应字段。
- 限定：只读初始 commit 会误学错误类型；默认值中的数字不能机械枚举化，
  也不能把所有固定常量改为 Apollo 配置。

## UE4. 同名公共类型不一定能替换本地类型

- Commits：统一类型 `ed18602e560c647a3fe0aaf050fdf15dccee65cd`；随后修正
  `74c80da1261758a59e589ce84737d4c240cdbfd4`。
- 文件根：`user-experience-service/src/main/java/com/gaotu/userexperience/`。
- 证据：`app/service/impl/TeacherServiceImpl.java` 与
  `infrastucture/acl/impl/linglong/FollowAdapter.java:queryPosterType` 又恢复本地
  ResponseVO；同目录 `PosterTypeQueryResponse.java` 给多个字段加显式 JSONField，
  保留 Long 的字符串序列化。
- 采用：类型复用前核对序列化、字段类型和调用协议，兼容性优先于类型统一。
- 限定：差异说明修正的内容，未证明具体线上故障原因，不能虚构生产事故。

## 使用边界

README 要求尽量删除无用/注释代码，但作者提交
`a2acfeb1779fea134b55ccc262ddd615112f2006` 通过注释停用监控。应遵守明确规范，
不将这个做法推广为惯例。样本的宽捕获或可疑条件也不作为异常和正确性范例。
没有证据规定所有 Map 改 DTO、所有查询改 lambda 或统一内部类/独立类风格。
