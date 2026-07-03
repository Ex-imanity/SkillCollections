<!-- OVERWRITE THIS FILE on each update. Do NOT append new sections. Archive previous version first with: python <skill-root>/scripts/generate_snapshot.py --archive . -->
# Snapshot: 2026-07-01 21:10

## Context
Phase 6.1：对 codex 的 Phase 6（首次使用依赖安装 + MCP 自动配置）做 review 复核，并按用户指示修复 F1–F5，在 MRS 留痕后交 codex 复核。Goal 不变：优化 case-lite skill 的用例生成质量与首次使用体验。

## Recent Progress
- Review 结论：方向正确、无安全红线；配置内容已对照飞书 `安装` 章节核对忠实；全仓库 grep 确认无真实 secret 泄漏（公开仓库）。
- 已修复 F1–F5（详见 findings.md 2026-07-01 review 表）：
  - F1 Claude Code 路径歧义：两路径同存不再静默猜测，报告列候选 + `--config`，`--fix --yes` 拒写(exit 3)
  - F2 no-clobber：默认仅写缺失 server，已有 feishu 需 `--replace-feishu` 才替换
  - F3 写入加固：原子写 + chmod 0o600 + 退出 CC 提示 + `claude mcp add-json` 文档
  - F4 凭证来源：优先 env，其次现有配置，消除误报
  - F5 覆盖：tomllib 读 Codex、补路径/凭证/no-clobber 测试、修弱断言、补连通性说明
- F6 按用户决定维持现状（公开仓库不内嵌凭证）。

## Current Focus
交 codex 复核。改动文件：`case-lite/scripts/setup_mcp.py`、`tests/test_setup_mcp.py`、`tests/test_skill_contract.py`、`SKILL.md`、`references/install-mcp.md`。

## Blockers
- (None)

## Files Modified
- case-lite/scripts/setup_mcp.py（重写：歧义检测 / 选择性 merge / 原子写 / 凭证解析）
- case-lite/tests/test_setup_mcp.py（重写：路径/凭证/no-clobber/报告 21 用例）
- case-lite/tests/test_skill_contract.py（新增安全写入契约断言）
- case-lite/SKILL.md（向导段落补路径确认/不覆盖/退出 CC）
- case-lite/references/install-mcp.md（路径歧义、--replace-feishu、CLI、连通性、Checklist）

## Next Session Should Know
- Next action: 交 codex 复核；复核重点见 findings.md 末尾三条（TOML 写侧字符串裁剪边角、选路后凭证一致性、是否需“只刷新 env 凭证”选项）。
- 验证：`python -m unittest discover -s case-lite/tests` 全绿；/tmp 烟测确认 no-clobber 与 ambiguity 拒写；未触碰真实全局配置。
