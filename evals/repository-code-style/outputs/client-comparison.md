# 客户端扩展配对评估摘要

日期 2026-09-26。旧版使用编辑前的 1.1.0 快照，新版使用 1.2.0；分别处理同一
client-scenarios.md 的 S10-S12，未读取对方结果或 evals.json 期望。本文件是人工
整理的草图摘要，不是执行日志。两名评估者此前分别参加 Android/RN 取样，存在研究
背景污染，因此不是完全盲测；未用该结果证明增益或自动触发能力。

## S10：RN helper 与 Harmony 注册

旧版用显式 Promise<string> named export，先保存 NativeDraft 局部引用；缺模块
返回 Promise.reject(createCapabilityError('saveDraft'))，否则直接返回 native
Promise。新版用 async named export，缺模块 throw 同一错误，await native Promise。
二者都保留 id/raw/overwrite 原值与 reject，不复制悬挂的可选调用包装。

二者都指出 registry 需新增 saveDraft/arity=3，对应生成 methodMap 需包含
ARK_ASYNC_METHOD_METADATA(saveDraft, 3)；不把 ArkTS 实现存在当注册完成。
只给 fixture 注册草图，没有运行 generator 或推测实际业务生成器。

二者的最小验证均包括缺能力、成功、失败、false/字符串保持和来源/产物一致；
新版另明确完成 Promise 与状态通知的区别，并引用 CL2、RN4、HM3 条件参考。

## S11：Android view 生命周期

二者均在 onViewCreated 后沿 repeatWithViewLifecycle 收集 Repository.status，
调用 private renderStatus，保留 ViewModel 刷新与实例 EventBus 的原范围。
旧版 render 草图明确读取当前 _binding；新版保留具体 UiState 映射为待接入方法，
说明实际 helper 形状沿模块定义，不捕获旧 binding。

二者均建议检查 view 销毁不访问旧 binding、刷新继续、新 view 收到最新值以及
不残留 collector。新版引用 CL3/AN2；未迁移 fetch 或增加事件缓冲。

## S12：iOS cell 复用

二者都捕获 bindingGeneration、弱 cell，在 main queue 取得有效对象并最终核对
generation 后调用私有 renderSubtitle。旧版另检查 representedID，新版以代号
覆盖同 ID 新 revision。两者保留原 bind/reuse 增量、public header 与原 text。
fixture 未提供真实 selector，二者没有虚构完整业务调用。

最小验证均包括后台回调/main UI、同 ID 新 revision、reuse 与 cell 释放；新版
引用 CL3/IO2/IO5。不依赖取消成功，也不新增全局锁。

## 结论与限制

人工对照 evals.json，三场景两版均符合期望，未测得基本行为改善。输入直接提供
契约、规范、生命周期和错误反例，容易导向正确结果。仅为代码草图，没有编译、
运行时、设备、bundle 或 codegen 测试，也未验证真实 leader Review 返工数量。
本次有效证据是资料的可追溯性、条件边界及分发一致性；实际约束效果仍需真实任务验证。
