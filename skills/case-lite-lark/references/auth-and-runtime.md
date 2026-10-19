# 认证与云端运行

本 Skill 不实现 OAuth、不读取 keychain/.env/token、不自动修改全局配置。
普通读取使用 `--as user`，其应用和用户由平台的 lark-cli 配置决定。

## 认证错误恢复

1. 检查实际错误中的 type/subtype/code/missing_scopes/hint。保留报错，禁止输出密钥。
2. 平台已统一管理应用时，使用平台提供的授权入口；不要另建应用或覆盖配置。
3. 平台允许用户自行授权时，按所需 scope 发起 Device Flow：

   ```bash
   lark-cli auth login --scope "<缺失的 scope>" --no-wait --json
   ```

   原样展示 verification_url；需要二维码时：

   ```bash
   lark-cli auth qrcode "<完整 verification_url>" --output ./auth-qrcode.png
   ```

   将链接和二维码交给用户，结束当前轮次；不要在用户尚未看到链接时阻塞轮询。
4. 用户回复授权完成后，执行：

   ```bash
   lark-cli auth login --device-code "<本次返回的 device_code>"
   ```

   code 只用于本次流程，不复用过期 code，不把它存进任务产物或日志。
5. 重试原来的只读命令。需要诊断时可单独运行 `lark-cli auth status --json --verify`，
   不把完整认证输出写入语料或公开报告。

应用开通 scope、用户授予 scope、文档本身访问权是不同条件。资源权限拒绝须由
所有者或知识库管理员处理；不自动切换 bot、不循环登录试错。
Wiki code 131014 表示对象未挂载 Wiki，普通 Docx 可正常返回“无子文档”；
其他错误不降级成空列表。

## 权限范围

按实际请求的 missing_scopes 申请，不默认申请全部域。通常涉及 Docx 只读、Wiki 节点
读取、Drive 原生 Markdown 读取/媒体预览下载、画板读取；内嵌 Sheet 另需表格读取权限。
CLI 对不同 scope 可能支持多选一，不能把旧 MCP 的固定 scope 列表作为平台应用配置。
内部应用的 owner、环境、权限和用户映射由平台确认，不从其他 Skill 复制 app secret。

## 云端 Pod 约定与验收

- 固定平台 CLI 版本并运行 doctor；已核对 1.0.97 的实际命令与源代码。
- Pod 的网络应可访问飞书 API，写回搬山另需对应内部 HTTP 服务。
- 平台负责应用配置、用户登录态隔离、令牌刷新与 Pod 重建后的状态恢复。
- 图片保存在任务工作目录，CLI 传相对路径，manifest 返回绝对路径供 Claude Code Read。
- 模型和模型网关应支持图片输入；网页端图片预览不代表模型已经读图。
- 对话跨轮与产物目录须在选章、授权、审核期间可恢复；工作流文件不含凭证。

发布到平台前实际验证：一次授权与 Docx/Wiki/Markdown 读取、图片和画板 Read、
新会话/Pod 重建后登录态恢复。当前本地离线 fixtures 和 doctor 不能代替该验收。

## 参考来源

- 官方 lark-shared：身份与权限、JSON 输出、分步 Device Flow。
- [Lark CLI v1.0.97](https://github.com/larksuite/cli/tree/v1.0.97)。
- [Claude Code Read](https://code.claude.com/docs/en/tools-reference#read-tool-behavior)。
