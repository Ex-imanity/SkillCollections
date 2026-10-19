"""Read-only lark-cli boundary. Credentials stay in the selected CLI context."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from lark_runtime import CLI_INSTALL_HINT, cli_environment, load_runtime


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()
                if key.lower().replace("_", "") not in {"accesstoken", "refreshtoken", "appsecret", "authorization", "devicecode"}}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", value)
        return re.sub(r"(?i)((?:access_token|refresh_token|app_secret)\s*[=:]\s*)[^\s,\"']+", r"\1[REDACTED]", value)
    return value


class CLIError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        self.details = redact(details or {"message": message})
        super().__init__(redact(message))


class LarkCLI:
    READ_COMMANDS = {
        ("wiki", "+node-get"), ("wiki", "+node-list"),
        ("markdown", "+fetch"), ("docs", "+media-preview"),
        ("docs", "+media-download"), ("whiteboard", "+export"),
    }

    def __init__(self, cwd: Path | None = None, timeout: int = 120):
        self.cwd = (cwd or Path.cwd()).resolve()
        self.timeout = timeout
        try:
            self.runtime = load_runtime()
        except ValueError as exc:
            raise CLIError(str(exc)) from exc

    def call(self, *args: str) -> dict:
        if tuple(args[:2]) not in self.READ_COMMANDS and tuple(args[:2]) != ("api", "GET"):
            raise CLIError("仅允许只读 CLI 命令；认证请按授权指引单独执行")
        if "--as" in args or "--format" in args:
            raise CLIError("身份和输出格式由适配器固定管理")
        return self._json([*args, "--as", "user", "--format", "json"])

    def _json(self, args: list[str]) -> dict:
        env = cli_environment()
        try:
            result = subprocess.run(self.runtime.command(*args), cwd=self.cwd, env=env,
                                    capture_output=True, text=True, encoding="utf-8",
                                    timeout=self.timeout, check=False)
        except FileNotFoundError as exc:
            raise CLIError(CLI_INSTALL_HINT, self.runtime.describe() | {"message": CLI_INSTALL_HINT}) from exc
        except subprocess.TimeoutExpired as exc:
            raise CLIError("lark-cli 调用超时；请检查网络和平台执行时限") from exc
        stream = result.stdout if result.returncode == 0 else result.stderr
        try:
            envelope = json.loads(stream)
        except (ValueError, TypeError) as exc:
            raise CLIError("lark-cli 未返回有效 JSON；请检查 CLI 版本和命令支持情况",
                           {"message": "invalid CLI JSON", "exit_code": result.returncode}) from exc
        if not isinstance(envelope, dict):
            raise CLIError("lark-cli JSON 信封必须为对象")
        if result.returncode or envelope.get("ok") is not True:
            error = envelope.get("error") or {"message": "CLI 未确认成功", "exit_code": result.returncode}
            if not isinstance(error, dict):
                error = {"message": "invalid CLI error envelope"}
            if error.get("subtype") == "not_configured":
                if self.runtime.mode == "auto":
                    hint = "请先确认在本地还是平台运行；本地导入内部提供的已有团队应用配置，平台联系管理员接入绑定 App；不要创建新应用"
                elif self.runtime.mode == "platform":
                    hint = "请由平台管理员将绑定应用接入本 Pod 的 lark-cli；不要创建新应用"
                else:
                    hint = "请运行 setup_lark.py local --config-file <内部配置> 接入已有团队应用；不要创建新应用"
                error = error | {"case_lite_mode": self.runtime.mode,
                                 "needs_mode_choice": self.runtime.mode == "auto",
                                 "hint": hint, "case_lite_hint": hint}
            raise CLIError(str(error.get("message", "CLI 调用失败")), error)
        if envelope.get("identity") != "user":
            raise CLIError("CLI 未确认 user 身份；请检查平台用户登录态，禁止回退到 bot")
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise CLIError("CLI data 不是预期对象；请检查 CLI 版本")
        return data

    def get(self, path: str, params: dict | None = None) -> dict:
        if not path.startswith("/open-apis/") or "?" in path or "#" in path:
            raise CLIError("API 路径必须以 /open-apis/ 开头；查询参数单独传递")
        args = ["api", "GET", path]
        if params:
            args += ["--params", json.dumps(params, ensure_ascii=False)]
        return self.call(*args)

    def media(self, media: dict, output_root: Path) -> str:
        root = output_root.resolve()
        relative = Path(media["expected_path"])
        expected = (root / relative).resolve()
        if not expected.is_relative_to(root):
            raise CLIError("媒体输出路径越界")
        expected.parent.mkdir(parents=True, exist_ok=True)
        # Paths passed to CLI stay relative to its CWD. Image filenames may gain a suffix.
        output = os.path.relpath(expected, self.cwd)
        if output.startswith(".."):
            raise CLIError("媒体目录必须位于 CLI 当前工作目录下")
        token = media.get("token", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise CLIError("缺少或非法媒体 token")
        if media["media_type"] == "board":
            data = self.call("whiteboard", "+export", "--whiteboard-token", token,
                             "--output-type", "preview", "--output", output, "--overwrite")
            saved = data.get("preview_image_path")
        else:
            try:
                data = self.call("docs", "+media-preview", "--token", token, "--output", output, "--overwrite")
            except CLIError as exc:
                if exc.details.get("type") != "permission_denied" and exc.details.get("code") != 403:
                    raise
                data = self.call("docs", "+media-download", "--token", token, "--output", output, "--overwrite")
            saved = data.get("saved_path")
        if not isinstance(saved, str) or not saved:
            raise CLIError("媒体命令缺少保存路径，无法确认图片可读")
        path = Path(saved)
        path = (self.cwd / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size == 0:
            raise CLIError("媒体下载未产生任务目录内的非空图片文件")
        return str(path)
