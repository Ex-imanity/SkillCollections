# linglong：条件范例

## 取样范围

- 仓库：`linglong`，源码路径均相对于该仓库根目录。
- 2026-09-26 checkout：`master`，HEAD
  `a107f1ce12e13348e977ca25b2710842a70b071f`；未 fetch。
- 深读 7 个 `gaoxue02@gaotu.cn` 非合并业务差异，时间范围 2026-01-30 至
  2026-07-20，主要涉及动态、推荐、青少年模式与策略。
- 已用 `git ls-files` 确认 README 被仓库跟踪。研究环境中的根 AGENTS.md 被
  `.gitignore` 忽略，是个人文件，不作为团队编码规范，不要求其他成员提供它。
  README 列出 domain/base/service/web/client，实际职责按目标模块核对。

以下为**样本归纳**。复查 `git show <commit> -- <file>` 及相关定义、当前模块。

## LL1. 业务入口值用枚举，核对实际数值

- Commit：`9feaf33859d3c3a53967bb3be9119c0a3d50c660`。
- 证据文件：
  `linglong-service/src/main/java/com/gaotu/linglong/app/specialtopic/service/impl/SpecialTopicAppServiceImpl.java`
  将视频参数 momentPageType 的 4 改为 `MomentVideoRecEnum.RECOMMEND_FEED.getCode()`；
  新增 `linglong-domain/src/main/java/com/gaotu/linglong/enums/MomentVideoRecEnum.java`。
- 采用：以业务语义表达协议值，协议键仍保持原结构。
- **反例**：同提交的
  `linglong-service/src/main/java/com/gaotu/linglong/app/specialtopic/moduleservice/SpecialTopicColumnRecommendServiceImpl.java`
  把 17 改成 `HOMEPAGE_COLUMN_FEED.getCode()`，新 enum 的该值是 14。不能当成纯风格
  等价替换；应确认这是否是有意业务变更，再决定能否采用。
- 限定：enum 的注释作者和提交作者不同，只归因具体差异。

## LL2. 复用查询前理解分页与补页语义

- Commit：`1a140e07b23217b887112e733acfe3742ea6b40b`。
- 文件：`linglong-service/src/main/java/com/gaotu/linglong/app/moment/service/impl/MomentServiceImpl.java`。
- 证据：`listFollowedMomentsForVideo` 改用带 VIDEO 类型参数的 `getFollowedMoments`，
  删除对结果 VO 的过滤；该查询方法的补页循环累计符合类型的数据。
- 采用：复用已有带业务约束的查询，避免返回后过滤破坏分页数量和游标语义。
- 限定：本轮查询涉及 DAO/cache/HBase timeline，不支持强推全仓库 MyBatis-Plus
  lambda；找到短调用不足以证明行为等价。

## LL3. 新过滤沿用既有配置与流程

- Commit：`3c8d4aed211376140d04334ce433edec3fab7858`。
- 文件：`linglong-service/src/main/java/com/gaotu/linglong/app/moment/service/impl/MomentServiceImpl.java`。
- 证据：timeline 过滤增加 machineApprovalFilterSwitch，使用
  `MachineApprovalStatusEnum.APPROVAL_REJECT/APPROVAL_REVIEW`，记录被过滤及剩余
  momentNumbers。
- 采用：在现有流程中复用其配置方式、枚举和诊断上下文。
- 限定：不推广为所有过滤都输出完整列表；日志大小、敏感字段和运行成本按本地规范判断。

## LL4. 兼容字段与既有响应包装保持一致

- Commit：`590518d624c328adf38656827d5bfce27a9c1dd8`。
- 证据文件：`linglong-domain/src/main/java/com/gaotu/linglong/app/teenager/TeenagerCheckVO.java`
  新增 closeAiSwitch 默认 false；
  `linglong-web/src/main/java/com/gaotu/linglong/app/teenager/controller/TeenagerController.java:check`
  取已有详情值填入原 VO，再返回既有 RestResponseVO 包装。
- 采用：兼容需求优先沿现有类型和响应模式补充。
- 限定：不说明任意业务逻辑都应放 controller；默认值与 nullable Boolean 需核对。

## LL5. 复用已有策略扩展点

- Commit：`d2cf76ef21cb9501bab8ec21a3c7cf5df3a2f238`。
- 文件：`linglong-service/src/main/java/com/gaotu/linglong/app/moment/strategy/MomentStrategyFactory.java:getMomentStrategy`。
- 证据：已有构造器用 List<MomentStrategy> 和 support 建映射，提交把空默认值改为
  推荐流策略。
- 采用：新增业务入口先看已有 enum/strategy 扩展点，避免另一套分发框架。
- 限定：默认策略变化是业务行为，不能当纯风格调整直接采用。

## 使用边界

作者提交 `e9a2facb197164a954e7680374ee340cb157cb42` 的
`linglong-service/src/main/java/com/gaotu/linglong/common/teenager/service/impl/TeenagerServiceImpl.java:handleLoginRelation`
在异步关系同步失败时捕获 Exception、记录消息后跳过；另一个修正
`71701e13325eed56f595d08e032270f0d6cba22e` 在
`linglong-service/src/main/java/com/gaotu/linglong/app/ai/util/AiJsonRepairRecordUtils.java:repairJsonAndRecord`
删除二次解析 catch，把失败交给调用方。两者不足以支持统一异常策略，必须按调用链判断。

样本混用注入、import、Optional 和直接判断，不能设置全仓库唯一写法。
