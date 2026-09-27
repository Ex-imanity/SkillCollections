# 1.0.2 targeted regression response

独立 agent 读取修正版 skill 后，在一次性 Git 仓库中对随包 discovery fixture
执行 S4-S6；没有读取 eval 期望或其他运行结果。下面保留返回的草案及判断。

已读取技能 `repository-code-style/SKILL.md`、`references/backend-java.md`，并检查 fixture。
`git ls-files` 确认 `.cursorrules`、`README.md`、`docs/wire-contract.md`、两个 Java 文件
均已跟踪；`git status` 显示它们已暂存。分支为 master，尚无提交，HEAD 不存在。
未编辑文件。

## S4

增加 `import java.util.Objects;`：

```java
public boolean shouldHandle(String value) {
    return Objects.nonNull(value);
}
```

依据：README 的 S4；`.cursorrules:3-5` 要求新改代码使用 Objects 判断空值。
`src/TaskService.java:7-9` 的旧方法使用 `!= null`，但显式规范优先，保留旧方法。

最小验证建议：null 返回 false，空字符串、普通字符串返回 true。

## S5

```java
public int pageType() {
    return PageType.LEGACY_HOME_PANEL.getCode();
}
```

依据：`src/TaskService.java:15-17` 原值为 17；`src/PageType.java:4-5` 明确
LEGACY_HOME_PANEL(17)，而 HOMEPAGE_COLUMN_FEED(14)。按已有数值映射选枚举，
历史名称不能覆盖兼容性要求。

最小验证建议：断言返回值仍为 17。

## S6

```java
public Map<String, Object> response(int count, long lastNumber) {
    return new ResponseStats(count, lastNumber).toResult();
}

private static final class ResponseStats {
    private final int count;
    private final long lastNumber;

    private ResponseStats(int count, long lastNumber) {
        this.count = count;
        this.lastNumber = lastNumber;
    }

    private Map<String, Object> toResult() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("count", count);
        result.put("lastNumber", lastNumber);
        return result;
    }
}
```

依据：`src/TaskService.java:19-23` 的字段命名、类型和边界转换；
`docs/wire-contract.md:9-17` 明确 bean 的 long/Long 会转字符串，而 Map 数值保留
JSON number。采用内部对象和边界 Map，保持公开返回类型、字段键、插入顺序及
数值类型；不新增序列化配置。当前对象只传递稳定结果，无更新流程，不需额外计数 API。

最小验证建议：检查 Map 键顺序为 count,lastNumber，值分别为 Integer、Long；
通过真实 API 序列化器确认 response(2,123L) 输出 `{"count":2,"lastNumber":123}`。

以上仅为草案与验证建议；没有执行编译、测试或序列化验证。
