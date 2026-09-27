#!/usr/bin/env python3
"""
case-lite MCP setup helper.

Default mode is diagnostic only. Use --fix after explicit user approval to
merge MCP config for Claude Code or Codex.

Safety contract (see references/install-mcp.md):
- Never guesses silently: when the Claude Code global config path is ambiguous
  (both new/old paths exist, e.g. legacy cc-switch override) it refuses to write
  until the user confirms which path is active.
- Never clobbers an existing feishu-docx-blocks entry unless the user opts in
  via --replace-feishu (or confirms interactively). Missing servers are added.
- Writes atomically, backs up first, and chmods secret-bearing files to 0o600.
- Reads credentials from env or existing config; never embeds default secrets.
"""
from __future__ import annotations

import argparse
import dataclasses
import getpass
import json
import os
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Any


BANSHAN_MCP_URL = "https://tech.baijia.com/mcp-server/banshan/mcp"
FEISHU_INTERNAL_DOC_URL = (
    "https://gaotuedu.feishu.cn/wiki/CNBZwz8rwiew8dkXHt1cRIAAn8g"
    "#share-DrNhdQPiToYWMXxyC6nciHlknJh"
)
# 旧版 cc-switch 会覆盖 Claude Code 的 MCP 配置路径，详情见此 PR。
CC_SWITCH_PATH_PR = "https://github.com/farion1231/cc-switch/pull/3431"


@dataclasses.dataclass
class ClaudeCodeConfigChoice:
    """Which Claude Code global config file to use, and whether it is ambiguous.

    The active path depends on whether a legacy cc-switch (<v3.16.4) overrode it
    to ~/.claude.json — that cannot be inferred from file existence alone, so
    when both candidates exist we flag it ambiguous and ask the user to confirm.
    """

    path: Path
    candidates: list[Path]
    ambiguous: bool
    note: str


@dataclasses.dataclass
class DiagnosticReport:
    agent: str
    config_path: Path
    uv_available: bool
    python_version: str
    feishu_configured: bool
    feishu_uses_latest: bool
    banshan_configured: bool
    feishu_app_id: str | None
    feishu_app_secret: str | None
    cred_source: str = "未提供"
    config_ambiguous: bool = False
    config_candidates: list[Path] = dataclasses.field(default_factory=list)
    config_note: str = ""

    def to_markdown(self) -> str:
        lines = [
            "# case-lite MCP 诊断报告",
            "",
            f"- Agent: `{self.agent}`",
            f"- 配置文件: `{self.config_path}`",
            f"- Python: `{self.python_version}`",
            f"- uv/uvx: {status(self.uv_available)}",
            f"- feishu-docx-blocks: {status(self.feishu_configured)}",
            f"- feishu-docx-blocks@latest: {status(self.feishu_uses_latest)}",
            f"- Banshan MCP: {status(self.banshan_configured)}（注：仅检查是否配置，不代表已连通）",
            f"- FEISHU_APP_ID: `{self.feishu_app_id or '<未提供>'}`（来源：{self.cred_source}）",
            f"- FEISHU_APP_SECRET: `{redact_secret(self.feishu_app_secret)}`",
            "",
        ]
        if self.config_ambiguous:
            lines.extend(
                [
                    "## ⚠️ 配置路径不确定",
                    "",
                    self.config_note,
                    "",
                    "候选路径：",
                    *[f"- `{p}`" for p in self.config_candidates],
                    "",
                    "自动修复前请确认哪个是**生效**路径，并用 `--config <路径>` 显式指定。",
                    f"参考：{CC_SWITCH_PATH_PR}",
                    "",
                ]
            )
        if not self.feishu_app_id or not self.feishu_app_secret:
            lines.extend(
                [
                    "## 需要补充",
                    "",
                    "未检测到完整的 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`。",
                    f"请从内部文档获取默认值：{FEISHU_INTERNAL_DOC_URL}",
                    "建议通过环境变量或交互输入提供，不要把 secret 写入命令历史或 skill 文档。",
                    "",
                ]
            )
        if self.feishu_configured and not self.feishu_uses_latest:
            lines.extend(
                [
                    "## 建议升级",
                    "",
                    "`feishu-docx-blocks` 已配置，但未使用 `feishu-docx-blocks@latest`。",
                    "建议征求用户同意后，用 `--replace-feishu` 升级，确保 `get_child_documents` 等新工具可用。",
                    "",
                ]
            )
        if not self.uv_available:
            lines.extend(
                [
                    "## 需要先安装 uv",
                    "",
                    "未检测到 `uv` 或 `uvx`。请先安装 uv 后再配置 `feishu-docx-blocks`。",
                    "参考：https://docs.astral.sh/uv/getting-started/installation/",
                    "",
                ]
            )
        if not self.feishu_configured or not self.banshan_configured:
            lines.extend(
                [
                    "## 可自动修复",
                    "",
                    "在用户明确同意后，可重新运行本脚本并添加 `--fix` 写入全局 MCP 配置。",
                    "脚本会先备份原配置，再 merge 缺失的 MCP server，不覆盖其他配置。",
                    "已存在的 `feishu-docx-blocks` 默认保留，需要替换时显式加 `--replace-feishu`。",
                    "",
                ]
            )
        return "\n".join(lines)


def status(value: bool) -> str:
    return "OK" if value else "缺失"


def redact_secret(value: str | None) -> str:
    if not value:
        return "<未提供>"
    return "***"


def feishu_server(feishu_app_id: str, feishu_app_secret: str) -> dict[str, Any]:
    return {
        "command": "uvx",
        "args": ["feishu-docx-blocks@latest"],
        "type": "stdio",
        "env": {
            "FEISHU_APP_ID": feishu_app_id,
            "FEISHU_APP_SECRET": feishu_app_secret,
        },
    }


def banshan_server() -> dict[str, Any]:
    return {
        "type": "streamable-http",
        "url": BANSHAN_MCP_URL,
    }


def merge_claude_code_config(
    existing: dict[str, Any],
    *,
    feishu_app_id: str,
    feishu_app_secret: str,
    write_feishu: bool = True,
    write_banshan: bool = True,
) -> dict[str, Any]:
    """Merge required MCP servers into an existing Claude Code config.

    Only the servers whose write flag is True are touched; every other key and
    server (including an existing feishu-docx-blocks when write_feishu is False)
    is preserved verbatim.
    """
    merged = dict(existing)
    servers = dict(merged.get("mcpServers") or {})
    if write_feishu:
        servers["feishu-docx-blocks"] = feishu_server(feishu_app_id, feishu_app_secret)
    if write_banshan:
        servers["Banshan"] = banshan_server()
    merged["mcpServers"] = servers
    return merged


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_quote(v) for v in values) + "]"


def _toml_header_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("["):
        return None

    in_single = False
    in_double = False
    escaped = False
    for idx, char in enumerate(stripped):
        if escaped:
            escaped = False
            continue
        if in_double and char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "]" and not in_single and not in_double:
            rest = stripped[idx + 1 :].strip()
            if rest and not rest.startswith("#"):
                return None
            name = stripped[1:idx].strip()
            return name or None
    return None


def _strip_toml_table(text: str, table: str) -> str:
    lines = text.splitlines()
    result: list[str] = []
    skipping = False
    for line in lines:
        header = _toml_header_name(line)
        if header == table or (header and header.startswith(f"{table}.")):
            skipping = True
            continue
        if skipping and header is not None:
            skipping = False
        if not skipping:
            result.append(line)
    return "\n".join(result).rstrip()


def merge_codex_config(
    existing: str,
    *,
    feishu_app_id: str,
    feishu_app_secret: str,
    write_feishu: bool = True,
    write_banshan: bool = True,
) -> str:
    """Merge required MCP tables into an existing Codex config.toml (text).

    Tables whose write flag is False are left untouched, so an existing
    feishu-docx-blocks table survives a banshan-only fix.
    """
    text = existing
    if write_feishu:
        text = _strip_toml_table(text, "mcp_servers.feishu-docx-blocks")
    if write_banshan:
        text = _strip_toml_table(text, "mcp_servers.banshan")

    additions: list[str] = []
    if write_feishu:
        additions.extend(
            [
                "[mcp_servers.feishu-docx-blocks]",
                'command = "uvx"',
                f"args = {_toml_array(['feishu-docx-blocks@latest'])}",
                "",
                "[mcp_servers.feishu-docx-blocks.env]",
                f"FEISHU_APP_ID = {_toml_quote(feishu_app_id)}",
                f"FEISHU_APP_SECRET = {_toml_quote(feishu_app_secret)}",
                "",
            ]
        )
    if write_banshan:
        additions.extend(
            [
                "[mcp_servers.banshan]",
                f"url = {_toml_quote(BANSHAN_MCP_URL)}",
                "",
            ]
        )

    if not additions:
        return existing

    prefix = (text.rstrip() + "\n\n") if text.strip() else ""
    return prefix + "\n".join(additions)


def backup_file(path: Path) -> Path | None:
    """Back up an existing config before writing. Returns None if nothing to back up."""
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, backup)
    _restrict_permissions(backup)
    return backup


def _restrict_permissions(path: Path) -> None:
    """Best-effort chmod 600 for files that may contain FEISHU_APP_SECRET."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(data, encoding="utf-8")
    _restrict_permissions(tmp)
    os.replace(tmp, path)
    _restrict_permissions(path)


def apply_claude_code_config(
    config_path: Path,
    *,
    feishu_app_id: str,
    feishu_app_secret: str,
    write_feishu: bool = True,
    write_banshan: bool = True,
) -> Path | None:
    existing: dict[str, Any] = load_claude_code_config(config_path)
    backup = backup_file(config_path)
    merged = merge_claude_code_config(
        existing,
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        write_feishu=write_feishu,
        write_banshan=write_banshan,
    )
    _atomic_write(config_path, json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    return backup


def apply_codex_config(
    config_path: Path,
    *,
    feishu_app_id: str,
    feishu_app_secret: str,
    write_feishu: bool = True,
    write_banshan: bool = True,
) -> Path | None:
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    backup = backup_file(config_path)
    _atomic_write(
        config_path,
        merge_codex_config(
            existing,
            feishu_app_id=feishu_app_id,
            feishu_app_secret=feishu_app_secret,
            write_feishu=write_feishu,
            write_banshan=write_banshan,
        ),
    )
    return backup


def detect_claude_code_config(home: Path) -> ClaudeCodeConfigChoice:
    """Resolve the Claude Code global config path, flagging ambiguity.

    New default is ~/.claude/.claude.json; a legacy cc-switch (<v3.16.4) may
    override the active path to ~/.claude.json. File existence cannot tell them
    apart when both exist, so that case is marked ambiguous for user confirmation.
    """
    new_path = home / ".claude" / ".claude.json"
    old_path = home / ".claude.json"
    existing = [p for p in (new_path, old_path) if p.exists()]

    if len(existing) >= 2:
        return ClaudeCodeConfigChoice(
            path=new_path,
            candidates=existing,
            ambiguous=True,
            note=(
                "同时检测到 `~/.claude/.claude.json` 与 `~/.claude.json`。"
                "装过旧版 cc-switch（<v3.16.4）时生效路径可能是 `~/.claude.json`，"
                "无法仅凭文件是否存在判断，请先确认再写入。"
            ),
        )
    if len(existing) == 1:
        return ClaudeCodeConfigChoice(
            path=existing[0], candidates=existing, ambiguous=False, note=""
        )
    return ClaudeCodeConfigChoice(
        path=new_path,
        candidates=[],
        ambiguous=False,
        note="未检测到现有配置，将新建默认路径 `~/.claude/.claude.json`。",
    )


def default_config_path(agent: str, home: Path | None = None) -> Path:
    home = home or Path.home()
    if agent == "claude-code":
        return detect_claude_code_config(home).path
    if agent == "codex":
        return home / ".codex" / "config.toml"
    raise ValueError(f"unsupported agent: {agent}")


def load_claude_code_config(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def analyze_claude_code_config(path: Path) -> tuple[bool, bool, bool]:
    config = load_claude_code_config(path)
    servers = config.get("mcpServers") or {}
    feishu = servers.get("feishu-docx-blocks") or {}
    banshan = servers.get("Banshan") or {}
    args = feishu.get("args") or []
    return (
        bool(feishu),
        "feishu-docx-blocks@latest" in args,
        banshan.get("url") == BANSHAN_MCP_URL,
    )


def _load_codex_toml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None


def analyze_codex_config(path: Path) -> tuple[bool, bool, bool]:
    data = _load_codex_toml(path)
    if data is None:
        # Malformed TOML — fall back to a conservative string scan.
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return (
            "[mcp_servers.feishu-docx-blocks]" in text,
            "feishu-docx-blocks@latest" in text,
            "[mcp_servers.banshan]" in text and BANSHAN_MCP_URL in text,
        )
    servers = data.get("mcp_servers") or {}
    feishu = servers.get("feishu-docx-blocks") or {}
    banshan = servers.get("banshan") or {}
    args = feishu.get("args") or []
    return (
        bool(feishu),
        "feishu-docx-blocks@latest" in args,
        banshan.get("url") == BANSHAN_MCP_URL,
    )


def read_claude_code_creds(path: Path) -> tuple[str | None, str | None]:
    config = load_claude_code_config(path)
    env = ((config.get("mcpServers") or {}).get("feishu-docx-blocks") or {}).get("env") or {}
    return env.get("FEISHU_APP_ID"), env.get("FEISHU_APP_SECRET")


def read_codex_creds(path: Path) -> tuple[str | None, str | None]:
    data = _load_codex_toml(path)
    if not data:
        return None, None
    env = ((data.get("mcp_servers") or {}).get("feishu-docx-blocks") or {}).get("env") or {}
    return env.get("FEISHU_APP_ID"), env.get("FEISHU_APP_SECRET")


def resolve_creds(
    agent: str, config_path: Path
) -> tuple[str | None, str | None, str]:
    """Prefer env vars, fall back to whatever the existing config already holds."""
    env_id = os.environ.get("FEISHU_APP_ID")
    env_secret = os.environ.get("FEISHU_APP_SECRET")
    if env_id or env_secret:
        return env_id, env_secret, "环境变量"
    if agent == "claude-code":
        cfg_id, cfg_secret = read_claude_code_creds(config_path)
    else:
        cfg_id, cfg_secret = read_codex_creds(config_path)
    if cfg_id or cfg_secret:
        return cfg_id, cfg_secret, "现有配置"
    return None, None, "未提供"


def build_diagnostic_report(
    *,
    agent: str,
    config_path: Path,
    uv_available: bool = True,
    python_version: str | None = None,
    feishu_configured: bool,
    feishu_uses_latest: bool,
    banshan_configured: bool,
    feishu_app_id: str | None,
    feishu_app_secret: str | None,
    cred_source: str = "未提供",
    config_ambiguous: bool = False,
    config_candidates: list[Path] | None = None,
    config_note: str = "",
) -> DiagnosticReport:
    return DiagnosticReport(
        agent=agent,
        config_path=config_path,
        uv_available=uv_available,
        python_version=python_version or sys.version.split()[0],
        feishu_configured=feishu_configured,
        feishu_uses_latest=feishu_uses_latest,
        banshan_configured=banshan_configured,
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        cred_source=cred_source,
        config_ambiguous=config_ambiguous,
        config_candidates=config_candidates or [],
        config_note=config_note,
    )


def env_or_prompt(name: str, *, secret: bool = False) -> str:
    value = os.environ.get(name)
    if value:
        return value
    if not sys.stdin.isatty():
        return ""
    prompt = f"{name}: "
    if secret:
        return getpass.getpass(prompt)
    return input(prompt)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose and optionally configure case-lite MCP dependencies.")
    parser.add_argument("--agent", choices=["claude-code", "codex"], required=True)
    parser.add_argument("--config", type=Path, default=None, help="Override global config path")
    parser.add_argument("--fix", action="store_true", help="Write config after user approval")
    parser.add_argument("--yes", action="store_true", help="Confirm --fix non-interactively")
    parser.add_argument(
        "--replace-feishu",
        action="store_true",
        help="Replace an existing feishu-docx-blocks entry (default: keep it)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable diagnostic report")
    return parser.parse_args(argv)


def _analyze(agent: str, config_path: Path) -> tuple[bool, bool, bool]:
    if agent == "claude-code":
        return analyze_claude_code_config(config_path)
    return analyze_codex_config(config_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    # Resolve config path, tracking ambiguity for Claude Code (F1).
    choice: ClaudeCodeConfigChoice | None = None
    if args.config:
        config_path = args.config
    elif args.agent == "claude-code":
        choice = detect_claude_code_config(Path.home())
        config_path = choice.path
    else:
        config_path = default_config_path(args.agent)

    feishu_configured, feishu_uses_latest, banshan_configured = _analyze(args.agent, config_path)
    feishu_app_id, feishu_app_secret, cred_source = resolve_creds(args.agent, config_path)

    report = build_diagnostic_report(
        agent=args.agent,
        config_path=config_path,
        feishu_configured=feishu_configured,
        feishu_uses_latest=feishu_uses_latest,
        banshan_configured=banshan_configured,
        uv_available=bool(shutil.which("uvx") or shutil.which("uv")),
        python_version=sys.version.split()[0],
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        cred_source=cred_source,
        config_ambiguous=bool(choice and choice.ambiguous),
        config_candidates=list(choice.candidates) if choice else [],
        config_note=choice.note if choice else "",
    )

    if args.json:
        payload = dataclasses.asdict(report)
        payload["config_path"] = str(report.config_path)
        payload["config_candidates"] = [str(p) for p in report.config_candidates]
        payload["feishu_app_secret"] = redact_secret(report.feishu_app_secret)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(report.to_markdown())

    if not args.fix:
        return 0

    # F1: never write to a guessed path when it is ambiguous.
    if choice and choice.ambiguous:
        print(f"\n⚠️ {choice.note}", file=sys.stderr)
        if args.yes:
            print(
                "已启用 --yes 但配置路径不确定；请用 --config 显式指定生效路径后重试。",
                file=sys.stderr,
            )
            return 3
        for idx, cand in enumerate(choice.candidates, 1):
            print(f"  {idx}) {cand}")
        selection = input("请选择生效的配置文件序号（回车取消）: ").strip()
        if not selection.isdigit() or not (1 <= int(selection) <= len(choice.candidates)):
            print("已取消。确认路径后可用 --config 指定。")
            return 0
        config_path = choice.candidates[int(selection) - 1]
        feishu_configured, feishu_uses_latest, banshan_configured = _analyze(
            args.agent, config_path
        )
        feishu_app_id, feishu_app_secret, cred_source = resolve_creds(args.agent, config_path)

    # F2: decide what to write; keep an existing feishu-docx-blocks by default.
    write_feishu = (not feishu_configured) or args.replace_feishu
    write_banshan = not banshan_configured

    if feishu_configured and not write_feishu and not args.yes:
        hint = "非 @latest，建议升级" if not feishu_uses_latest else "已是 @latest"
        answer = input(
            f"检测到已存在 feishu-docx-blocks（{hint}）。是否用推荐配置替换？输入 yes 替换，回车保留: "
        ).strip()
        if answer == "yes":
            write_feishu = True

    if not write_feishu and not write_banshan:
        print("现有配置已满足要求，无需修改。")
        return 0

    kept = []
    if feishu_configured and not write_feishu:
        kept.append("feishu-docx-blocks（保留现有）")
    if banshan_configured and not write_banshan:
        kept.append("Banshan（保留现有）")
    to_write = []
    if write_feishu:
        to_write.append("feishu-docx-blocks（新增/替换）")
    if write_banshan:
        to_write.append("Banshan（新增）")

    print("\n将写入：" + ("、".join(to_write) if to_write else "（无）"))
    if kept:
        print("将保留：" + "、".join(kept))
    if args.agent == "claude-code":
        print("提示：写入前请退出 Claude Code，避免运行中并发写回覆盖本次修改。")

    if not args.yes:
        answer = input(f"确认写入全局 MCP 配置 `{config_path}`？输入 yes 继续: ").strip()
        if answer != "yes":
            print("已取消写入。")
            return 0

    if write_feishu:
        feishu_app_id = feishu_app_id or env_or_prompt("FEISHU_APP_ID")
        feishu_app_secret = feishu_app_secret or env_or_prompt("FEISHU_APP_SECRET", secret=True)
        if not feishu_app_id or not feishu_app_secret:
            print(
                f"缺少 FEISHU_APP_ID / FEISHU_APP_SECRET，请从内部文档获取：{FEISHU_INTERNAL_DOC_URL}",
                file=sys.stderr,
            )
            return 2
    else:
        feishu_app_id = feishu_app_secret = ""

    if args.agent == "claude-code":
        backup = apply_claude_code_config(
            config_path,
            feishu_app_id=feishu_app_id,
            feishu_app_secret=feishu_app_secret,
            write_feishu=write_feishu,
            write_banshan=write_banshan,
        )
    else:
        backup = apply_codex_config(
            config_path,
            feishu_app_id=feishu_app_id,
            feishu_app_secret=feishu_app_secret,
            write_feishu=write_feishu,
            write_banshan=write_banshan,
        )

    if backup:
        print(f"已写入 MCP 配置。备份文件（含明文 secret，注意妥善保管/清理）: {backup}")
    else:
        print("已写入 MCP 配置（原文件不存在，已新建，无需备份）。")
    print("请重启 Agent / MCP 会话后再使用 case-lite。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
