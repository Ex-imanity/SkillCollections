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

## 从 curl 命令封装认证调用

浏览器「复制为 cURL」得到的命令自带一段会话 Cookie。不要硬编码它。封装形式不固定
——可以是一条命令、一个 bash 函数，或代码库里的 Python 客户端；关键是遵循原则:

- **识别认证**:`-b` 里的 `SESSION` / `JSESSIONID` / `cas_name` / `CAS_AC_CURRENT_ROLE`
  / `uid` 表示这是 CAS 认证请求。粘贴的 Cookie 只作证据,绝不复用。
- **处理 Cookie**:用 `scripts/fetch_cookie.py` 取新 Cookie,置于内存或 `0600` 文件,
  整体作为 `Cookie` 头,绝不打印。bash:`curl -H "Cookie: $(cat "$COOKIE_FILE")" ...`。
- **最小封装**:只转发接口真正需要的头——通常就是 Cookie 加上带 JSON body 时的
  `content-type`。其余(`origin` / `referer` / `priority` / `sec-*` / `accept-language`
  / `user-agent` / 身份头 `uid`)一律丢弃,失败再逐个加回。(实测 `test-mi` 只需
  Cookie + `content-type`,`b_client` / `accept` / `uid` 都非必需。)
- **副作用先问**:`GET` / `HEAD` 可直接重放;`POST` / `PUT` / `PATCH` / `DELETE` 等
  可能改动数据的请求,重放前**必须**先向用户确认,不自动重试。

参考实现(可选):`scripts/call_api.py` 已内置以上原则——默认仅转发 `content-type`
(`--keep-header` 加回其他头),`--confirm-write` 前拒绝发送非 `GET`/`HEAD` 方法,
仅对读请求自动刷新重试一次。

```bash
# 读请求(GET/HEAD,或确认后的只读 POST 如 /list):
python scripts/call_api.py --curl-file request.curl --discover-cas --username your-account
# 有副作用的方法,仅在用户确认可安全重放后:
python scripts/call_api.py --curl-file request.curl --discover-cas --username your-account --confirm-write
```

内置主机可省略 `--discover-cas`;已知服务入口改用 `--cas-service-url`。响应体打印到
标准输出,主机 / 状态码 / 转发与丢弃的头名打印到标准错误,Cookie 不出现在任何一处。

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

多数高途内部接口在未登录时返回 HTTP `200`/`401` 且响应体为
`{"code":700,"data":"https://<cas>/cas/login?service=..."}`，`--discover-cas` 会从
`data` 的 `service` 参数自动得到服务地址。若只是裸 `401`、HTML 登录页，或 `data`
不指向可信 CAS，则无法自动推断，需显式 `--cas-service-url` 或浏览器回退。`403` 还可能
代表账号没有权限；即使获取了新 Cookie 后仍返回 `403`，也不应循环刷新或重试写操作。
