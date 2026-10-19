#!/usr/bin/env python3
"""Import an existing team app locally, or authorize the selected CLI context."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from lark_cli import CLIError
from lark_runtime import CLI_INSTALL_HINT, DEFAULT_PROFILE, LarkRuntime, cli_environment, load_runtime, platform_managed, settings_path, validate_profile


def control_json(runtime: LarkRuntime, *args: str, secret: str | None = None):
    """CLI management commands return raw JSON, unlike document API envelopes."""
    options = {"input": secret + "\n"} if secret is not None else {"stdin": subprocess.DEVNULL}
    result = subprocess.run(runtime.command(*args), env=cli_environment(), capture_output=True,
                            text=True, encoding="utf-8", check=False, timeout=120, **options)
    stream = result.stdout if result.returncode == 0 else result.stderr
    if secret:
        stream = stream.replace(secret, "[REDACTED]")
    try:
        payload = json.loads(stream)
    except ValueError:
        raise CLIError("CLI 配置命令未返回有效 JSON；停止接入，请检查 CLI 版本和配置") from None
    if result.returncode:
        error = payload.get("error") if isinstance(payload, dict) else None
        raise CLIError("CLI 配置检查失败", error if isinstance(error, dict) else None)
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise CLIError("CLI 配置命令未确认成功")
    return payload


def save_local_settings(profile: str) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"mode": "local", "profile": profile}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


@contextmanager
def onboarding_lock():
    """Serialize our imports in the CLI config directory, including the preflight."""
    override = os.environ.get("LARKSUITE_CLI_CONFIG_DIR")
    directory = Path(override).expanduser() if override else Path.home() / ".lark-cli"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / ".case-lite-onboarding.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise CLIError("已有本地接入正在执行；请等待结束后重试，不并发改配") from None
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CLIError("已有本地接入正在执行；请等待结束后重试，不并发改配") from None
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def configure_local(config_file: Path, profile: str) -> dict:
    # A local import is explicit; ordinary reads and the platform path never call this.
    if os.environ.get("CASE_LITE_LARK_MODE") == "platform" or platform_managed():
        raise CLIError("当前是平台管理的应用环境；请复用绑定配置，不能在此导入本地应用")
    validate_profile(profile)
    if config_file.expanduser().resolve() == settings_path().resolve():
        raise CLIError("团队配置和运行设置必须使用不同文件")
    try:
        team = json.loads(config_file.expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CLIError("无法读取团队应用配置；请通过内部渠道获取有效 JSON 配置") from None
    if not isinstance(team, dict):
        raise CLIError("团队应用配置必须是 JSON 对象")
    app_id, secret, brand = team.get("app_id"), team.get("app_secret"), team.get("brand", "feishu")
    if not isinstance(app_id, str) or not re.fullmatch(r"cli_[A-Za-z0-9_]+", app_id):
        raise CLIError("请填写团队已有应用的有效 app_id，不使用示例占位符")
    if not isinstance(secret, str) or not secret.strip() or any(ord(c) < 32 for c in secret):
        raise CLIError("团队应用配置缺少有效 app_secret")
    if not isinstance(brand, str) or brand not in {"feishu", "lark"}:
        raise CLIError("brand 只接受 feishu 或 lark")
    with onboarding_lock():
        return configure_profile(app_id, secret, brand, profile)


def configure_profile(app_id: str, secret: str, brand: str, profile: str) -> dict:
    # Listing before init also rejects malformed config. Never interpret an arbitrary
    # CLI error as an empty config: upstream init would otherwise replace it.
    profiles = control_json(LarkRuntime(), "profile", "list")
    if not isinstance(profiles, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("name"), str) or
            not isinstance(item.get("appId"), str) or not item["name"] or not item["appId"]
            for item in profiles):
        raise CLIError("CLI profile 列表格式无效，停止接入")
    named = next((item for item in profiles if item["name"] == profile), None)
    if named and named["appId"] != app_id:
        raise CLIError("同名 profile 已绑定其他应用；请指定其他 --profile，不覆盖原应用")
    # Two aliases for one App ID share the secret store. Reuse an existing alias
    # rather than reimporting the secret through another named config.
    existing = named or next((item for item in profiles if item["appId"] == app_id), None)
    state = "reused" if existing else "initialized"
    if existing:
        profile = existing["name"]
        if existing.get("brand") != brand:
            raise CLIError("已有应用的 brand 与团队配置不一致，停止接入")
    else:
        try:
            control_json(LarkRuntime(), "config", "init", "--name", profile, "--app-id", app_id,
                         "--app-secret-stdin", "--brand", brand, secret=secret.strip())
        except (CLIError, subprocess.TimeoutExpired):
            # Init can persist config before a failing network probe. Do not resend,
            # roll back another caller's config, or mark local onboarding complete.
            raise CLIError("CLI 初始化未确认成功，配置可能已保存；请检查 CLI 配置和原始平台错误，再决定是否重试",
                           {"message": "CLI 初始化未确认成功，配置可能已保存；停止接入，不自动重试",
                            "configuration_may_be_saved": True}) from None
    selected = control_json(LarkRuntime("local", profile), "config", "show")
    if not isinstance(selected, dict) or selected.get("appId") != app_id or selected.get("brand") != brand:
        raise CLIError("CLI 未确认选中了预期团队应用，停止接入")
    path = save_local_settings(profile)
    return {"mode": "local", "profile": profile, "app_id": app_id, "state": state,
            "settings_path": str(path.resolve()), "auth_verified": False,
            "message": "已接入已有应用，未创建应用、未发起用户授权；使用 status 检查并按需 login"}


def forward_auth(runtime: LarkRuntime, args: list[str]) -> int:
    # Preserve native split-flow JSON (including the one-time device_code), exit
    # codes and QR output. Do not store auth output or copy another user's login.
    if args[0] == "login" and runtime.mode == "auto":
        raise CLIError("请先确认在本地还是平台运行；本地先接入团队应用，平台显式选择 platform 后再授权")
    result = subprocess.run(runtime.command("auth", *args), env=cli_environment(),
                            check=False, timeout=120)
    return result.returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser("local", help="一次性导入内部提供的已有应用，不创建应用")
    local.add_argument("--config-file", type=Path, required=True)
    local.add_argument("--profile", default=DEFAULT_PROFILE)
    status = commands.add_parser("status", help="检查当前模式的用户登录态")
    status.add_argument("--verify", action="store_true")
    login = commands.add_parser("login", help="按指定范围发起用户授权，或继续本次 Device Flow")
    login.add_argument("--scope", action="append", default=[])
    login.add_argument("--domain", action="append", default=[])
    login.add_argument("--device-code")
    qr = commands.add_parser("qrcode", help="将完整授权 URL 转为二维码")
    qr.add_argument("url")
    qr.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "login":
        if bool(args.device_code) == bool(args.scope or args.domain):
            parser.error("login 需指定 --scope/--domain，或仅用 --device-code 继续授权")
        if any(not value.strip() for value in [*args.scope, *args.domain]):
            parser.error("授权范围不能为空")
    try:
        if args.command == "local":
            data = configure_local(args.config_file, args.profile)
            print(json.dumps({"ok": True, "data": data}, ensure_ascii=False, indent=2))
            return 0
        runtime = load_runtime()
        if args.command == "status":
            return forward_auth(runtime, ["status", "--json", *(["--verify"] if args.verify else [])])
        if args.command == "qrcode":
            return forward_auth(runtime, ["qrcode", args.url, "--output", args.output])
        if args.device_code:
            return forward_auth(runtime, ["login", "--device-code", args.device_code])
        scopes = [flag for value in args.scope for flag in ("--scope", value)]
        domains = [flag for value in args.domain for flag in ("--domain", value)]
        return forward_auth(runtime, ["login", *scopes, *domains, "--no-wait", "--json"])
    except CLIError as exc:
        error = exc.details
    except FileNotFoundError:
        error = {"message": CLI_INSTALL_HINT}
    except subprocess.TimeoutExpired:
        error = {"message": "CLI 调用超时；请检查当前状态，不自动重试或创建应用"}
    except ValueError as exc:
        error = {"message": str(exc)}
    except OSError:
        error = {"message": "无法保存本地运行设置，请检查用户配置目录权限"}
    print(json.dumps({"ok": False, "error": error}, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
