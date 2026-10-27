# Changelog — internal-api-cookie-auth

本文件记录该 skill 的版本变更。版本号的唯一真相是 `SKILL.md` frontmatter 的 `version` 字段，
本文件顶部条目必须与之一致（由 `tests/test_repo_conventions.py` 校验）。

版本语义按**对使用者坏了什么**判定：

- **MAJOR** — 已有产物或用法失效，需要迁移
- **MINOR** — 新增能力，向后兼容
- **PATCH** — 修 bug、改文档、调措辞，行为不变

规则：不是每个 commit 都要升版本，但每次升版本必须在此留下条目。

## 1.0.2 - 2026-10-28

- 单元测试和评估迁到仓库级 tests/internal-api-cookie-auth、evals/internal-api-cookie-auth，运行认证和请求脚本及安装使用边界保持不变。

## 1.0.1 - 2026-10-04

- 修复 `--discover-cas` 只识别 `code=700`、漏掉高途接口实际使用的 `errorCode=700`。
- 允许安全解包可信的完整 CAS 登录 URL，避免误传给 `--cas-service-url` 时出现误导性的 Cookie 缺失错误。
- 增加对应回归测试，保持原有 CAS 主机、service 校验和凭证保护规则。

## 1.0.0 - 2026-09-03

首个标注版本。此前变更见 git 历史，不追认为 release。

当前能力基线：

- 为受支持的内部域名获取短期 CAS Cookie，规范认证失败后的处理路径
- 仅限允许的内部域名；不输出或持久化凭证
- 403 视为可能的权限问题，禁止盲目重试写操作
