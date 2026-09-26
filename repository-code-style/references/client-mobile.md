# 客户端条件偏好

适用于 RN、Android、iOS、HarmonyOS 的现有代码。以下是 skill 的条件偏好；
各平台 profile 的显式规范和取样边界分别列出，不是四位作者共同发布的标准。
只加载当前端与直接相关的跨端契约资料，不因客户端任务把四套工程全部扫描一遍。

## CL1. 按端、模块与产品选范例

- 先确认语言、模块职责、产品 source set/subspec、入口和编译依赖。Java/Kotlin、
  Objective-C/Swift/ObjC++、TS/TSX、ArkTS/C++ 不能仅因功能相似就互换写法。
- 新增命名、成员可见性、文件组织、导出、空值、注释和资源定位沿目标模块规则。
  RN 新文件依其 tracked 规则；Android 的 official Kotlin style 不等于后端 Java
  业务规则；iOS C++/ObjC++ 边界与 Harmony C++ formatter 不扩展为所有语言格式。
- 共用流程先复用既有组件、Repository、ViewModel、model、业务 API 与领域 helper。
  业务差异留在现有产品/模块边界；新增抽象须减少具体重复，不默认引入跨端统一层。
- 证据：RN 团队规则、AN 显式配置/AN6/AN7、IO1、HM 显式架构/HM7。

## CL2. 沿完整 bridge 和路由契约改动

- 涉及端能力，检查声明/Spec、helper、native 实现、导出或生成注册、调用者与
  对应产品能力。只检查这次能力的链路，不借机统一其他旧插件。
- 参数名/顺序/数量、返回字符串或对象、Promise/callback、错误形状、线程、事件名、
  协议 action 及缺能力行为都属于契约。不能把 void 改成 Promise 就声称已可等待，
  或把方法在 native 类中存在当作 JS 运行时已注册。
- Promise 的成功、失败、缺能力、权限拒绝/取消分支需有明确结束；不能用可选调用
  加 new Promise 留下悬挂。流式事件或多次状态通知有不同语义，不强制一次回调。
- 生成文件先核对源声明、生成过程和产品产物；优先改可维护的来源并核对生成差异。
  历史手工绑定修复说明检查点，不授权猜造生成器或每次手改全部生成物。
- 跳转沿既有 router/schema/provider/navigation；区分 RN 栈内返回、关闭原生容器、
  push、present、仅通知现有页面。必要业务同步和动画完成顺序按当前契约决定。
- 证据：RN3/RN4、AN1、IO1/IO3/IO4/IO6、HM3/HM4。

## CL3. 生命周期检查资源的真正所有者

- 找到任务、订阅、队列、timer、binding、音频/相机、图片加载的拥有者。Android
  Fragment 实例与视图生命周期不同；RN effect 与长回调的 ref/state 不同；iOS
  view/window/VC 生命周期不同；ArkUI 页面订阅按其实际挂接和解除点判断。
- 读取回调/队列实际执行上下文，UI 在该端允许的线程更新。离页/销毁/重建/复用后
  的旧结果需按现有取消、代号或身份策略处理；同 ID 的新请求也可能使旧结果失效。
- 取消调度、解除订阅和清理资源要覆盖失败路径，并保持同一 callback/资源身份。
  不仅检查是否有 cleanup，还检查异步注册晚到、重入、多实例和清理后的新回调。
- 已由 ViewModel 或业务层持续运行的工作，不为保护 UI 顺带停止；只调整本次需要
  的视图观察边界。全局 loading、静态锁与进程一次标记不能冒充实例生命周期控制。
- 证据：RN1/RN6/RN7、AN2/AN3/AN8、IO2/IO5/IO6、HM2/HM4/HM5。

## CL4. 模型、状态与数据转换保留业务语义

- 复用现有 DTO/entity/view model 和 serializer；把复杂重复转换放在贴近领域的
  小方法，简单字段访问保持局部。服务字段、本地展示状态和缓存的归属分别确认。
- 本地状态需 transient/忽略序列化时遵循目标 serializer，不凭命名推断已被排除。
  0、false、null、undefined、空串、未知 enum 和字符串 ID 按契约处理。
- 区分状态覆盖、流式追加、卡片替换及临时占位；异步队列的规则在实际消费点复核。
  展示占位资源不能污染原始数据；动画不得覆盖业务隐藏条件或丢弃待应用新状态。
- 编码、签名、表单/JSON、查询位置和解包保持已有请求入口，例外限定具体接口。
  从加密样本只借鉴 helper/类型/调用边界，不将历史算法或材料混淆推荐为安全标准。
- 证据：RN2/RN5/RN7/RN8、AN3/AN4/AN6、HM1/HM5/HM6。

## CL5. UI、工具与诊断沿当前平台约定

- 复用主题、字体、布局宽度/安全区、资源 bundle/Resource、列表和点击工具。RN
  当前 press guard 要按 tracked 规则选，不因为旧作者用过 safePress 就继续新增。
  不为所有端强设同一防抖值、尺寸、动画库或“任何方法都 memo/weak”的规则。
- 业务埋点沿 tracker/logger，核对入口、事件 ID、source、位置/计数口径和动作
  顺序。重复点击控制需保留不同入口的草稿、禁用态、导航和权限差异。
- 调试注入/日志开关限定构建和模块依赖；本地调试代码不反向污染基础层，不提交
  个人签名、环境产物或无关生成文件。配置中开关存在不等于 release 行为已实测。
- 证据：RN 团队规则/RN7/RN8、AN5/AN7/AN9、IO5、HM6/HM7。

## CL6. 验证范围跟随实际改动

- 核对项目真实的 build/test/lint/codegen 命令、目标模块/产品和本机可用环境；
  按当前规范和风险选最小验证。不可用时明确未运行及尚未证明的跨端行为。
- bridge 改动检查签名、运行时注册和拒绝/取消；视图异步检查离页、重建与旧结果；
  序列化检查本地状态与原协议；UI 检查本次目标端的宽度、安全区、资源与布局。
- 不为了资料提炼安装 SDK、生成签名、同步 bundle、运行全端构建或修改业务仓库。
  真实开发需要这些操作时由主任务授权与项目流程决定，本 skill 不另开操作流程。

## 平台资料

| 当前端 | 条件范例与明确边界 |
| --- | --- |
| RN / RNSuperHigh | [rnsuperhigh.md](repositories/rnsuperhigh.md) |
| Android / AndroidSuperClass | [android-super-class.md](repositories/android-super-class.md) |
| iOS / iOS_2 | [ios-2.md](repositories/ios-2.md) |
| HarmonyOS / HarmonySuperHigh | [harmony-super-high.md](repositories/harmony-super-high.md) |

编号在相应 profile 中定位。它们是按端拆开的 reference，保持一个流程入口；
未来平台确有独立工具执行流程时再拆 skill。没有历史 repo 也可依据本摘要与当前模块
继续，不能声称已核查缺失源码、作者身份、设备行为或 leader 批准。
