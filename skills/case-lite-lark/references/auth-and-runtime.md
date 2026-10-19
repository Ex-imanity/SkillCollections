# 认证与运行模式

本 Skill 的两端使用同一套文档和用例脚本。应用配置与用户授权分开管理：
团队共用已有应用，每位成员登录自己的账号。脚本不读取 CLI token、旧 MCP 的 `.env`
或其他 Skill 的凭证；平台绑定应用不等于用户已授权，也不保证 CLI 已接入绑定配置。

## 模式选择

运行 `python3 "{skill}/scripts/feishu_docs.py" doctor` 查看 `mode`、`profile`、`needs_mode_choice`。
它仅检查命令能力；`auth_verified:false` 不能用于判断登录失败或触发初始化。

- `CASE_LITE_LARK_MODE=platform`：保留平台提供的凭证来源、环境变量和 CLI profile。
  不读本地接入设置，不导入应用。推荐平台 Agent 显式设置此值。
- 已识别的平台凭证代理或 OpenClaw/Hermes/Lark Channel 上下文，默认走平台模式；
  此时本地接入脚本拒绝改配，不加 `--force-init` 绕过。
- 本地执行一次接入后，使用 `~/.config/case-lite-lark/runtime.json` 中记录的 profile。
- 没有本地设置且没有明确的平台上下文时，返回 `mode:auto`、`needs_mode_choice:true`。
  先确认用户是在本地还是平台运行并等待回复，不仅凭 Linux/macOS 或 `not_configured` 猜测。
  已明确运行位置时不重复询问。`auto` 是诊断返回值，不是环境变量的可选值。
  用户选择平台后，对后续 doctor、授权和读取入口显式传 `CASE_LITE_LARK_MODE=platform`；
  用户选择本地后按下文接入一次。本轮未选择前不发起登录、配置或文档读取。
- 可用 `CASE_LITE_LARK_SETTINGS` 指定用户运行设置文件位置；文件不含 Secret/token。
  `CASE_LITE_LARK_MODE=local` 显式要求本地设置存在；损坏/缺失时中止，不回退其他身份。

## 平台：复用绑定应用

管理员把已有应用绑定到 Agent，并通过平台支持的凭证注入方式提供给同一 Pod 中的
lark-cli。Skill 不执行应用初始化。若真实请求返回 `not_configured`，报告错误并联系
平台管理员，验证 CLI 的凭证接入；不要因 CLI hint 提及初始化就执行新建 App。

平台负责每位用户的登录态隔离与持久化。验收必须在实际运行环境中以 `--as user`
读取真实文档；仅在管理页面显示“已绑定”不能作为 CLI 可用的证据。

## 本地：一次性接入团队已有应用

管理员确认应用的业务归属、环境、成员可用范围及所需权限已发布，通过内部渠道提供
JSON 配置，格式见 [示例](../assets/team-app.example.json)。该配置放在 Skill 分发目录之外，
不要把填好的配置提交到仓库或发进聊天。团队成员无需各自创建应用。

```bash
python3 "{skill}/scripts/setup_lark.py" local --config-file "/path/to/private/team-app.json"
```

默认 profile 是 `case-lite-team`，可通过 `--profile <name>` 指定名称。脚本先检查：

1. 同名 profile 指向其他 App：中止，不覆盖。
2. 同一 App 已在任意 profile 下配置：复用其原名称，不重写 Secret 或用户列表。
3. 完全未配置该 App：通过 `config init --name ... --app-id ... --app-secret-stdin`
   导入已有应用，保留其他配置与默认应用；不使用 `--new`。
4. 配置损坏、CLI 命令失败或初始化后网络探测失败：中止，不自动重试。初始化失败时
   配置可能已经保存，应先核对状态。凭证更新由管理员另行处理，重复接入不用于轮换 Secret。

接入脚本按 CLI 配置目录互斥执行；接入期间不要在其他终端用原生 CLI 改配，
原生 CLI 不参与本脚本的互斥。

成功后仅保存模式和 profile。后续授权、读取和媒体下载统一选用此 profile；CLI 自行
管理应用凭证和用户令牌。接入本身不登录，不承诺文档权限已具备。

已有旧版 case-lite/feishu-docx-blocks 也需给 CLI 接入已有 App，旧 MCP 的配置和登录态
不自动迁移；仅删除旧 Skill 安装目录不会删除 CLI 状态。全新成员由管理员提供同一个
团队 App 配置，个人完成授权即可，不要求创建新应用。

## 用户授权与认证错误恢复

两端统一使用下面的包装入口，确保授权与文档读取落在同一凭证上下文，不自行拼接
另一套 `--profile`。缺配置先处理上述接入问题；有应用但缺用户授权时才执行 login。

需要诊断时：

```bash
python3 "{skill}/scripts/setup_lark.py" status --verify
```

该命令透传 CLI 原始 JSON，不是文档工具的 `ok/data` 信封。检查
`identities.user.available`、`identities.user.status` 及 `verified/verifyError`。
顶层 `identity:bot`、退出码 0 或应用已配置，都不表示用户已登录。
不要把完整认证输出写入需求语料或公开报告。

按实际错误中的 `missing_scopes` 申请所需权限，不默认请求全部域：

```bash
python3 "{skill}/scripts/setup_lark.py" login --scope "<缺失的 scope>"
```

首次没有用户授权、错误未提供 scope 时，可按本工作流的文档用途申请对应域：

```bash
python3 "{skill}/scripts/setup_lark.py" login --domain docs --domain drive --domain wiki
```

包装入口自动使用 `--no-wait --json`，返回本次 `verification_url` 和 `device_code`。
URL 原样转发并生成二维码，URL 在前、二维码在后：

```bash
python3 "{skill}/scripts/setup_lark.py" qrcode "<完整 verification_url>" --output ./auth-qrcode.png
```

展示链接与二维码，告知用户完成后回复，结束本轮。不要在用户尚未看到链接时阻塞轮询。
用户回复完成后，由 Agent 在后续轮次继续：

```bash
python3 "{skill}/scripts/setup_lark.py" login --device-code "<本次返回的 device_code>"
```

code 仅用于本次流程，不写入任务产物、不复用过期链接。成功后重试原来的只读命令。
本地与平台各自保存授权状态，同一个 App 不会自动同步两端用户 token。

应用开通 scope、用户授予 scope、文档访问权是不同条件。资源拒绝须由所有者或
知识库管理员处理；不切换 bot、不循环登录。Wiki code 131014 表示对象未挂载 Wiki，
普通 Docx 可正常返回“无子文档”；其他错误不降级成空列表。

## 运行条件与验收

- Python 3.10+、lark-cli；原读取契约核对 1.0.97，新增接入/命名 profile 契约核对 1.0.98。
- 网络可访问飞书 API；写回搬山另需对应内部 HTTP 服务。
- 本地用户设置和 CLI 状态跨任务保留；平台负责登录态隔离、刷新和 Pod 重建恢复。
- 图片保存在任务工作目录，CLI 传相对路径，manifest 返回绝对路径供 Agent Read。
- 模型和网关须支持图片输入；网页图片预览不代表模型已经读图。
- 选章、授权、审核期间会话和任务产物须可恢复，任务工作流文件不含凭证。

实际验收：首次本地接入和重复接入、各自用户授权、Docx/Wiki/Markdown 读取、
图片/画板 Read，以及新会话/Pod 重建恢复。离线 fixtures 和 doctor 不能替代真实联调。

## 参考来源

- 官方 lark-shared：身份与权限、JSON 输出、分步 Device Flow。
- [CLI 配置导入](https://github.com/larksuite/cli/blob/v1.0.98/cmd/config/init.go)、
  [配置展示](https://github.com/larksuite/cli/blob/v1.0.98/cmd/config/show.go)、
  [profile 列表](https://github.com/larksuite/cli/blob/v1.0.98/cmd/profile/list.go)。
- [Lark CLI v1.0.97](https://github.com/larksuite/cli/tree/v1.0.97)。
- [Claude Code Read](https://code.claude.com/docs/en/tools-reference#read-tool-behavior)。
