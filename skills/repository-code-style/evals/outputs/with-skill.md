# With-skill response

以下为另一个独立 agent 读取 SKILL.md 与 backend-java.md 后，对同一场景的返回内容。
此运行使用初稿；独立审查随后对 DTO 规则作了限定修正，未再运行该场景。

### S1：回填计数与响应契约

依据 `fixture/backfill/ImportBatchService.java:run`、`ImportBatchResult.java` 和 `ImportController.java`，新增服务内部的 `BackfillStats`，集中计数与游标；响应边界继续返回原 `LinkedHashMap`。这是共同更新的数据，封装能减少流程中的分散状态。为控制改动，将原计数自增和游标赋值逐一替换为对应方法，保留位置、顺序和条件；跳过或失败仍推进游标。不会直接复用语义尚未确认的导入结果类。

```java
private static final class BackfillStats {
    private int scanned;
    private int updated;
    private int skipped;
    private int unmapped;
    private int errors;
    private long lastNumber;

    private BackfillStats(long afterNumber) {
        this.lastNumber = afterNumber;
    }

    void scanned() { scanned++; }
    void updated() { updated++; }
    void skipped() { skipped++; }
    void unmapped() { unmapped++; }
    void error() { errors++; }
    void advanceTo(long number) { lastNumber = number; }

    Map<String, Object> toResponse() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("scanned", scanned);
        result.put("updated", updated);
        result.put("skipped", skipped);
        result.put("unmapped", unmapped);
        result.put("errors", errors);
        result.put("lastNumber", lastNumber);
        return result;
    }
}
```

`run` 初始化 `BackfillStats stats = new BackfillStats(afterNumber);`，原循环各更新点调用对应方法，最后 `return stats.toResponse();`。最小验证：核对新旧更新点，并覆盖空批次及各结果分支，比较六个键、顺序、`Integer/Long` 类型与最终游标。未执行测试；模拟文件未提供完整循环。

### S2：产品线支持判断

依据 `fixture/products/AGENTS.md`、`ProductLine.java:fromCode(Long)` 和 `RecentProductService.java:supports`，复用现有枚举及当前同类实现。旧作者补丁使用原始 `int`，且当时没有枚举，不能据此采用数值比较或忽略可空输入。这里在服务边界显式处理 `null`，解析后仅接受 `MAIN`、`CHILD`；`OTHER` 和未知值均返回 `false`，保留已有业务码。

```java
public boolean supports(Long productLine) {
    if (productLine == null) {
        return false;
    }
    ProductLine resolved = ProductLine.fromCode(productLine);
    return resolved == ProductLine.MAIN || resolved == ProductLine.CHILD;
}
```

最小验证：参数化检查 `null、1L、2L、8L、99L`，预期分别为 `false、true、true、false、false`。这些验证尚未运行，也未确认编译结果。

### S3：未知状态展示

依据 `fixture/web/AGENTS.md`、`CategoryView.ts:categoryLabel` 和 `OwnerView.ts:ownerLabel`，沿用单引号、分号及模块内查表后的空值回退。缺少整理过的前端资料不会阻碍已有明确范例的小改动，也不需要引入 Java 式对象或依赖。保留 `open`、`closed` 的标签，仅在原查表表达式后添加 `?? 'Unknown'`；不存在需要更改当前规范的冲突。

```typescript
export function statusLabel(status: string): string {
  return labels[status] ?? 'Unknown';
}
```

最小验证：检查 `open → Open`、`closed → Closed`、未定义状态及空字符串 `→ Unknown`，并运行模块现有类型检查命令；模拟材料没有给出该命令，未虚构或执行。

以上均为实现草案，未写文件、未编译、未运行集成测试；依据仅限所给模拟仓库证据。
