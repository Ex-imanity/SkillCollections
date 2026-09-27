# community 前端代码惯例

## 范围与证据边界

- 研究日期：2026-09-26；C 端社区 H5，当前代码为 Nuxt 2、Vue 2、JavaScript SFC、Vuex、Less。
- 研究 checkout：`master`，工作区干净；HEAD：`94b8e29d0441a6715ae9c51b31717eb2e6b8f183`。
- 未 fetch；以下历史来自本地 Git，不能证明远端完整历史或生产部署版本。
- 样本主要覆盖 2025-01 至 2026-06，深读实质业务 diff 和相同 revision 的请求、组件、工具上下文。
- 下列条件规律是样本归纳；只有“显式配置”部分可以作为该快照的直接配置证据。
- 缺少本仓库或历史对象时，本文件摘要仍可使用；实施时以目标 checkout 的规范及同类实现重新核对。
- 不把现有整个文件归为某位作者；作者证据只覆盖列出的提交变化。

### 作者覆盖

- HEAD 可达且排除 merge：`dengyong <dengyong@baijia.com>` 548 次、`lichen03 <lichen03@baijia.com>` 23 次。
- `wangdi08@baijia.com` 同范围 140 次，author name 分为 `wangdi` 24、`王迪` 100、`dengzhenna` 16。
- 本文该邮箱深读样本 author 为 `wangdi`；相同邮箱的不同名字不能独立证明自然人身份。
- 全本地 refs 的 author 搜索未找到 `liyunbo02` 或 `liyunbo`；不宣称本文覆盖该作者。
- 不把这些规律表述为四人共同规范，也不据提交次数判断代码质量。

## 显式配置与文档冲突

- tracked 文件及相关 untracked/ignored 文件名扫描未找到 `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、`.cursor/rules` 或 stylelint 配置。
- `.editorconfig`：4 空格、LF、UTF-8、末尾换行、清理行尾空白；Markdown 不清理行尾空白。
- `.prettierrc.js`：4 空格、单引号、分号、80 printWidth、trailingComma all、arrowParens always、LF。
- `.eslintrc.js` 继承 `plugin:mew/vue`，`no-magic-numbers` 为 warning；若干规则关闭不等于鼓励对应弱实践。
- `README.md` 要求新增依赖保持 `package-lock.json` 的 lockfileVersion 1；执行时仍核对当前包管理配置。
- `README.md` 的旧 rem 基数说明与当前 `nuxt.config.js` 的 `rootValue: 32` 不一致；样式变更读实际转换配置。
- `pages/README.md` 含旧页面列表和默认自动路由说明；当前有自定义 `router.js`，新增路由核对实际入口。
- `项目介绍.md` 的扫描总结与建议只能帮助定位，不能把“建议新建 API 适配层”升级为强制惯例。
- `docs/2026-05-迭代-前端技术反讲文档.md` 大量内容属于 school-reporte 的 React/Next 项目，不作为 community 实现规范。
- `components/veVideoPlayer/README.md` 可帮助理解业务 props，格式示例与配置冲突时以当前 formatter 为准。
- `package.json` 的 `lint` 指向 `src test/unit test/e2e/specs`，与当前 `pages/components/util` 结构不符。
- 检查前确认命令实际覆盖目标文件；不要盲跑全仓 `lintfix`，也不要仅由脚本名宣称代码已 lint。

## 条件规律

### C1：客户端接口沿用集中 URL 与请求实例，明确编码

- 适用：现有页面、组件的业务请求；样本归纳。
- 作者：`lichen03 <lichen03@baijia.com>`。
- 提交：`2d77f9c89c7a607365aa0ccf95c234e65e7cd033`。
- 路径：`api/index.js`、`components/teacher/blogPublish/topicPopup.vue`；方法：`fetchRecommendTopics`。
- 事实：修正 `teacher.topicRecommend` URL，mock 改为 `$axios.$post($api.teacher.topicRecommend, payload, options)`。
- 事实：显式 JSON header，成功判断为 `res.code === 0 && res.data`；字段为 title/content/images。
- 上下文：同 revision 的 `plugins/axios.js` 注入 sid/did/gid/p_client/version，默认 qs 编码，仅显式 JSON 分支保留 JSON。
- 使用：新增或调整接口先读 interceptor，复用当前客户端及字段契约；不要绕过公参另起客户端。
- 限制：SSR 有 `api/ssr/*` 与 `app.axiosServer` 独立路径，不强制全部接口进入同一目录。
- 反例：该样本同步 try/catch 包 Promise then，不能捕获异步拒绝；保留 mock 注释也不是错误处理范例。

### C2：发布链路沿用 props 输入与 emit 确认边界

- 适用：已有发布页和选择弹窗增强；样本归纳。
- 作者：`lichen03 <lichen03@baijia.com>`。
- 提交：`41ee29485208a84de4d2df9363517e809535aa36`。
- 路径：`pages/blog/publish/index.vue`、`components/teacher/blogPublish/addTopic.vue`、`components/teacher/blogPublish/topicPopup.vue`。
- 方法/组件：`publishImages` computed、`AddTopic`、`TopicPopup`、`onComfirm`。
- 事实：标题、正文、图片从页面经现有 addTopic 传入弹窗；String 默认空串、Array 用默认值工厂。
- 事实：选中结果通过 `setTopicList` emit 返回，草稿和确认状态放组件 data，标题由 computed 派生。
- 使用：先扩展现有组件边界，确认状态的拥有者，再决定是否需要跨页 store。
- 限制：本提交请求仍为 mock，真实接口见 C1；不能将 mock 当可交付数据来源。
- 反例：computed 读取 `$refs.getPictures()` 的响应性需另行验证；不推广该依赖，也不禁止跨页状态使用 Vuex。

### C3：默认推荐受已有选择和确认状态约束

- 适用：默认推荐、圈子或话题选择；样本归纳。
- 作者：`lichen03 <lichen03@baijia.com>`。
- 提交：`616c7a9f18b2a0c4315f9bae683bba52bcc86d06`。
- 路径：`components/teacher/blogPublish/topicPopup.vue`；方法：`watch.showTopicPopup`。
- 事实：移除调试日志，用 `getInnerText(publishContent).trim()` 判断内容；未确认且未选时，任一输入存在才请求。
- 关联提交：`23cccf187ea251a5a09bc2c94354121772229d6c`，同作者，`components/teacher/blogPublish/addCircle.vue`。
- 关联事实：圈子列表返回后仅在没有 selectedCircle 时设置默认圈子及 confirmCircle。
- 使用：明确默认态、编辑态、确认态；新增默认行为不能无条件覆盖用户选择。
- 限制：触发条件不能证明响应返回期间的用户编辑安全；异步结果是否仍有效需要单独检查。
- 反例：历史 `DefaultCirtle` 拼写不是推荐命名，仅在保持兼容时保留已有标识。

### C4：跳转调整同时保持 source、埋点和端差异

- 适用：课程卡与现有 H5 容器跳转；样本归纳。
- 作者：`wangdi <wangdi08@baijia.com>`。
- 提交：`a092d4ed69719d3457599e273c4ad160fa8d95c5`。
- 路径：`components/teacher/CourseCard.vue`；方法：`onGotoDetail`。
- 事实：命名常量 `LIANBAO_COURSE_TYPE = 23`、归一 courseType；联报走 learn，其余走 product。
- 事实：保留 signUpPathTag，先上报点击；端内沿用 bridge openWindow，端外用 location。
- 上下文：source 由 SIGN_UP_PATH、COURSE_TYPE_ID_COLLECT、p_client、signUpOrigin 和端差异共同决定。
- 使用：追踪业务类型、路由、source 与埋点完整链路，沿用目标模块 wrapper。
- 限制：仓库存在多种 bridge；此提交迁移特定课程协议，不能要求所有 native 跳转使用同一 API。

### C5：共同业务协议放小型领域 util，调用点保留自身参数

- 适用：多入口分享参数复用；样本归纳。
- 作者：`dengyong <dengyong@baijia.com>`。
- 提交：`ed817479f5ccde1f6eb8d603fcdb317ebbbc9288`。
- 路径：`util/attribution.js`、`components/teacher/blog/BlogInfo.vue`、`components/teacher/blog/DetailHeader.vue`。
- 其他调用：`components/teacher/circle/CircleBlog.vue`、`pages/blog/detailNew/_id.vue` 的分享处理。
- 方法：`addMomentDetailNaturalShareParams`、`getShareInfo`；事实：公共参数对象经已有 addUrlParams 合并 utm_content。
- 事实：调用点额外补 shareCode/source/p_client；SDK 在 `plugins/attribution.js` 动态载入，配置为 client 模式。
- 使用：重复且稳定的协议归入领域 util，浏览器 SDK 核对 client-only 注册及失败处理。
- 限制：后续环境修正见 `39dd25d38b6dad2d9cb19874e2e9895093158d2b`、`be852b4d3098e694c334baa4267f8203a6239f95`。
- 反例：初始固定 lc 和 API 地址不是长期模板；不为单次使用创建通用抽象。

### C6：文本转换复用 helper，同时保留链接许可和端映射

- 适用：用户内容、Markdown 链接展示；样本归纳，非安全审计结论。
- 作者：`dengyong <dengyong@baijia.com>`。
- 提交：`4527cdf1fffb4e2ed458ffd8be0151b92ba05346`。
- 路径：`util/common.js`、`components/teacher/blog/Blog.vue`、`components/teacher/blog/Detail.vue`、`components/teacher/blog/CommentCard.vue`。
- 方法：`formatSafeMarkdownLinks`、`escapeHtml`、`textToSafeHtml`、组件 content/parseMarkdownLinks。
- 事实：集中重复 regex/escape 实现，调用参数表达链接开关、白名单、业务协议与端内 scheme 差异。
- 使用：复用当前 helper，保留 checkContentLinkAvailable；纯工具避免隐式浏览器 DOM 依赖。
- 限制：regex 不是成熟 Markdown parser；no-v-html 规则关闭不表示原始用户 HTML 可直接渲染。
- 后续 `7421aa0f3200232613fae7cbecc4d67d47ea95f5` 调整保留标签，新增需求必须重读当前业务契约。

### C7：重复点击控制复用现有节流，并保留业务校验

- 适用：活动跳转、返回、分享等动作；样本归纳。
- 作者：`wangdi <wangdi08@baijia.com>`。
- 提交：`8e4156529fbe9353f90c03fe3bf3a11f3ab61287`。
- 路径：`pages/blog/winterActivity/Aiyan.vue`、`pages/blog/winterActivity/components/NavBar.vue` 等活动组件。
- 方法：handleInteract/handleBack/handleShare；事实：lodash throttle、普通 function 保留 this、leading true/trailing false。
- 上下文：沿用 ActivityStatusEnum 校验和 commonMixins.handleJumpUrl；后者在 beforeDestroy 清理 listener/timer。
- 使用：复用当前能力、状态常量和生命周期清理；根据动作选择节流语义。
- 限制：300ms/1000ms 是场景值；方法级 throttle 多实例作用域需要评估，不要求所有方法节流。
- 反例：本提交还调整任务链路，不能把整体 diff 当纯风格重构复制。

## 复查方式

在对应仓库使用 `git show <commit> -- <相对路径>` 查看变化，`git show <commit>:<相对路径>` 查看同 revision 上下文。
这些源代码引用是可选核对证据，不是 skill 运行时文件依赖；不要要求团队成员拥有固定本机目录。
