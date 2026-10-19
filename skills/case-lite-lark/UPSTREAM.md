# 来源与维护边界

- 新 Skill：case-lite-lark 0.1.0，独立分发，不从机器上的其他仓库或 Skill 导入。
- 工作流、写回 Markdown 解析器与风格规则源自 SkillCollections 的 case-lite 1.2.0，
  基线提交 `5b1e57972b22e0a738e0bf79722a6cd2ebf87a9c`。新版本独立维护。
- scripts/block_processor.py 来自 feishu-docx-blocks 3.4.0 的 src/block_processor.py，
  上游提交 `e5226dbf483874261467f4e31e0429ac6af016ba`。
  本包清理行末空白，并修复：表格单元格静默截断、合法重复文本丢失、
  单元格子块顺序和超链接目标遗漏；这些改动仅在新 Skill 内。
  本次已校验 PyPI 3.4.0 wheel 的 38 个 Python 文件与该提交工作目录逐字节一致。
  本文件 SHA256：`969519e0d09880c82c287eb8a1159bfc76e85b03765baddd6fde7a418bd4bf7a`。
- Markdown ATX/围栏/层级解析改编自同版本 get_markdown_file_sections.py 的纯解析逻辑，
  去除 MCP 类型，补充原始换行保留、闭围栏判断、重叠去重和变更检测。
- 上游 pyproject.toml 声明 MIT；本包随附 LICENSE。未复制凭证、授权文件或上游调试数据。
- CLI 适配按官方 v1.0.97 源码核对：raw API 使用单层 CLI data，Wiki nodes 是 nodes，
  Markdown 是 content，媒体是 saved_path，画板是 preview_image_path。
- 新写回脚本复用已有搬山业务接口，增加显式确认、格式警告阻塞、空用例检查、
  JSON-RPC/MCP/业务响应检查和树内容读回比较；原 case-lite 未修改。

参考：
- [PyPI 3.4.0](https://pypi.org/project/feishu-docx-blocks/3.4.0/)
- [Lark CLI v1.0.97](https://github.com/larksuite/cli/tree/v1.0.97)

升级时先核对上游 diff 与 CLI 帮助/JSON 契约，更新 fixtures 并运行回归。
离线验证不代表真实平台 OAuth、下载和模型视觉已验收。
