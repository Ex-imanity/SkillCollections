# 内部接口 Cookie 认证

这个 Skill 用于开发和排查调用内部 HTTP 接口的脚本，无需手动导出或粘贴会话 Cookie。
它会调用本机的 `baijia-cookie` 工具获取新的 CAS Cookie，并将其写入权限为 `0600`
的文件。内置站点可以直接登录；其他内部站点必须先由一次已获用户授权的只读请求证明其
确实跳转到可信 CAS，才会提交登录凭证。

## 依赖

Cookie 工具的默认目录：

```text
/Users/gaotu/Projects/baijia-cookie
```

目录不同可通过环境变量覆盖：

```bash
export BAIJIA_COOKIE_TOOL_DIR=/path/to/baijia-cookie
```

该目录需要已安装 Node.js 依赖。

## 手动使用

请在交互式终端运行。脚本会提示输入凭证，密码不会进入 Shell 历史或命令行参数：

```bash
COOKIE_FILE="$(mktemp)"
python scripts/fetch_cookie.py \
  --url https://internal-ad.gaotu100.com/welcome \
  --output "$COOKIE_FILE" \
  --username your-account
```

随后将 Cookie 文件传给支持 `--cookie-file` 的脚本：

```bash
python /Users/gaotu/Projects/FeedbackEntrance/scripts/batch_qapair_status.py \
  offline --ids-file qapair_ids.txt --cookie-file "$COOKIE_FILE" --execute
rm -f "$COOKIE_FILE"
```

## 其他 CAS 站点

除 Internal AD / UOS、Athena、Compass 外，其他内部 HTTPS 站点也可以使用，但不再依赖
静态域名白名单。前提是用户已允许对一个无副作用的读取地址进行一次无 Cookie 探测：

```bash
COOKIE_FILE="$(mktemp)"
python scripts/fetch_cookie.py \
  --url https://internal-service.example.com/api/status \
  --discover-cas \
  --output "$COOKIE_FILE" \
  --username your-account
```

该探测不携带 Cookie，也不跟随跳转。只有响应跳转到与环境匹配的
`cas.baijia.com` 或 `test-cas.baijia.com`，且包含 HTTPS `service` 参数时，工具才会
继续登录。若已知 CAS 服务地址，也可改用 `--cas-service-url https://.../auth/login/cas`。

不要把上架、下架、创建、更新、删除等写接口作为探测地址。先选择健康检查、详情查询或
其他明确无副作用的 `GET` / `HEAD` 地址。

非交互环境可通过 `SITE_USERNAME` 和 `SITE_PASSWORD` 提供凭证。不要提交凭证或生成的
Cookie 文件。

## 内置主机

- Internal AD / UOS：生产和 `test-` 测试环境
- Athena：生产和 `test-` 测试环境
- Compass：生产和 `test-` 测试环境

`401` 或 JSON `code:700` 只表示可能需要认证，不能单独证明 CAS 服务地址。`403` 还可能
代表账号没有权限；即使获取了新 Cookie 后仍返回 `403`，也不应循环刷新或重试写操作。
