# Contributing

感谢贡献。这个仓库的基本交付单元是一个可以独立安装的 Skill。

## 新增或修改 Skill

1. 在 `skills/<skill-name>/` 下维护一个完整 Skill。
2. `SKILL.md` 必须包含 `name`、`version` 和清晰的触发条件。
3. 目录名必须与 frontmatter 中的 `name` 一致，名称使用小写和连字符。
4. 同步更新 `CHANGELOG.md` 和根 README 的总览表。
5. 长规则放入 `references/`，可执行逻辑放入 `scripts/`，并保留必要的相对链接。
6. 增加或更新能证明行为的测试、示例或评估资料。

## 提交前检查

```bash
python -m unittest discover -s tests
git diff --check
```

不要提交账号、Cookie、token、内部日志、真实用户对话或未脱敏的服务地址。对外部
系统有副作用的脚本应有明确的确认步骤，并在 README 中说明依赖和风险。
