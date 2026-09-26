# 前端扩展配对评估摘要

日期：2026-09-26。两个独立 agent 分别读取旧版 1.0.2 和新版 1.1.0，处理同一
S7-S9 fixture；未读取彼此结果、expected_output 或真实业务仓库。下面是人工整理
的结果摘要，不是执行日志。两者只交付代码草图，没有修改源码、构建或浏览器验证。

## S7

旧版草图在 Options API methods 中调用 `$api.alphaApi.getCards`，参数为当前
productCode；`response.code === 0` 时赋值 `response.data.cards/total`，finally
恢复 loading。保留字符串 ID、零值及产品层，不迁移框架。

新版同样使用以上契约，另先快照 productCode，返回时检查当前选择是否相同再
赋值，并说明该判断未解决同产品并发请求的顺序和 loading 归属。

两者都选择 loadSummary、alphaApi、axios-contract 和当前 editorconfig 作为
证据；均建议验证 0、字符串 ID、total=0、失败收尾，新版另建议验证切换产品。
旧版指出非零业务码/错误展示惯例不足，新版指出并发约定不足。

## S8

两者都在已有 model 内复用 listCards 与 CardListRequest，把 current 转成
pageIndex，直接保留 status/published，读取返回根 list/total，输出 table 的
`{ data, total, success: true }`。新版草图另标注 CardListData 返回类型。

均依据 service、interface、base-contract 和 sibling model，不复制 H5 envelope，
不新增状态框架；建议 mock 检查完整分页参数及 0/false、失败路径和实际类型检查。
旧版明确缺完整 model 注册/导出上下文，新版要求接入现有 model 形式。

## S9

两者都新增 displayCoverUrl computed：`this.coverUrl || this.fallbackCover`，
只替换图片绑定，save 仍提交原始 coverUrl。选择当前协议、近邻展示范例和 tracked
editorconfig，拒绝 mounted 回写占位 URL 及历史 tabs。

均建议验证空串展示 fallback 但保存空串、非空 URL 保持；新版另明确从非空清空
后的状态。旧版说明图片标签仅为绑定草图，实际保留其他属性与布局。

## 结论与限制

人工按 evals.json 对照，S7-S9 两版均符合预期；未测得基本契约保持的改善。
新版多检查一项异步选择有效性，但不能把这项额外选择视为完整并发实现或效果证明。
输入直接提供契约、近邻和反例，未测量独立发现能力、自动触发率、真实 Review 返工
或 UI 行为。历史仓库研究和该合成评估是不同证据，不将其混为业务集成验证。
