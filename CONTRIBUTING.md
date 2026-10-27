# Contributing

感谢贡献。这个仓库的基本交付单元是一个可以独立安装的 Skill。

## 新增或修改 Skill

1. 在 `skills/<skill-name>/` 下维护一个完整 Skill。
2. `SKILL.md` 必须包含 `name`、`version` 和清晰的触发条件。
3. 目录名必须与 frontmatter 中的 `name` 一致，名称使用小写和连字符。
4. 同步更新 `CHANGELOG.md` 和根 README 的总览表。
5. 长规则放入 `references/`，可执行逻辑放入 `scripts/`，并保留必要的相对链接。
6. 单元测试放在 `tests/<skill-name>/`，评估清单、合成夹具、预期及验证记录放在
   `evals/<skill-name>/`，维护 skill 本身的指南放在 `docs/maintainers/`。
7. `skills/<skill-name>/` 只保留执行任务必需的入口、参考、脚本、资源和实际使用的
   示例，必须能单独复制安装。不要把单元测试、评估量具、合成业务源码或缓存放进运行包。
8. 运行包内的相对链接和依赖保持在该包内。README 可用仓库级路径说明开发资料位置，
   但不得让安装后的执行流程依赖这些目录。评估 `files` 相对于对应 `evals.json` 目录。
9. 调整结构时保留现有测试语义，修正源文件定位与检查命令；合成样本不能用于证明
   真实业务规范。运行必需的示例/模板按实际消费者判断，不能只按文件名或扩展名迁走。

## 提交前检查

```bash
python tools/run_tests.py
git diff --check
```

开发检查要求 Python 3.11+，与 CI 一致。统一入口为各组测试创建独立进程并禁止生成
字节码缓存；不要把仓库级测试通过描述为真实模型评估或业务环境验证通过。

不要提交账号、Cookie、token、内部日志、真实用户对话或未脱敏的服务地址。对外部
系统有副作用的脚本应有明确的确认步骤，并在 README 中说明依赖和风险。
