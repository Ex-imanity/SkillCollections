# Without-skill response

以下为独立 agent 对三个合成场景的返回内容。没有读取本 skill 或使用 skill 后的结果。

## S1：批量回填结果

沿用 `ImportBatchService.run` 和 `ImportBatchResult` 的局部模式：计数及游标放进结果对象，响应键只在 `toResponse()` 中出现。时间紧的要求通过小对象实现；保持循环原有分支及计数位置，每行处理后推进游标，跳过或失败也不遗漏。

```java
final class BackfillResult {
    private int scanned;
    private int updated;
    private int skipped;
    private int unmapped;
    private int errors;
    private long lastNumber;

    BackfillResult(long afterNumber) {
        lastNumber = afterNumber;
    }

    void recordScanned() { scanned++; }
    void recordUpdated() { updated++; }
    void recordSkipped() { skipped++; }
    void recordUnmapped() { unmapped++; }
    void recordError() { errors++; }
    void advanceCursor(long number) { lastNumber = number; }

    Map<String, Object> toResponse() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("scanned", scanned);
        response.put("updated", updated);
        response.put("skipped", skipped);
        response.put("unmapped", unmapped);
        response.put("errors", errors);
        response.put("lastNumber", lastNumber);
        return response;
    }
}
```

`run` 初始化 `BackfillResult result = new BackfillResult(afterNumber)`；将原来的各处自增及游标赋值分别替换成对应方法，最后 `return result.toResponse()`。不根据示例猜测 outcome 是否互斥，也不移动原计数位置。

最小验证：空批次保留 `afterNumber`；覆盖更新、跳过、未映射、失败，逐项比较变更前后的六个响应值与键顺序，并确认末行失败仍推进游标。

## S2：支持的产品线

```java
public boolean supports(Long productLine) {
    ProductLine resolved = ProductLine.fromCode(productLine);
    return resolved == ProductLine.MAIN
            || resolved == ProductLine.CHILD;
}
```

选择当前 `fixture/products/AGENTS.md`、`ProductLine.fromCode` 和 `RecentProductService.supports`：三者共同提供明确的现行模式，转换方法已覆盖空值。旧作者的实现使用 primitive `int`，且当时没有枚举，因此不适合直接复制到 nullable `Long` 场景。用命名枚举常量表达支持范围，也避免拆箱空指针和散落的数字。

最小验证：`null`、`1L`、`2L`、`8L`、未知值如 `99L` 分别得到 `false`、`true`、`true`、`false`、`false`。

## S3：未知状态标签

```typescript
const labels: Record<string, string> = {
  open: 'Open',
  closed: 'Closed',
};

export function statusLabel(status: string): string {
  return labels[status] ?? 'Unknown';
}
```

选择该模块的 `AGENTS.md` 与 `CategoryView.categoryLabel`、`OwnerView.ownerLabel` 的一致表达式，保留单引号、分号和原标签。没有证据冲突；缺少整理过的前端规范不影响依据现有相邻实现完成这一行修改，也无需引入依赖或推断全公司规范。

最小验证：`open`、`closed` 仍返回原标签；普通未定义状态如 `pending` 和空字符串返回 `Unknown`。

以上仅为基于模拟证据的实现草案，未写文件，也未执行编译或集成测试。
