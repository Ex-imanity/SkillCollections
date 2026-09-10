# Utilities & Resource Registry

<!-- SINGLE INDEX RULE
     This file is the ONE place every resource is registered — internal or
     external, remote or local. Findings, decisions, plans and task_state MUST
     cite a resource by its ID (e.g. "(res: R3)") instead of repeating the
     pointer, so an agent never has to guess which document holds it.

     Recovery and pre-compaction digests always replay this file (its sections
     are pinned, never recency-trimmed), so anything registered here survives
     /clear and context compaction.

     Column notes:
     - Access:   凭据名称 / 角色 / open / **读取命令或工具**
                 （例：`lark-cli docs +fetch --doc <url> --scope full`）。永不写凭据值。
     - Verified: 最后确认可达的日期 + **读到的版本**（例：`2026-09-07 (rev 607)`）。
     - 子资源清单（Base 表清单、文档章节目录、数据集文件列表）不要一行一条，
       容器登记为一行，清单挂到 `## Notes` 并以 ID 开头。
     - 不要登记「作为证据引用的单个源码文件」，那属于引用它的 finding。

     Rules:
     - One row per resource, one line each. Keep the table under ~25 rows;
       prune dead entries instead of letting it grow without bound.
     - Record credential NAMES, never values. A likely secret value fails
       verification.
     - Every row needs an explicit Sensitivity. `restricted` rows are omitted
       from snapshots and recovery digests; a row with no level is treated as
       restricted (dropped) whenever any row in the same section is restricted.
     - Register a resource the first time it is used, not at the end of the task.

     Type enumeration (extend via `other:<label>` — never invent a bare type):
       feishu-doc      飞书文档 / Wiki / 电子表格 / 多维表格 / 妙记
       web-page        外部网页、官方文档站、博客、规范
       repo            代码仓库（本地路径或远程 URL）
       local-path      本地文件、目录、数据集、日志文件
       service-api     HTTP/RPC 接口或服务端点
       database        数据库 / 缓存实例
       log-platform    日志 / Trace / 监控平台查询入口
       dashboard       报表、看板、指标页
       local-process   本地进程、端口、dev server、隧道
       static-site     本地或预览用静态页面 / 构建产物
       cli-tool        命令行工具
       mcp-tool        MCP server 或 skill 暴露的工具入口
       ticket          需求 / 缺陷 / 工单 / 用例平台条目
       test-asset      用例集、测试数据、录制流量
       credential-ref  凭据名称引用（只写名称，永不写值）
       other:<label>   以上未覆盖的类型，自定义 label

     Row shape:
       | R1 | feishu-doc | 需求 PRD | https://xxx.feishu.cn/docx/... | prod | 飞书登录 | internal | 2026-09-10 |
-->

## Resource Registry

| ID | Type | Name / Purpose | Pointer | Env | Access | Sensitivity | Verified |
|----|------|----------------|---------|-----|--------|-------------|----------|
| — | — | (none recorded) | — | — | — | — | — |

## Notes

<!-- Optional. Short operational caveats tied to a registered ID
     (e.g. "R4 needs VPN", "R7 link rotates monthly"). Not findings, not decisions. -->
- (none recorded)
