# HarmonySuperHigh 客户端条件范例

## 范围、规范与作者覆盖

- 研究日期 2026-09-26；checkout `feature/aisearch/harmony-add-mistake`，HEAD
  `13e03981663232fe3c505dc9fea1ccc6e25f2629`，工作区干净，本地跟踪分支显示落后 1。
- 未 fetch；深读 9 个业务/修正差异及相关上下文。部分样本来自其他本地 refs，
  不代表当前分支已包含，也不证明已部署。重复 cherry-pick 不计作独立规则证据。
- 本地所有 refs 非 merge 记录：zhaodexi@baijia.com 73、早期 baijiahulian.com 1；
  zhenqiang@baijia.com 118；tangaoyang@baijia.com 3；zhangyu118@baijia.com 20。
  本文按邮箱定位；zhangyu118 不自动等于所有名为 zhangyu 的作者。
- 未发现 tracked AGENTS.md、CLAUDE.md、Cursor 规则或 editorconfig；`.clang-format`
  明确 `Language: Cpp`、4 空格、120 列，不能将它用于 ArkTS 格式或强制全仓格式化。
- tracked `README.md` 明确 app/basic/service/business 层、NavigationRouter 和
  DynamicProvider 的跨模块边界；推荐 GTMMKVStorage。这是显式架构说明，使用时
  仍核对目标模块实际 router/provider。不要把 README 的环境安装步骤自动执行。
- README 要求 RN 与 Harmony 分支配套，bundle/资源不提交，手动签名修改不提交；
  对跨端任务核对对应 RN 源分支和产物来源，不据一个端的 HEAD 推断整套产物一致。
- 以下是条件归纳，非四位作者共同标准。带 AI co-author 的提交不作为纯个人手写
  风格证据；提交信息中的构建成功不等于本次已验证。缺源码时摘要可参考，当前规范优先。

## HM1. 请求编码修正在既有网络边界处理

- 作者 zhaodexi@baijia.com；commit `611d4fdb2cba2a11fe6a02ab0ecc94eca3af8d59`。
- 路径 `basic/library_network/src/main/ets/ApiInterceptor.ets`；`filterExtraData`、
  新 helper `encodeFormComponent`。
- 事实：FORM 分支编码键和值，签名仍使用原始值；JSON 分支不拼 form 文本。
- 条件：修正现有编码契约时，分清签名输入、传输编码与 contentType，复用原入口。
- 限制：不能推广为所有参数都重复 urlencode；该函数修改原 param 的历史行为仍需
  按调用契约核对，不复制其中旧硬编码或把整个 interceptor 当最佳实践。
- 上下文 `basic/library_network/src/main/ets/ApiService.ets` 的 unifyFetchRequest
  使用 assembleUrl/filterExtraData/headInterceptor/filterResponse，不新建第二套公参体系。

## HM2. 回调内的异步异常在真正执行边界收尾

- 作者 zhaodexi@baijia.com；commit `327691703830886d110c9878749597717c0a1717`。
- 路径 `business/module_react_native/src/main/ets/turboModules/NativeIntentTurboModule.ets`；
  `getAutoLocationAreaList`。
- 事实：给定位成功的 async 回调内增加 try/catch，将 nearbySearch/坐标转换异常 reject；
  原来只有注册回调外层 try/catch，不能捕获后续 async 拒绝。
- 条件：保持 Promise 的 JSON 字符串返回与错误路径，检查 SDK 失败/能力不支持的分支。
- 限制：样本多个 reject 不携带错误，不升级为统一错误规范；未证明所有权限/定位
  回调都恰好调用一次或所有产品地图服务均已启用。

## HM3. TurboModule 检查实现、注册与参数契约

- 作者 tangaoyang@baijia.com；commits `c546395cd2a49307972a15d4d2b991355b3e8adf`、
  后续 `082e07fa120c4eda36f1f4101a626c77ba6b9895`。
- 路径 `business/module_react_native/src/main/ets/turboModules/NativeNetworkTurboModule.ets`
  的 uploadFile；`business/module_react_native/src/main/cpp/generated/NativeNetwork.cpp`。
- 事实：ArkTS 上传读取沙箱文件、复用认证 header，返回原始响应字符串；后续在
  methodMap_ 增加 `ARK_ASYNC_METHOD_METADATA(uploadFile, 4)`，才补齐 C-API 调用入口。
- 条件：跨端能力沿 RN Spec、native 实现、运行时绑定和消费者一起核对，保留参数
  数量/顺序、异步约定和错误形状。生成来源先查项目流程，不能仅改一个生成文件。
- 限制：历史补丁不是长期手工维护生成物的规范；bodyJson 解析、已有 URL query
  拼接仍有边界风险，不整段照抄上传代码，也不通用化固定的上传字段名。

## HM4. 深链动作沿 router 常量和成对事件订阅实现

- 作者 zhenqiang@baijia.com；commit `05d644951cb2ae24a336fa98af3e94a612203c87`。
- 路径 `basic/library_router/src/main/ets/router/model/RouterModel.ets`，
  `basic/library_router/src/main/ets/utils/DeepLinkDispatcher.ets:openPageByAction`，
  `business/module_ai_search/src/main/ets/pages/AISearchEntryPage.ets`。
- 事实：命名常量 AI_SEARCH_IMAGE_QA_EVENT；dispatcher 发事件，已有页面用稳定
  imageQaCallback 订阅，并在 removeEventListeners 中用同一 callback 解除。
- 条件：协议要求只通知已打开页面时，保留“无人订阅静默”的语义，不擅自创建页面。
- 限制：不推广为所有深链都发 emitter；同文件其他 eventHub 的宽 off 不作为推荐。
  window Promise 延迟注册是否跨越页面消失仍需检查，成对代码不等于无生命周期竞态。

## HM5. 事件合并限定请求范围，timer 随页面清理

- 作者 zhenqiang@baijia.com；commit `8260adb92b9d1e68a1ec9a6044c4a54ef4dffe23`
  标有 AI co-author。
- 路径 `app/src/main/ets/components/home/GaoTuHomeComponent.ets`，
  `business/module_ai_search/src/main/ets/pages/AISearchEntryPage.ets` 及各自
  `repository/AISearchConfigRepository.ets`；scheduleAiSearchConfigRefresh/buildConfigUrl。
- 事实：配置请求尾部防抖，主首页请求仍即时；timer 清零并在消失时取消；配置 GET
  将有效 gradeId 放 URL，适应此版本 wrapper 的 param 进入 extraData 的行为。
- 条件：确认同一业务动作产生重复事件后，只合并允许延迟的请求；请求字段位置看 wrapper。
- 限制：500ms/正 gradeId 是该业务选择，不能移植给所有字段；复杂 query 需既有
  编码工具。已有 requestId 检查也不自动证明页面退出后所有响应都失效。

## HM6. 资源转换保留服务端数据与调试隔离

- 作者 zhangyu118@baijia.com；commit `498babffa1c23af753e959ffa5fefc53c65761f2`。
- 路径 `app/src/main/ets/utils/KingKongIconAsset.ets:resolveKingKongIcon`，
  `app/src/main/ets/utils/Grid.ets`，
  `app/src/main/ets/components/home/gaotu/GTCommunityAdCardComponent.ets`。
- 事实：集中内置资源映射，展示入口命中 Resource，未命中继续原 URL；未回写 icon。
  校验开关受 BuildProfile.DEBUG 限定，资源和映射同时新增。
- 条件：固定图标内置时沿现有图片组件，保留 placeholder、未知资源 fallback 和类型。
- 限制：按文件名认资源只适合这里的唯一命名约定，不能用于任意远程 URL；未实际
  构建验证 release 分支裁剪，不把“所有图片必须内置”写成规范。

## HM7. 产品与容器差异留在现有上下文边界

- 作者 zhaodexi@baijia.com；commit `96ce42b8186b655a5b5bba99cc47d7f300921653`。
- 路径 `basic/library_router/src/main/ets/utils/DeepLinkDispatcher.ets:openPageByAction`；
  事实：home_page 按 AppContextHolder.productName 区分心理产品 COURSE 与其他 HOME。
- 条件：修正产品路由先核对矩阵配置、原协议与 tab；不另造全局产品识别。
- 补充作者 zhangyu118@baijia.com，commit `27a42c340994cccad64bb8428070d0dc0958133f`，
  `app/src/main/ets/components/CustomHomeTabView.ets:CustomHomeTab`：padding 对齐同级 tab。
- 限制：产品判断和底部 36 均为局部协议/布局事实，不升级为统一常量或全局安全区公式。
