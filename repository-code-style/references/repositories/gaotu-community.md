# gaotu-community：条件范例

## 取样范围

- 仓库：`gaotu-community`，源码路径均相对于该仓库根目录。
- 2026-09-26 checkout：`feature_api_plugin`，HEAD
  `db040a2f67e65a109ec5e7685bbc39baccfb05f3`；未 fetch。
- 深读 7 个 `gaoxue02@gaotu.cn` 非合并业务差异，时间范围 2026-01-26 至
  2026-02-24，主要涉及 Feed、TopBar、广告卡片与空值修正。
- 已用 `git ls-files` 确认根 README 被跟踪，未发现跟踪的 AGENTS.md。README 列 API/domain/app/
  infrastructure/facade；部分枚举后来迁移到 community-client，应用前核对实际路径。

以下为**样本归纳**。在此仓库用 `git show <commit> -- <file>` 复查，再查当前定义。

## GC1. 枚举替换业务魔法值，保留协议键

- Commit：`6c40a9b5eee3784680bf16bd03ad6aef9119b624`。
- 文件：`community-app/src/main/java/com/gaotu/community/app/service/feed/FeedService.java:buildVideoParam`。
- 证据：momentPageType 从 4 改为 `MomentVideoRecEnum.RECOMMEND_FEED.getCode()`，
  保留原 key 和 URLEncoder 构造流程。
- 采用：业务编号以既有枚举表达，改写时确认 code 与原值一致。
- 限定：不支持所有字符串常量化；视频参数仍可保留 JSONObject 边界结构。

## GC2. 相关业务参数形成请求对象

- Commit：`bfb87a103e54b2d28da50d97f4710277b99965ff`。
- 证据文件：`community-api/src/main/java/com/gaotu/community/api/dto/topbar/TopBarRequest.java`
  承载 subjectIds/newHomePageGroup，沿用本地 Lombok、Swagger、Serializable；
  `community-api/src/main/java/com/gaotu/community/api/TopBarService.java:getHomePageTopBar`
  从 List 入参改为该请求对象，实现在
  `community-app/src/main/java/com/gaotu/community/app/service/home/TopBarServiceImpl.java`。
- 采用：形成稳定业务概念的相关参数可放进本地已有 DTO 层。
- 限定：该提交也改变 HTTP 入参形式，不能据此认为封装无需检查兼容性；新 DTO
  注释的 author 为 system，提交作者不等于全部设计的原创作者。

## GC3. 同一业务数量保持同一来源

- Commit：`c596cde5c5cc8d1637d241a9a3254c036a1d9688`。
- 文件：`community-app/src/main/java/com/gaotu/community/app/service/feed/FeedService.java`。
- 证据：新增 openCourseAdCount；`convertToOpenCourseCardVOList` 的 limit(10)
  和 `buildRecommendCardRequestFromOpenCourseRequest` 的 setPageSize(10) 同改为该
  配置属性；`convertCourseCardDTOToOpenCourseVO` 增加 courseType 非空判断区分纯广告。
- 采用：同一业务阈值在多处使用时复用同一配置/常量，避免独立漂移。
- 限定：不要求所有局部常量变 Apollo；新增条件要核对特殊广告的业务语义。

## GC4. 窄改动扩展已有 helper

- Commit：`bd07d57dcfb2fb1d0567c75c768a11cb77cb0713`。
- 文件：`community-app/src/main/java/com/gaotu/community/app/service/home/TopBarServiceImpl.java:initTeenagerV2Config`。
- 证据：在已有 early return 中把支持范围扩为 TEENAGER_V2 或
  NEW_HOME_PAGE_TEENAGER，保持现有 helper；上下文已有 null guard、详细设置检查和
  Boolean.TRUE.equals(publishLimit)。
- 采用：少量新增条件沿已有清晰 helper 实现，无复用收益时不新增处理类。
- 限定：不要求整个仓库统一 early return、Optional 或 null 判断方式。

## 使用边界

TopBar 动态配置仍使用 Map/ObjectNode，不能要求所有 Map 改 DTO。此批查询证据
不足以支持全仓库 MyBatis-Plus lambda 迁移。没有证据固定注入、import 或 Stream/for。

Commit `d66afedceef642575ae9d62ba1bc25f07a4d9495` 中
`community-bff/src/main/resources/script/CoursePorcelain.groovy`
出现日志 placeholder 与实参数量不匹配，不应作为日志范例。异常和日志样本需
检查具体内容，不能因为作者身份直接采用。
