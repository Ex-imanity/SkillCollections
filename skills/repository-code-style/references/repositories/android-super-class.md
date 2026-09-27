# AndroidSuperClass 编码惯例

## 范围与作者覆盖

- 研究日期：2026-09-26；Java/Kotlin Android 主工程，含 basic、service、business 与多产品 source set。
- checkout：`feature/zp/feedback-audit`；HEAD：`574c4578d26a5a5460348b153f74ed280ffef67e`；工作区干净。
- 只读本地历史，未 fetch、checkout、安装或构建；不能证明远端最新状态、生产版本或运行正确性。
- 以下 AN1-AN9 是样本归纳；提交作者只证明其 diff，不代表整份文件或团队批准。
- HEAD 可达非 merge 记录：`zhaodexi@baijia.com` 211 条，`zhaodexi@baijiahulian.com` 982 条。
- 同范围：`zhenqiang@baijia.com` 1566 条，`zhangyu118@baijia.com` 3 条，`tangaoyang@baijia.com` 3 条。
- 全本地 refs 还出现赵德玺、甄强、张宇118的 `@gaotu.cn` 记录；邮箱别名不独立证明自然人身份。
- 候选 `zhangyu` 的实际匹配是 `zhangyu118`/张宇118；未发现无编号 `zhangyu` 身份，不混合其他同名作者。
- 张宇118的 HEAD 样本只有一条业务 diff，另两条忽略产物；唐傲阳只有一条完整 bridge 变更和两条接口路径修改。
- 深读下列业务 diff、同 revision 定义/调用方与 HEAD 路径历史；覆盖首页容器、登录、直播升级、短视频、AI 搜索。
- 若历史对象不可用，摘要仅作线索；重新读取目标模块，不能声称已复查或据此要求迁移全仓。

## 显式配置与文档

- tracked `.idea/codeStyles/Project.xml`：Kotlin official style；Java import 分组；XML 命名空间/id/style/Android 属性排列。
- 该配置关闭 editorconfig；未找到 tracked `.editorconfig`、ktlint、detekt、checkstyle 或 spotless 专用配置。
- tracked 文件列表未见 AGENTS、CLAUDE、Cursor rules 或 CONTRIBUTING；限定隐藏文件扫描也未发现对应文件。
- 根 AGENTS/CLAUDE 名称命中 ignore 规则，但磁盘不存在；ignore 匹配本身不能证明有规范或其团队属性。
- `app1/build.gradle` 的 lint 关闭 release 检查；多模块 `abortOnError false`，不能据此声称严格 lint 门槛已通过。
- 网络层 tracked README 位于 `basic/library_network/src/main/java/com/gaotu100/superclass/network/retrofit/kotlin/README.md`。
- 它说明 suspend API 返回业务 `Result`，调用用 `apiCall` 包装并区分 `Success`/`Failure`；不是全仓 Rx 迁移要求。
- `business/module_live/README.md` 说明业务/UI/Core 分层、源码/二进制切换及 `IProvider` 对外接口；作用限直播模块。
- HEAD `business/architecture_example` 提供 Repository/ApiResult/ViewModel/StateFlow/UIState 范例；它是示例，非作者样本。
- Java/Kotlin、Moshi/Gson、Rx/协程并存；格式和架构先跟目标目录，勿仅据某一范例统一全仓。

## 条件规律

### AN1：跨模块能力沿接口、实现、bridge 完整变更

- 适用：已有 H5 到直播服务的能力扩展；样本归纳。
- 提交：`e79816068cdad017b9a4fd6b40a587b7c288b661`；`tangaoyang <tangaoyang@baijia.com>`。
- 路径：`business/module_hybrid/src/main/java/com/gaotu100/superclass/hybrid/plugins/GTAppPlugin.java`，`showUpgradeApp`。
- 契约：`service/business/api_live/src/main/java/com/gaotu100/superclass/router/service/LiveVersionUpdateService.java` 与同层 `callback/ILiveVersionCallback.java`。
- 实现：`business/module_live/main/src/p_upgrade/java/com/gaotu100/superclass/upgrade/VersionUpdateServiceImp.java`，`showUpgradeApp`。
- 事实：接口增加 callback，实现接受/取消时回传 boolean，bridge 映射为 PluginResult OK/ERROR；沿 ARouter ServicePath 获取服务。
- 同 revision：实现持 Context 弱引用并经 ThreadManager UI 调度；API 留在 service 层，业务实现留在直播 source set。
- 使用：先检查共享契约和全部调用方，在现有 router 服务边界增加结果回传；避免 bridge 直接依赖业务实现。
- 边界：弱引用失效、低系统版本、无新版本分支没有回调；不能复制为“每个请求必终结”的模板。HEAD 路径历史无后续修正。

### AN2：Fragment 事件处理区分实例与视图生命周期

- 适用：实例已注册事件，但绑定/RecyclerView 尚未就绪；样本归纳。
- 提交：`157261da6951f36dd931c640969209301d9afa8f`；`zhenqiang <zhenqiang@baijia.com>`。
- 路径：`business/module_course_v2/src/main/java/com/gaotu/course/aisearch/tutor/TutorChatFragment.kt`。
- 方法：`onCreate`、`onEvent`、`onViewCreated`、`onDestroyView`、`onDestroy`。
- 事实：新增 isViewReady 和 pendingImageEvents；相关来源的图片事件先排队，视图创建后复制清空并重放，销毁视图重置就绪标记。
- 同 revision：EventBus 注册/注销跟实例，事件为 MAIN；Flow 观察用 repeatWithViewLifecycle，上传却用实例 lifecycle.coroutineScope。
- 使用：找到实际视图就绪点、来源过滤与事件所有者，再决定缓冲、重放和销毁清理策略。
- 边界：该补丁解决早到事件丢失，未保证上传回调跨 onDestroyView 安全，也未定义队列容量或进程恢复；不照搬为全局事件缓存。
- 后续：HEAD 路径历史该提交为最新；未观察到额外修正，不能据此宣称所有生命周期问题已解决。

### AN3：异步消息状态在实际消费点再次核对

- 适用：SSE 收包与 UI 延迟队列不同步、临时卡存在互斥语义；样本归纳。
- 提交：`ec07425bd62fc2fdb985e8e8a98de076c3e339cd`；`zhenqiang <zhenqiang@baijia.com>`。
- 路径：`business/module_course_v2/src/main/java/com/gaotu/course/aisearch/fragment/AISearchFragment.kt`。
- 方法：`onMessage`、`appendAIMessage`、`insertAIReturn`。
- 事实：恢复消费阶段 25/32 临时卡互斥判断，enum 取 code；末尾为异类临时卡才移除，同类留给覆盖更新。
- 同 revision：Handler 延迟消费 dataArrayList；同类临时卡更新 moduleData，AI 文本才拼接，新结果移除临时状态。
- 使用：先区分覆盖、追加、替换，规则落实在实际写 adapter 的位置；注释解释队列竞态和业务语义。
- 边界：仅是末尾 25/32 规则；非通用同步锁。查询分支仍直接取末项，空列表风险需另查，不能复制其索引假设。
- 前序 `075439159c667816239fe8b257e9f7af3d829bbf` 同作者只补说明；注释存在不能证明当时互斥代码生效。

### AN4：复用卡片的本地展示状态由实体持有

- 适用：RecyclerView 重绑应保持首屏决策、协议含 JSON 扩展字段；样本归纳。
- 提交：`ca116175b676e28e8d02131d4ac9c4538c33032b`；`zhenqiang <zhenqiang@baijia.com>`。
- 路径：`business/module_course_v2/src/main/java/com/gaotu/course/aisearch/api/model/AISearchModuleInfo.kt`、`business/module_course_v2/src/main/java/com/gaotu/course/aisearch/api/model/AskingExt.kt`、`business/module_course_v2/src/main/java/com/gaotu/course/aisearch/card/EveryoneAskingCard.kt`。
- 方法：`AskingExt.parseTotalCount`、`EveryoneAskingCard.bind`、`animateAdd`。
- 事实：Boolean? 的 null 表示未计算；首屏 question 数与 totalCount 决定可见性，缓存在 moduleLocalData，换一换/重绑沿用。
- 同 revision：moduleLocalData 在外层标记 Transient；解析用 JSONObject 和具名 key/default；XML 初始隐藏，动画只加入可见项。
- 使用：明确服务字段、本地状态及未初始化语义；重复解析放贴近模型的小 helper，动画不能覆盖隐藏条件。
- 边界：首次缓存是此业务要求；动态总数需更新时应重新定义失效条件。此处解析失败降级 0，不适用于必须报错的字段。
- 反例：模型同时有外层 likeState 等本地字段；不能宣称全仓本地字段都严格位于 Transient 对象，HEAD 未见后续修正。

### AN5：埋点入参从当前 UIState 传递，公共映射集中

- 适用：短视频卡片曝光/点击增加动态维度；样本归纳，作者覆盖有限。
- 提交：`49ee3386e00441d09ba8b4510923ebab72cc07bc`；`zhangyu118 <zhangyu118@baijia.com>`。
- 路径：`business/module_shortvideo/src/main/java/com/gaotu100/shortvideo/adapter/viewholder/ShortVideoViewHolder.kt` 与 `statistic/VideoTracker.kt`。
- 方法：`trackCourseShoppingCartShow`、`trackCourseShoppingCartClick`、`ProductContent.makeParams`；点击绑定在 `ItemShortVideoBinding.initListener`。
- 事实：曝光与点击传 uiState.id；Tracker 复用 product.makeParams，追加 moment_id，保持原事件 ID 与 list_order 的位置加一口径。
- 同 revision：曝光受购物车可见与当前选中视频约束；点击走 setSafeClickListener，并使用同份 UIState 的 jumpUrl/product。
- 使用：在状态所有者取维度，沿现有 tracker 扩展，核对曝光和点击两条链路；协议键留在统计边界。
- 边界：位置有效性、曝光去重未由这次 diff 保证；相邻多商品埋点仍有自身映射，不能要求所有场景都携带 moment_id。
- 后续：HEAD 的 VideoTracker 路径历史该提交最新；不由一条业务提交推断该作者全平台风格。

### AN6：重复业务变换集中，调用方保留各自协议

- 适用：登录/绑定多个 ViewModel 需要一致变换；样本归纳，非加密设计建议。
- 提交：`afada90d29d5ada96c7b5b97211c9aead1e95157`；`zhaodexi <zhaodexi@baijia.com>`。
- 路径：`service/business/account/src/main/java/com/gaotu100/superclass/account/encrypt/LoginAesEncryptor.kt`，`encrypt`/`decrypt`。
- 调用：`service/business/account/src/p_login/java/com/gaotu100/superclass/account/AccountLoginViewModel.kt`，`loginByPassword`，以及 V2、绑定、密码 ViewModel。
- 事实：新增 object 工具；调用点先沿 CommonPhoneNumberUtils 规范区号，再变换请求字段，密码/风控及其他字段保留原流程。
- 同 revision：ViewModel 同时有 viewModelScope 状态收集与 Rx/BaseObserver 请求；不能据此强制所有接口改为协程。
- 后续 `11e08d6ad94c07b51f2f28b6b0e027a6ef2a3cdd` 同作者改私有构造方式、lazy 缓存；工具调用 API 保持。
- 使用：共享稳定算法归现有领域工具，API 参数语义仍由调用方表达；异常策略结合调用链核对。
- 边界：历史算法和材料混淆不是安全标准；encrypt 在请求订阅之前可抛异常，不能把 BaseObserver 当所有失败的处理者。

### AN7：共同交互流程抽私有方法，差异显式传入

- 适用：同视图工具栏/面板共用分发逻辑但埋点、草稿处理不同；样本归纳。
- 提交：`7731e62dff42387d1be0cd2a2c4d48330e77ec4c`；`zhenqiang <zhenqiang@baijia.com>`。
- 路径：`business/module_course_v2/src/main/java/com/gaotu/course/aisearch/card/view/ChatInputView.kt`，`bindAISearchTools`/`handleToolClick`。
- 事实：把嵌套函数抽私有方法，传 trackClick 与 clearInputAfterClick；禁用态 early return，AIToolsType 合并相同路由分支。
- 同 revision：面板类展开时不关输入框/不清草稿；未知工具有 jumpUrl 才导航，缺失记录 tracker，避免默默清空。
- 前序 `cf286347886a5faf51bb1834b4ea4c852c1bae00` 同作者明确工具栏 true、面板 false，修正此前统一清理草稿行为。
- 使用：复用流程并把真实差异作为参数；命名常量/enum 表达分发，保持 UI、导航、埋点、副作用顺序。
- 边界：不是所有 Boolean 参数都值得推广；需要多种独立策略时重新评估类型，不能以“统一点击”抹平入口差异。

### AN8：容器级一次副作用明确作用域和时点

- 适用：首页初始化完成的进程内一次统计；样本归纳。
- 提交：`21483d6b842e858cb6ad24229f2ee8511f8151ed`；`zhaodexi <zhaodexi@baijia.com>`。
- 路径：`business/launch/src/main/java/com/gaotu100/superclass/ui/activity/BaseMainActivity.kt`，`onCreate`/`reportHomeContainerInitialized`。
- 事实：companion AtomicBoolean.compareAndSet 门控；initView/initData 与首页容器性能结束节点后调用具名方法。
- 同 revision：首页绘制另有 onHomeContentOnPreDraw/onFirstScreenRendered；此事件只表示容器初始化。
- 使用：副作用单独命名，明确 Activity、进程、安装级作用域；沿既有 Tracker 与启动时序挂接。
- 边界：AtomicBoolean 只管进程内一次，不是安装持久幂等；重启会再次报告，不能替代业务去重。
- 后续：HEAD 仍保留该门控及调用；Env 首次安装判定只是事件维度，不能据标题推断只在首次安装上报。

### AN9：调试细节通过既有开关控制，日志默认成本可见

- 适用：公共日志/统计初始化需要减少调试输出成本；样本归纳。
- 提交：`fab56b144139f34cf7b434135083e56acd12ad9c`；`zhaodexi <zhaodexi@baijia.com>`。
- 路径：`basic/logs/src/main/java/com/gaotu100/superclass/base/logger/MyLogger.java`，`isShowDefault`；`service/basic/hubble/src/main/java/com/gaotu100/superclass/base/statistical/HubbleStatisticsUtils.java`，`initHubbleStatistic`。
- 事实：MyLogger 默认简化输出；Debug Hubble 默认 error，偏好开关允许 debug；DebugApplication 注册 KitHubbleLog 操作既有 Storage。
- 使用：业务诊断复用目标模块 logger/Tracker；区分细节开关、本地显示与真实统计上传，不随意改全局默认。
- 边界：本提交不证明 Release SDK 默认级别；debugkit 的 System.exit 重启只属调试工具，不能推广到业务代码。
- 后续 `75635aa64a3b880db047b61fae329f4d530d312d`，`zhuwen02 <zhuwen02@gaotu.cn>` 给 `MyLogger.d(String)` 加空值早退；旧工具需核对最新实现。

## 复查

- 用 `git show <完整提交> -- <相对路径>` 看差异，`git show <提交>:<路径>` 读相同 revision，沿方法查看调用与后续修正。
- 这些路径是可选证据，不是运行依赖；实际任务用当前模块范例和最小验证，本研究未执行构建、设备测试或 leader Review。
