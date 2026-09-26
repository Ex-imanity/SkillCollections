# mweb: 多产品 C 端 H5

## 使用范围与取样边界

- 本资料是样本归纳；修改时先读取目标产品、目录的当前配置和同类实现。
- 取样日期：2026-09-26；分支 `master`；HEAD `640a6128630e418f0292eaf3232d71e58f59556b`。
- 当时本地分支落后已记录的 `origin/master` 1 个提交，研究未更新 refs；不是远端最新状态证明。
- 作者统计来自本地所有可达 refs 的 `git log --all --no-merges`，不代表远端完整历史。
- 已深读 13 个实质业务 diff，重点覆盖选课中心、共享评论/NPS、订单卡片和支付页面。
- 没有运行或构建七个产品；不能据此声称产品行为一致或样本均经过运行验证。
- 缺少仓库或历史对象时，可使用下述条件摘要；恢复访问后应核对当前代码，不能声称已读取证据。
- 路径均相对于 `mweb` 仓库；仅新增或修改的行可以归因对应作者，整文件不是个人风格证明。

## 显式规范与配置

- `README.md` 明确：`base` 存通用组件、API、constants、mixins、plugins、util；`business` 存业务公共组件与复用页面；`packages` 存各产品内容。
- README 明确各产品独立部署上线；共享代码变更需核对消费它的产品入口。
- 七个产品 `gaotu`、`gaotujingpin`、`gaotusuyang`、`gaotuzhixue`、`gongkao`、`lexue`、`tutu` 有 tracked `.editorconfig`、`.eslintrc.js`、`package.json`。
- 产品 `.editorconfig` 规定 4 spaces、LF、UTF-8、末尾换行和去尾空格，Markdown 例外保留尾空格。配置优先于历史文件偶见的 tabs。
- 根目录及产品 ESLint 使用 `plugin:mew/vue`；样本配置中 `no-magic-numbers` 为 warning，`max-lines`、`no-console` 等关闭。
- 关闭检查不等于推荐长文件、诊断日志或硬编码；注释掉的规则也不能作为生效要求。
- 未发现 tracked `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、`.cursor/rules`、Prettier 或 Stylelint 配置；忽略文件扫描排除 `node_modules` 后也没有这些规范。
- README 存在陈旧、混杂内容和依赖安装说明冲突；本资料只采用明确的目录职责，实际工具流程以目标产品配置为准。
- `packages/gaotu/package.json` 的 `lint` 路径和 `lintfix` 全目录自动修改范围需要先检查，不能直接运行全仓格式化。
- 框架事实：该包有 Nuxt 2、Vuex 3、Vant 2、Less；所读样本主要是 JS Vue Options API。不得因此强制改写现有 TS 或其他模块。

## 作者覆盖

| 匹配邮箱 | 非 merge 数量 | 样本时间范围 |
| --- | ---: | --- |
| `wangdi08@baijia.com` | 781 | 2022-07-07 至 2026-09-14 |
| `lichen03@baijia.com` | 171 | 2022-07-10 至 2026-06-08 |
| `liyunbo02@gaotu.cn` | 6 | 2025-06-19 至 2025-09-16 |
| `dengyong@baijia.com` | 21 | 2024-03-04 至 2026-05-09 |

`wangdi08` 对应王迪/wangdi/wangdi08，`lichen03` 对应 lichen03/李琛03，`liyunbo02` 对应李云波。其他域名身份出现在部分 merge 记录中，未混计上述数量。样本不均衡，尤其李云波业务证据集中订单卡片，不能称为四人共同规范。

## 条件规律与证据

### M1. 跨产品同一业务能力优先检查共享层，迁移时同步入口

- 条件：多个产品已有同类业务副本且差异可以通过现有品牌/产品配置表达。
- Commit：`1e5e98eee518ff07d9a379278bc0e19f926356f3`；作者 `lichen03 <lichen03@baijia.com>`；2026-04-29。
- 路径：`business/pages/comment/list/_id.vue`、`business/pages/comment/my/index.vue`、`business/components/comment/CommentCourseListItem.vue`、`business/components/comment/CommentLessonListItem.vue`、`packages/gaotu/router.js` 及其他产品 router。
- 方法/组件：`getCourseCom`、`CommentCourseListItem`、`CommentLessonListItem`。
- 事实：迁移评论页面/组件到 `business`，删除多个产品副本，router lazy import 改为 `@business/pages/comment/...`；品牌文案取产品 `BRAND_NAME`。
- 上下文：对应 revision 的 `base/api/index.js` 和 `base/mixins/comment.js` 已有路径与行为复用，页面继续使用 `$api`、`$axios`、mixins。
- 限制：成功页仍保留产品入口，公共 dialog 样式仍进入产品 main.less；不是所有页面都搬共享层。共享变更必须核对 alias、路由、品牌和消费产品差异。

### M2. 可选字段的重复展示逻辑放在已有 computed 边界

- 条件：模板重复处理同一个可选展示字段，且计算不应产生副作用。
- Commit：`16cc5021d6696c962b49a3f8b62c4b5da080ab06`；作者 `lichen03 <lichen03@baijia.com>`；2026-06-08。
- 路径/方法：`business/components/comment/CommentCourseListItem.vue` / `teachers`。
- 事实：两处 `teacherList.join('、')` 改为 computed `teachers`，缺少列表返回空字符串；部分模板增加 `v-if="teachers"`。
- 限制：只处理字段缺失，不是任意非数组类型校验；不能把接口失败一律静默转为空态。
- 对照：`32f573cbb4b5257aaa601cf958847ac875868aec`，`李云波 <liyunbo02@gaotu.cn>`，`business/pages/orders/detail/components/ReachCard.vue` 的 `teacherText`、`batchList`、`hasClassInfo` 也提取展示计算。
- 对照限制：同一提交新增空真实数据时使用 `mockData` 的行为和内联状态字符串；这些不作为生产规范推荐。

### M3. 沿用 API 注册与请求封装，字段位置按接口协议确认

- 条件：目标模块已有 `$api`、`$axios` 和公参/编码插件。
- Commit：`8a1036622cf5321a36939913b240c5fb4bee6643`；作者 `lichen03 <lichen03@baijia.com>`；2026-05-13。
- 路径/方法：`business/pages/comment/list/_id.vue` / `getCourseCom`；`business/pages/comment/my/index.vue` / `getCommentList`。
- 事实：`os` 从 headers 移到 POST params，继续调用 `$axios.$post(this.$api.comment..., params)`。
- 上下文：对应 revision 的 `base/api/index.js` 集中定义评论路径；`base/plugins/axios.js` 处理公参、身份、版本、form/JSON 编码及错误上报。
- 限制：只是评论接口修正，其他服务可能要求 header 或公参；不能推断所有 `os` 都在 body，也不能用 raw fetch 绕过现有请求功能。

### M4. 多入口同一业务取值规则集中到局部方法，逐字段 fallback

- 条件：同一卡片的多个跳转入口共享归因取值规则。
- Commits：`5f104f5f4c7dbcce2d1a8dfba50227517483d490`、`2dba2f19137eb1eb129e142b040e45f0411d89aa`；作者均为 `wangdi <wangdi08@baijia.com>`；2026-09-14。
- 路径：`packages/gaotu/components/chunsun/selectCourseCenter/ClazzCard/index.vue`。
- 方法：`getOrderSource`、`getMiniProgramCourseUrl`、`jumpToWebCourseDetail`。
- 事实：小程序/H5 固定 source 改为局部取值方法；后续命名 `DEFAULT_SOURCE`，分别为 `actionSource.detail` 和 `actionSource.signup` 提供兜底。
- 限制：采用后续完整修正，不能以先前空 source 返回作为范例。规则仅适用于该卡片，不能扩大成全局 source util 或重命名协议字段。

### M5. 环境分支与生命周期按页面现有约定维护

- 条件：同一页面覆盖普通 H5、App、小程序、SSR，并涉及加载或缓存。
- Commit：`dd235b6035f14058ef5329bf76cdedf268d2ce43`；作者 `wangdi <wangdi08@baijia.com>`；2026-08-07。
- 路径/方法：`packages/gaotu/layouts/default.vue` / `keepAlivePages`；`packages/gaotu/pages/chunsun/selectCourseCenter/index.vue` / `mounted`、`activated`、`deactivated`、`fetchPageData`。
- 事实：只有普通 H5 增加选课中心 keep-alive；客户端 mounted 按 SSR 数据开启首屏 loading，成功和 catch 关闭；缓存保存恢复内部滚动位置，App 继续调用 bridge 更新缓存。
- 上下文：该 revision 已有 `asyncData` SSR 取数、细分 loading、Vuex 状态及避免回写触发 watch 的 `isSyncingPageDataState`。
- 限制：不是所有页面都需要 keep-alive；window/document 必须守住客户端边界。旧 TODO、调试 `window.test` 等不属于推荐惯例。

### M6. 改动作时一起检查路由、bridge、产品协议和埋点

- 条件：业务点击在端内/端外行为不同，或携带来源及物流/课程标识。
- Commits：`72d3e227409cddf7a559d82c5c2858ef5b4f408b`、`5ec620f1a18c8c9463fee2f590dac24510170007`；作者均为 `李云波 <liyunbo02@gaotu.cn>`；2025-06-19。
- 路径/方法：`business/pages/orders/detail/components/ReachCard.vue` / `handleViewLogistics`、`handleViewSchedule`。
- 事实：物流取 `delivery` prop 并补充 `ORDER_DETAIL_ID` 埋点参数，按字段决定详情/列表；课程中心按 `isGaotuApp` 选择产品协议或 `$router.push('/study')`，protocol 取 store 配置。
- 限制：queryUrl 存在但 invoiceNumber 为空时样本没有动作，不能当完整实现照抄。历史有多套 bridge wrapper，应先选目标模块现有封装，不能强制统一库。

### M7. 恢复共享状态时检查 watcher 依赖和提交顺序

- 条件：缓存/接口数据恢复触发派生状态和其他 Vuex mutation。
- Commits：`181d01dd8607c63125061f177a7567ba59c5c258`、`3402dc5925807ed5c81e9abd03cb532393288af3`；作者均为 `dengyong <dengyong@baijia.com>`；2025-02-24、2025-03-11。
- 路径/方法：`business/pages/npsAssess/index.vue` / 缓存恢复；`business/components/NPS/NPSProgress.vue` / `watch.npsChooseAnswer`。
- 事实：恢复字段增加默认值，watch 对缺失 val 提前返回；后续把 `SET_NPS_NECESSARYNUM` 移到恢复答案之前。
- 上下文：进度 watch 依赖 questionNum、答案数、getCoin，修改 schedule 后又提交币数量，因此顺序会影响结果。
- 限制：旧 watch 仍直接读取 oldVal，不是完整容错范例；不要求所有 watcher 添加 deep/immediate，临时诊断日志/埋点也不是长期约定。

### M8. 使用业务语义 CSS 名称，避免无关格式化扩大 diff

- 条件：新增样式来自设计导出命名，或窄改动触及历史大文件。
- Commits：`72af30af119d634f47676b8e500742e00b8235e9`、`39dbcd64935fd5fb6c395318ffc90dad5323638b`；作者均为 `dengyong <dengyong@baijia.com>`；2024-04-10、2024-04-15。
- 路径/组件：`packages/gaotu/pages/pay/succeed/_id.vue`、`packages/tutu/pages/pay/succeed/_id.vue` / 支付成功展示。
- 事实：`GROUP-0`、`FRAME-1` 等改为 `pay-*`，同步模板和 Less；后续提交明确恢复自动格式化产生的改动。
- 限制：`pay-grounp` 拼写问题不能复制；不据此强制 BEM 或单一大小写风格。当前显式配置优先，保持局部 diff 不能成为忽略配置的理由。

## 使用前核对

先确认目标产品及部署边界，再检查共享层消费方、当前 formatter/linter、接口编码、公参、路由/品牌/bridge 与埋点契约。JS/TS、缩进、引号、类名、生命周期应按目标模块当前约定确定；不要用这些局部样本给七产品强行统一风格。
