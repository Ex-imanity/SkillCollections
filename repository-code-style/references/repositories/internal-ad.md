# internal-ad：B 端前端条件范例

## 取样范围

- 仓库源码路径均相对于 `internal-ad` 根目录；可用 `git show <commit> -- <file>` 复查。
- 用户称 `ad-internal`；本次可验证对象的 package 名、README 标题及规范文件均为
  `internal-ad`。尚无证据确认两个名称对应同一个远端仓库，不自动套用到其他仓库。
- 2026-09-26 checkout：`feature-feedback-category-20260922`，HEAD
  `8d6cdb502fa20553de703ae422db18062a22ca4a`；未 fetch、安装依赖或运行业务构建。
- 当时已有 FeedbackCategory 相关路由、权限、页面、mock、类型、service 和测试变更。
  研究仅阅读提交差异与对应 revision，未把这些未提交代码作为指定作者范例。
- 深读 8 个非合并业务差异，覆盖四人。`git log --all` 匹配记录含 merge，分布为：
  liyunbo02 165、lichen03 156、dengyong 81、wangdi08 145，不代表贡献质量或样本权重。
- 作者身份：李云波 `liyunbo02@gaotu.cn`；lichen03/李琛03 `lichen03@baijia.com`
  及早期 `lichen03@baijiahulian.com`；dengyong `dengyong@baijia.com`；
  wangdi/王迪/wangdi08 `wangdi08@baijia.com`。规则只归因实际差异，不归因整份文件。

以下为**样本归纳**，不是个人风格的强制复制。没有历史仓库也可使用条件摘要；
实施前仍需阅读目标模块当前规范与同类代码。

## IA0. 显式约定与配置事实

- 已由 `git ls-files` 核对跟踪的 `AGENTS.md`、`CLAUDE.md`、6 个 `.cursor/rules/*.mdc`、
  README、package、tsconfig、ESLint/Stylelint 配置及 ignore 文件；关键规范文件没有
  `git check-ignore` 命中。跟踪状态与用户当前指令分开判断。
- AGENTS/CLAUDE 明确：函数组件、业务域 services、复用 components/hooks/models/utils、
  Less、集中路由、严格 TS、IE11 目标及 `/internal-ad-panel/` 部署假设。
  新增代码遵循目标 checkout 显式要求，不将其他仓库默认风格移植过来。
- package/config 事实：React 16、Umi 3、Ant Design 4、ahooks 2；tsconfig strict 为 true；
  `config/config.ts` 配置 IE11 target、publicPath 和 runtimeHistory。
- AGENTS/CLAUDE 指定修改后类型检查，涉及样式/import 时 lint；实际命令查 package scripts。
  本研究没有验证命令可运行。`.eslintrc.js` 的 extends 含 `pligin: react-hooks`；
  跟踪的格式文件名为 `. prettierrc`（点后有空格），不能当作已生效的标准 `.prettierrc`。
- README 残留 Vue CLI/serve 指令，与当前 Umi package 不一致；Cursor 开发规范的 umi request
  示例也与实际业务主请求不同。请求实现应先核对 `src/utils/request.ts`，不能照抄示例。
- `src/utils/request.ts` 是共享 axios client，配置凭证、拦截器、imis adaptor 和业务响应处理，
  返回业务数据而非默认 AxiosResponse；`src/services/base.ts` 当前为空，不能推荐为入口。
- 规范倾向类型放 interfaces/types；历史存在具名局部接口及 imis 同目录 types/api。
  新增遵循显式约定，局部修改不为统一形式迁移所有历史目录。框架版本只作取样事实。

## IA1. 查询与导出复用参数转换

- Commit：`04515906fffb2da6dc19aa3d89cec7ac54ad1cac`，wangdi `wangdi08@baijia.com`。
- 文件：`src/pages/SheildManage/index.tsx:DynamicList`；`src/services/sheild.tsx:exportShieldHitList`。
- 事实：抽出 `formatQueryParams`，查询与导出共同转换课程标签/CMS 分类的级联叶节点；
  导出 service 从无参改为传 params 的 Blob 请求，继续复用共享 request。
- 事实：`handleExport` 检查 JSON Blob 业务失败，生成时间戳文件名，保留下载兼容分支，
  释放 Object URL；业务失败不能仅靠 HTTP 成功判断。
- 采用：导出要求匹配当前查询时，共用同一参数转换，核对列表和导出的 API 契约。
- 限定：不复制历史 `as any`、未类型化 params、重复 loading 清理；JSON Blob 的失败协议
  按接口核对，不能假定每个下载 endpoint 都相同。

## IA2. 表单输入、请求参数与缓存形状分开表达

- Commit：`04515906fffb2da6dc19aa3d89cec7ac54ad1cac`，wangdi `wangdi08@baijia.com`。
- 文件：`src/interfaces/sheild.ts`；`src/pages/SheildManage/home/HitQueryPage.tsx:HitQueryPage`；
  `src/services/sheild.tsx:getShieldHitList`。
- 事实：新增 `HitQueryFormValues` 与 `HitQueryCache`，userId 输入可字符串/数字；
  `handleSearch` 请求前转 Number，接口参数用 `HitFilterParams`，同步修正 endpoint。
- 事实：查询成功缓存表单值与数据；`handleReset` 同时重置表单、列表和 sessionStorage。
- 采用：UI 状态与接口类型不同，在调用边界显式转换；重置时处理关联状态。
- 限定：不把整表缓存推广到所有页面；缓存 schema、有效期和存储失败处理按需求决定。

## IA3. 筛选、关联选项与分页共同恢复和重置

- Commit：`843da75379bbea389af5c4373ed93ef84f618738`，lichen03 `lichen03@baijia.com`。
- 文件：`src/pages/DynamicList/SearchFilter.tsx:SearchFilter`；
  `src/pages/DynamicList/index.tsx:DynamicList`；`src/utils/dynamicListCache.ts`。
- 事实：将 filter 内缓存逻辑提到工具，统一 key/TTL、过期与解析失败处理；清空操作同时
  清空关联选中值并重置 pager；分页首次 state 从缓存恢复，后续通过 upsert 合并保存。
- 事实：请求参数尊重调用方显式 pager；分页变化与请求结果更新缓存。
- 采用：筛选与分页需跨页面保留时，保证两者读写一致，显式区分重置、翻页与恢复。
- 限定：并非所有列表都需持久缓存；不复制任意 any 字典、日志或直接删除参数字段；
  普通筛选是否重置页码要依据当前需求，不从此样本推导统一行为。

## IA4. 开关与历史配置分开，回显保护 0/false

- Commit：`cea987dc5a9fa22ce76acf3dad648a10c7ff2185`，dengyong `dengyong@baijia.com`。
- 文件：`src/pages/ResetTeenPwd/index.tsx:ResetTeenPwd`。
- 事实：删除开关 onChange 重置默认配置逻辑；条件卸载改为隐藏，保留字段值。
- 对应 revision：`openAiSettingModal` 从详情回填并用 `??` 保留 0/false；
  `handleUpdateTeenagerConfig` 校验后确认保存，isOpen 控制生效、detail 保留历史配置；
  成功后清理表单/关闭并刷新，finally 清理保存 loading。这是上下文，不全归因本次差异。
- 采用：业务要求开关关闭后仍保留配置时，分开生效状态与配置内容，检查回显和提交转换。
- 限定：关闭即清空的字段不能机械保留；不推广为禁止条件渲染或要求所有保存均二次确认。

## IA5. 同一业务上传规则由多个入口复用

- Commit：`d9f5fd1372872acc5824b5d4a7f6f5ab023b75c5`，dengyong `dengyong@baijia.com`。
- 文件：`src/utils/dynamicImageUpload.ts:validateDynamicImage`；
  `src/components/UploadImages/utils.tsx:beforeImageUpload`；
  `src/components/UploadVideo/utils.tsx:beforeVideoPosterUpload`。
- 事实：抽出 MIME、短边、比例常量及读尺寸、压缩、创建文件函数，图片和视频封面共用；
  返回契约从 boolean 扩为 `boolean | File`，可返回压缩文件；finally 释放 Object URL。
- 采用：多个入口执行同一业务规则时，提取有业务名称的小工具，并检查调用方接收新文件。
- 限定：比例和尺寸仅属于动态封面，不推广至其他上传；兼容代码对应此项目 IE11 目标；
  读图失败反馈仍须核对，不能认为抽出工具就已覆盖所有异常。

## IA6. 同步校准响应类型与分页消费层级

- Commit：`620d378fa9023ef29f3d1b5c2c72f7d377212b71`，李云波 `liyunbo02@gaotu.cn`。
- 文件：`src/pages/imis/gaotu-c-nickname-history/index.tsx:GaotuCNicknameHistory`、同目录 types；
  `src/pages/imis/live-audit-images/index.tsx:LiveAuditImages`、同目录 types；
  `src/pages/imis/user-avatar-history/index.tsx:UserAvatarHistory`、同目录 types。
- 事实：消费从 data.pager 改为响应根 pager，类型同步移动；头像历史删除 data.total 回退。
- 采用：接口层级变化同时修改类型与消费，核对分页 current/pageNum/pageSize/total 映射。
- 限定：这是具体接口纠错，不能假定所有 pager 都在根部；不要添加猜测层级的多重兜底。
  这些页面含生成来源，只以提交实际修正为证据，不把生成整文件归因作者。

## IA7. 已有低代码模块沿 adaptor 和配置扩展

- Commit：`3955fea6c53570190b798c246a7247537bbe1aa0`，lichen03 `lichen03@baijia.com`。
- 文件：`src/pages/OfficialWebsiteManage/TeacherList.tsx:TeacherDisplay/setConfig`。
- 事实：沿 Renderer/BusinessSwitch/model 配置增加 download 与隐藏 business 字段；
  requestAdaptor 将 renderer pager 转为 pageNum/pageSize，移除 undefined 参数。
- 采用：已有 imis 页面先查配置、adaptor、请求与业务线切换约定，再增加功能。
- 限定：不默认改写手写 CRUD；不能由本次删除权限 imports 推导普遍删除权限检查，
  也不把配置字符串插值当成通用编码规范。

## IA8. 异步回显检查实际读取的依赖和请求顺序

- Commit：`3bba19260ee6c251abbf64b942fa9d45b5940d0b`，wangdi `wangdi08@baijia.com`。
- 文件：`src/pages/SheildManage/ManageForm/index.tsx:App`。
- 事实：回显 effect 补入实际读取的 rockExperimentNameList 依赖，修正实验请求慢时不重跑；
  保存格式化对可空 groupName 显式回退数组。
- 采用：并行请求后回显/解除 loading 的代码，检查依赖、请求不同顺序、失败与合法空结果。
- 限定：该 diff 未解决空实验列表的 readiness 条件，不推广“数组非空才等于加载完成”。

## 使用边界

普通 services 和 imis 同目录 api 都复用共享 request，但目录和返回类型需按模块选择。
不要把旧代码中的 any、内联类型、宽捕获、可疑配置或生成风格升级为强制规则。
本资料提供可审查的历史选择；目标模块当前显式约定、接口契约与正确性要求优先。
