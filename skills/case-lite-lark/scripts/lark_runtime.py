"""Select platform credentials or an explicitly onboarded local CLI profile."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROFILE = "case-lite-team"
CLI_INSTALL_HINT = "未安装 lark-cli；本地使用请先安装 CLI，平台使用请联系管理员预置"
PLATFORM_CONTEXT_VARIABLES = ("LARKSUITE_CLI_AUTH_PROXY", "OPENCLAW_HOME", "HERMES_HOME", "LARK_CHANNEL")


def platform_managed() -> bool:
    return any(os.environ.get(key) for key in PLATFORM_CONTEXT_VARIABLES)


def settings_path() -> Path:
    override = os.environ.get("CASE_LITE_LARK_SETTINGS")
    return Path(override).expanduser() if override else Path.home() / ".config/case-lite-lark/runtime.json"


def validate_profile(profile: str) -> str:
    forbidden = " /\\\"'`$#!&|;(){}[]<>?*~"
    if (not isinstance(profile, str) or not 1 <= len(profile) <= 64 or
            any(ord(char) <= 31 or ord(char) == 127 or char in forbidden for char in profile)):
        raise ValueError("profile 名称为空、超过 64 字符或包含 CLI 禁止的字符")
    return profile


@dataclass(frozen=True)
class LarkRuntime:
    mode: str = "platform"
    profile: str | None = None

    def command(self, *args: str) -> list[str]:
        prefix = ["lark-cli", "--profile", self.profile] if self.profile else ["lark-cli"]
        return [*prefix, *args]

    def describe(self) -> dict:
        return {"mode": self.mode, "profile": self.profile, "needs_mode_choice": self.mode == "auto"}


def load_runtime() -> LarkRuntime:
    mode = os.environ.get("CASE_LITE_LARK_MODE", "")
    if mode not in {"", "platform", "local"}:
        raise ValueError("CASE_LITE_LARK_MODE 只接受 platform 或 local")
    if mode == "platform":
        return LarkRuntime()  # Keep the platform's provider, environment and profile selection intact.
    if platform_managed():
        if mode == "local":
            raise ValueError("当前 CLI 由平台管理，不能强制使用本地 profile；请使用 platform 模式")
        return LarkRuntime()
    path = settings_path()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if mode == "local":
            raise ValueError("本地尚未接入团队应用；请先运行 setup_lark.py local --config-file <内部配置>") from None
        return LarkRuntime("auto")
    except (OSError, ValueError):
        raise ValueError("本地运行设置无法读取；请检查 CASE_LITE_LARK_SETTINGS 或重新执行本地接入") from None
    if not isinstance(settings, dict) or settings.get("mode") != "local":
        raise ValueError("本地运行设置无效；请重新执行本地接入，不回退其他应用身份")
    return LarkRuntime("local", validate_profile(settings.get("profile")))


def cli_environment() -> dict[str, str]:
    return dict(os.environ, LARKSUITE_CLI_NO_UPDATE_NOTIFIER="1", LARKSUITE_CLI_NO_SKILLS_NOTIFIER="1")
