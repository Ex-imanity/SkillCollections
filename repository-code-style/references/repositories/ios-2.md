# iOS_2 客户端条件范例

## 范围、规范与作者覆盖

- 研究日期 2026-09-26；checkout `feature/aiSearch/0901`，HEAD
  `0b631010f9e6779ccd5141f117d8d74e42c0cf76`。已有 GTGeneralFileUploadManager.m 修改，
  未修改或作为本次历史作者证据。未 fetch、pod install、生成工程或构建。
- 本地所有 refs 非 merge 记录：zhaodexi@baijia.com 169、早期 baijiahulian.com 22；
  tangaoyang@baijia.com 2647（含中文名 1）、相同显示名 qq 邮箱 258 未合并身份；
  zhangyu118@baijia.com 1826；未发现 zhenqiang。按邮箱定位，不把 zhangyu 同名泛匹配归因。
- 深读 6 个业务差异及对应上下文，涵盖 Hybrid、RN bridge、相机、路由和图片加载。
  样本在本地 refs 可用，不保证都在 HEAD；重复 cherry-pick 不算独立规范支持。
- 未发现 tracked AGENTS.md、CLAUDE.md、Cursor、editorconfig、clang-format 或
  swiftlint 规则；不据此声称没有任何团队规范，也不强制新增 formatter。
- tracked XcodeGen/README.md 说明矩阵壳工程生成和产品差异；业务模块 podspec
  划分 Core 与产品 subspec、声明源码/资源与依赖。以目标模块实际 podspec/工程为准。
- Business/GTAI/README.md 是 CocoaPods 模板，名称与 GTAI.podspec 不一致，不能
  直接当当前构建命令或公开组件规范。GTHybrid README 的有效接口说明仍要核对头文件。
- 以下均为条件归纳，不规定全部模块必须 Objective-C、Masonry、category 或同一种
  weak 宏。新增代码沿用当前模块语言、类型、内存语义和布局 API，避免跨语言重写。

## IO1. 在既有 Hybrid 插件保持参数和页面配置

- 作者 zhaodexi@baijia.com；commit `144ed7699a1a2f154e95b22b57f18c25475ab4fc`。
- 路径 `Services/Basic/GTHybrid/Sources/Plugins/HybridRouter/GTHybridRouterPlugin.m`；openWindow。
- 事实：特定端能力从新旧 Web 分流改为 GTHybridViewController，继续通过现有
  safeStringForKey/safeString 读取协议值，保留方向、导航栏、状态栏、reportParam、缓存和 UA 配置。
- 条件：端能力变更在既有插件与容器边界处理，同时读调用参数及页面创建后的动作。
- 限制：这是一次明确的容器迁移，不能推所有旧 Web 页面都要改；nil 安全工具不能
  代替任意值类型校验，不把删除旧框架埋点当成普遍允许删除埋点。

## IO2. 异步队列区分设备操作与 UI 更新

- 作者 tangaoyang@baijia.com；commit `bc54f531a984a2e715b007a45433db714959966a`。
- 路径 `Business/GTAI/Sources/Core/Camera/GTAINewHomeWorkCameraPreview.m`；sessionStart、
  setSessionShouldRun、addPreviewLayerWithSession、lightDeviceChange。
- 事实：相机 session 操作使用实例串行队列，UI 层和提示回主队列；窗口移除时停止，
  shouldRunSession 限定晚到权限回调；预览层/observer 防重复，block 用 weak/strong 生命周期检查。
- 条件：耗时设备操作与 UI 更新分别沿已有队列约定，检查授权晚到、离页与重新显示。
- 限制：样本并非完整线程安全审计；部分回调路径和 observer 移除后的标记还需核对。
  不要求所有 block 一律弱引用，也不为普通轻量函数创建串行队列。

## IO3. 导航完成顺序按真实 push/present 容器判断

- 作者 tangaoyang@baijia.com；commit `a6a4dd34dfa59f28966ce9a39d3e6b2ba9456b59`。
- 路径 `Services/Basic/GTHybrid/Sources/Plugins/HybridRouter/GTHybridRouterPlugin.m`；openScheme。
- 事实：用 GTBaseUIManager 获取来源；push 栈移除来源后调 schema，present 在
  dismiss completion 后调 schema，无导航容器时回退到来源 VC 本身。
- 条件：同时关闭旧页和跳新页时，沿既有 schema/router 且明确容器和动画完成语义。
- 限制：不能据栈长度推导任意复杂容器的来源关系；延时参数兼容性和其他场景仍需
  核对，不把该修正提升为全端统一跳转流程。

## IO4. RN bridge 沿现有类扩展并保留线程与类型

- 作者 zhaodexi@baijia.com；commit `174fa1b117db438e3124f43b2c25843d954fbc4a`。
- 路径 `Services/Business/GTReactNative/Sources/Core/Plugin/NativeIntent.mm`；copyToClipboard。
- 事实：在既有 NativeIntent 增方法，主队列写 UIPasteboard，nil 字符串回空串。
- 条件：native 实现和 RN Spec/导出机制一起核对，保持方法签名、同步/异步约定，
  无需为一个端能力增加第二套插件体系。
- 限制：此 diff 只证明实现方法，不单独证明每个产品的生成绑定与 JS 可调用性；
  空串 fallback 属于此契约，不把所有 nullable 输入静默吞掉。

## IO5. 复用异步图片使用实例上下文与过期回调判断

- 作者 zhangyu118@baijia.com；commit `e357e990d3f77696d7941a5dac989bf7eedbe6d7`。
- 路径 `Basics/GTUIKit/Sources/Core/BaseUI/Category/UIImageView+GTCriticalImage.m`；
  gt_setCriticalImageWithURL、gt_startRequestWithContext、gt_stopRequestAndPendingRetryWithContext。
- 事实：category 的 associated context 持有具名 URL/代号/重试状态；新请求、取消、
  挂起让 generation 失效，回调和延迟 block 均先核对；错误分类后有限次数重试。
- 事实：DEBUG 注入通过 hook，调试模块单向依赖 UIKit，不让基础组件导入 GTDebug。
- 条件：复用 UI 的图片/异步展示，优先现有 loader；检查同 URL 重新绑定、取消、离页与重试。
- 限制：重试次数、延时及状态码仅用于该关键图片能力，不推广所有请求；同步通知
  未加载状态不是“完成只调用一次”。后续 `6b83cb84f676a18638f31ef3c3a2aaf4c06b5d78`
  删除无调用方 loaded API，使用前查当前头文件。未执行安全/性能或 release 验证。

## IO6. 重复入口控制集中在业务 API，所有退出路径检查

- 作者 tangaoyang@baijia.com；commit `6464cd5b2d104b244f3c747f790ea66d029aa46f`。
- 路径 `Business/GTAI/Sources/Core/GTAISearchApi+Api.m`；pushToChatListHome。
- 事实：非主线程调回主线程，用当前 VC 与展示中标记避免重复拉起；沿原 GTBaseUIManager
  和自定义转场，present completion 释放标记，无导航容器提前退出。
- 条件：多个入口共享拉页能力时，在已有业务 API 约束操作并检查实际页面状态。
- 限制：静态标记可能跨产品/多场景共享，异常展示是否回调需单独验证；不在全部页面
  增全局锁，不把“不重复打开”自动推广成禁止所有栈内同类页面。

## 复查与可移植性

使用 `git show <完整commit> -- <仓库相对路径>` 检查差异，相关定义按同 revision 阅读。
缺少历史对象时本摘要是可选参考，依据当前模块继续；不声称已核对作者原始源码。
header 的 nullability、property 的 copy/weak/strong、模块 import、资源 bundle 与
产品 target 以目标代码/配置为准，不把抽样约定写成整个 iOS 工程的强制规则。
