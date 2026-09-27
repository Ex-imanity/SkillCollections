# RNSuperHigh 编码模式参考

## 范围与证据边界

- 2026-09-26 只读研究本地 Git 对象；未 fetch、checkout、安装依赖或运行构建。
- 快照分支为 `feature/zp/feedback-category`，HEAD 为 `fb4e17202d29b1a31423ab56b5917343b156c4fe`。
- 工作区已有修改与未跟踪文件；历史与现状比对均用 `git show`，不把未提交代码作为团队规范。
- 作者候选使用 `git log --all --no-merges` 筛选；merge、资源压缩、生成 demo、纯机械格式调整未用作模式证据。
- 相同修改的 cherry-pick 只算一个模式；提交作者仅证明该 diff 的归属，不能证明整文件由其设计。
- 以下路径均相对仓库根目录；使用时以目标 checkout 的显式规则和同模块契约优先。
- 不要求使用者持有研究快照：每条提供方法、行为与边界；缺失历史对象时不能声称已复查。

## 团队规范与身份核实

- 跟踪入口：`AGENTS.md`、`CLAUDE.md`、`.claude/CLAUDE.md`；正文统一到 `.agents/rules`。
- Cursor 的 `.cursor/rules/platform/reactnative.mdc` 是适配入口，范围为 `src/**/*.{ts,tsx}`。
- RN 正文 `.agents/rules/platform/reactnative.md` 要求 TS、优先 interface、函数组件/Hooks、named export。
- 同规则指定主题颜色、`GTFontStyles`、FlashList、安全区工具；新页面注册 `App.tsx` 与 `PageConstants.ts`。
- `.agents/rules/base/general.md` 要求分层、相关功能同模块、避免反向依赖、复杂逻辑注释和新文件头注释。
- `.agents/rules/workflow/ui-components.md` 指定复用 `src/basic/gtui`，优先组合已有组件。
- `.agents/rules/workflow/click-debounce.md` 指定每按钮独立 `usePressGuard`；旧 `safePress`、`debounceClick` 不宜新增。
- `.agents/rules/workflow/reanimated-istanbul.md` 要求忽略注释紧贴 worklet 箭头函数节点。
- `.eslintrc.json` 实际配置限制 `accessories > biz_modules > service > basic` 的反向依赖。
- `module_mine` 有专门宽度限制：使用 `useMineLayoutWidth()`，不能把窗口宽当作平板双列可用宽。
- `tsconfig.json` 启用 strict、noEmit 与模块别名，但关闭 strictFunctionTypes、noImplicitReturns 等部分检查。
- `.prettierrc.cjs`：2 空格、120 列、单引号、无分号、无尾逗号、箭头参数括号、LF。
- `.editorconfig` 通用缩进是 4 空格，与 Prettier 冲突；TS/TSX 采用现有格式器及目标文件风格，不全仓重排。
- `package.json` 有编译/启动脚本但未定义 lint/test 脚本；不能宣称已存在可直接运行的统一验证命令。
- `README.md` 是混合跨平台工程运行说明；个人 ignored 配置不纳入团队规范来源。
- Git raw author 核实到 zhaodexi/赵德玺：`zhaodexi@baijia.com`、`zhaodexi@baijiahulian.com`、`zhaodexi@gaotu.cn`。
- 核实到 zhenqiang/甄强：`zhenqiang@baijia.com`、`zhenqiang@gaotu.cn`，有非 merge 业务样本。
- `zhangyu` 检索命中 zhangyu118/张宇118：`zhangyu118@baijia.com`、`zhangyu118@gaotu.cn`，有业务样本。
- 未核实到字面作者 `zhangyu` 的身份；本页只把张宇118作为候选近似匹配，不合并其他同名人员。
- 核实到 tangaoyang/唐傲洋：`tangaoyang@baijia.com`、`tangaoyang@gaotu.cn`，有多模块业务样本。

## RN1：异步操作的资源清理覆盖失败路径

- 条件：页面启动一个有明确结束点的异步任务，并显示 loading 或占用临时资源。
- 证据：`9d3cb101e1bf88dbe2565f2e577857c4c949dc17`，zhaodexi `<zhaodexi@baijia.com>`。
- 路径：`src/biz_modules/module_setting/main/src/pages/AddressList/AddressOperateDialog.tsx`。
- 方法：`getLocationAuthentication`；定位授权成功后 `showLoading()`，再请求 `getAutoLocationAreaList()`。
- diff 将 `hiddenLoading()` 从成功 `.then` 移到 `.finally`；catch 仍记录失败，成功仍设置地址与弹层。
- 同 revision 上下文显示授权失败发生在外层 Promise，此时尚未 showLoading，不能机械扩大清理范围。
- 复用：成功处理数据，失败处理错误，最终分支负责本任务拥有的清理动作。
- 边界：并发任务共享全局 loading 时还要核对所有权；finally 本身不能解决全局计数、取消或卸载问题。
- 反例：原实现只在成功时隐藏 loading，定位 reject 后会残留加载状态；不复制该旧写法。

## RN2：原生协议转换集中到有类型的业务 helper

- 证据 A：`430bfdbe2da21b5ba7b7889fd33ee685d2e5a54a`，zhaodexi `<zhaodexi@baijia.com>`。
- 路径：`src/biz_modules/module_account/main/src/helper/LoginAesEncryptor.ts`；方法 `encryptLoginMobileField`。
- 同 diff 的 `hook/usePassCodeVerify.ts` 先 `transformToAreaPhone` 再转换，服务请求字段同步改为 `mobileEnV1`。
- `service/LoginService.ts` 的重置密码、微信绑定、验证码验证、换绑参数类型一并更新协议字段。
- 证据 B：`b7997ba722605e73ae90bc893428c65f50463ef0`，同作者邮箱；方法 `getLoginAesKeyWordArray`。
- 后续 diff 把返回 `any` 改为 `CryptoJS.lib.WordArray`，以 nullable 模块变量懒缓存解析结果。
- 条件：多个同域调用方需要完全一致的协议转换，且有现成库类型可表达中间值。
- 复用：把算法与序列化留在 helper，调用方保留业务输入构造；明确返回类型，复用稳定中间结果。
- 边界：协议字段名是兼容合同；迁移必须连同服务端约定核对，不能为风格任意改名。
- 反例：该 AES 模式、静态 key 与混淆方案是历史协议实现，不代表可推荐的密码学设计。

## RN3：原生容器关闭前完成必要的业务同步

- 证据：`b88ea772c9173118fa678cc0474b0ee5604cdab7`，zhangyu118 `<zhangyu118@baijia.com>`。
- 路径：`src/biz_modules/module_account/main/src/pages/BindWechatConflictPage.tsx`，方法 `onbind`。
- 配套路径：`src/biz_modules/module_account/main/src/service/BindWechatConflictService.ts`，方法 `continueBindWechat`。
- diff 在不能 navigation.goBack 的分支，把 `loginStatus(true)` 移到 `closeScreen()` 之前。
- 同 revision 成功分支有 RN 栈内返回与原生容器关闭两种退出方式；同步顺序只修正后一种。
- 后续证据：`1c9af0cee3dc33ea6fefb301b5cdacf7ccd9be54`，lanhaiting `<lanhaiting@baijia.com>`。
- 后续 service 将通用 `loginStatus(true)` 替换为 `bindWechatConflictFinish()`；该快照 HEAD 仍使用专用事件。
- 条件：关闭 RN 容器会影响后续 bridge 通知或业务接收时机；先核对当前账户/导航工具的契约。
- 复用：保证必要同步先于销毁或退出；使用当前专用完成事件，保持栈内返回的原有语义。
- 反例：不能把“所有关闭前调用 loginStatus(true)”当规范，旧方法已演进，且同步 API 返回不等于原生处理完成。

## RN4：bridge 完成信号必须与调用者等待语义一致

- 证据：`95225f5c90ce4e13e7bb82fd2e71c2c8fd91f454`，zhenqiang `<zhenqiang@baijia.com>`。
- 路径：`RNTurboModules/AppInfo/js/NativeAppInfo.ts`，`Spec.submitSubjectInfo` 由 void 改为 `Promise<boolean>`。
- 路径：`src/service/appcontext/AppInfoHelper.ts`，`submitSubjectInfo` 导出异步接口并传播 resolve/reject。
- 同 diff Android module 改为接收 Promise，但方法体仍为空；该提交本身不能证明平台实现完成。
- 调用上下文：`91b72c85db1452d0f07d52f9b06f743e2d221355`，zhenqiang `<zhenqiang@baijia.com>`。
- 路径：`src/biz_modules/module_subject/main/src/SubjectPage.tsx`，`handleBottomButtonClick` 提交后 `.then` 返回。
- 条件：页面关闭依赖原生落地完成，接口需要可等待结果；声明、helper、消费者与各原生端一起核查。
- 反例：旧 helper 用 `new Promise` 包裹 `AppInfo?.submitSubjectInfo`；模块缺失时没有 resolve/reject，会悬挂。
- HEAD 仍保留该包装；只能借鉴完成信号契约，不能照抄可选调用包装或把空 Android stub 当正确实现。

## RN5：网络编码例外留在具体 service 调用

- 证据：`d91373622910cd0bba3853e544c1acbc815d81d3`，zhenqiang `<zhenqiang@baijia.com>`。
- 路径：`src/biz_modules/module_mine/main/src/pages/mine/service/MineService.ts`，方法 `requestMessageList`。
- diff 为这一条 `post` 增加末参 false；同 revision `src/service/network/NetworkHelper.ts:post` 默认是 `isJsonType ?? true`。
- 同 revision `MineHeaderBar.tsx:getMsgCount` 只消费 totals；显示组件不负责决定原生请求编码。
- 条件：具体后端接口有与默认不同的编码合同；在 service 显式选项，保留公共网络层默认行为。
- 反例：false 不是“所有消息/所有 POST”的规则；旧 async 方法仍使用 callbacks，不能据此假设返回 Promise 代表请求完成。

## RN6：长生命周期回调区分瞬时状态与真正后台

- 证据：`260075f8d2b0a8d20527fb641f22f76c0313508b`，tangaoyang `<tangaoyang@baijia.com>`。
- 路径：`src/biz_modules/module_study/course_list/main/src/components/study_material/StudyMaterialPage.tsx`。
- 方法：AppState change effect；diff 将暂停条件从 background 或 inactive 改为仅 background。
- 同 revision 用 `backgroundPlayRef` 读最新设置、`wasPlayingBeforeBackground` 记录恢复依据，effect 返回 subscription.remove。
- 同文件 `loadAudio` 以 currentTaskId 过滤过期异步音频，资源卸载与 requestAnimationFrame 都有清理分支。
- 条件：外部事件、播放任务或高频回调跨渲染存活；区分 UI state 与回调读用的 ref，明确清理点。
- 边界：inactive 语义取决于功能；安全、隐私功能可能必须立即遮挡，不能套用播放器策略。
- 反例：该 effect 仍依赖 audio.current、backgroundPlay、isPlaying；此 diff 不能证明订阅只创建一次或整个播放器无竞态。

## RN7：动画完成后落地数据，跨线程回调只带必要信息

- 证据：`06fd0ae92fce220c2eb4f81040b0175f4234339e`，tangaoyang `<tangaoyang@baijia.com>`。
- 路径：`src/biz_modules/module_study/home_page/main/src/components/modules/TodayRecommendV2ModuleView.tsx`。
- 方法：`applyPendingModuleInfo` 与 moduleInfo effect；新增 ref 保存待应用数据，动画完成后 `runOnJS` 无参读取 ref。
- 同 revision 保留实验开关旧分支；新增时先背景高度动画再更新数据，移除时先更新数据再收缩高度。
- 条件：展示内容与尺寸动画必须按顺序更新，且大型业务对象无需跨 UI/JS 线程传递。
- 复用：把状态更新放到 JS 方法，worklet 保持轻量；结合当前覆盖率规则放置忽略注释。
- 边界：此样本按实验控制，是局部兼容修复；旧分支传对象、收缩 setTimeout 未清理不能升级为通用规范。

## RN8：接口 DTO 与展示口径分离，复用现有列表与点击工具

- 证据：`98370a278a78376dee4895ddfbbfddde159f77a6`，zhenqiang `<zhenqiang@baijia.com>`。
- 提交含 AI 协作署名；非机械生成 diff，但不足以独立证明该作者长期习惯。
- 路径：`src/biz_modules/module_ai_search/main/src/api/model/CorrectRecordViewModel.ts`，方法 `mapDtoToViewModel`。
- DTO 保留服务字段；转换集中处理未知状态、无效题数、空 taskId、缺失跳转与时间解析失败。
- 配套路径：`src/biz_modules/module_ai_search/main/src/pages/AiHomeworkCorrectRecordPage.tsx`，`fetchPage`/`buildListItems`。
- 页面复用 RefreshFlashList、LoadErrorView、独立 usePressGuard；列表用业务 id，追加复用未变化项引用。
- 条件：同一服务数据驱动列表/卡片且展示规则复杂；集中归一化，让展示消费明确模型。
- 边界：unknown→Failed、完成态才展示题数是此业务合同；不能跨业务照搬，也不能把注释中的性能原因当设备实测证据。
- 反例：页面有较多平台专用分页协调与长注释；新简单页面不需要复制全部 ref/timer 或预留未使用功能。

## 使用检查

- 先匹配任务与模式条件，再核对目标模块现状；接口字段、平台能力与业务事件优先于作者外观风格。
- 本次深读八类非 merge 差异及必要的前后修正；覆盖地址、账户、品类、我的页、课程音频、今日推荐与 AI 搜索。
- 历史缺陷、旧格式、空 stub 与 AI 协作代码均已限定；未执行运行时测试，不宣称跨端行为通过验证。
