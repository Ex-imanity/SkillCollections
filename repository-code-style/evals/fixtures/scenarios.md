# Style decision scenarios

These are synthetic, self-contained repository excerpts. They are not copied
from Gaotu source and cannot establish a Gaotu repository convention.
Source locators below are fixture locators, not paths in an actual checkout.
For this exercise, return a concrete patch sketch and its reasoning; do not
edit a business repository or claim compilation/integration testing.

## S1: Backfill counters and a stable wire contract

Task: Complete a Java batch backfill result, including scanned, updated,
skipped, unmapped, errors, and lastNumber. Keep the response JSON keys and the
counting behavior. Time is short; keep the change small.

Target `fixture/backfill/BackfillService.java:run`:

```java
int scanned = 0;
int updated = 0;
int skipped = 0;
int unmapped = 0;
int errors = 0;
long lastNumber = afterNumber;
// The loop increments these counters and advances lastNumber.
Map<String, Object> result = new LinkedHashMap<>();
result.put("scanned", scanned);
result.put("updated", updated);
result.put("skipped", skipped);
result.put("unmapped", unmapped);
result.put("errors", errors);
result.put("lastNumber", lastNumber);
return result;
```

Available local exemplars:

- `fixture/backfill/ImportBatchService.java:run`: uses an `ImportBatchResult`
  object for counters and cursor; a boundary method `toResponse()` builds a
  `LinkedHashMap` with the existing wire keys. Each processed row advances the
  cursor, including rows whose business outcome is skipped or failed.
- `fixture/backfill/ImportBatchResult.java`: contains named fields and small
  outcome methods, not a generic map keyed by strings or a state machine.
- `fixture/backfill/ImportController.java`: returns the service map unchanged;
  no new serializer configuration is needed.

## S2: A recent local pattern and an older author's pattern

Task: Add a check for supported product lines in a service. Input is nullable
`Long`; only 1 and 2 are supported. Unsupported input should return false.

Target `fixture/products/ProductService.java:supports(Long productLine)` is
currently missing.

Available evidence:

- `fixture/products/AGENTS.md`: use existing `ProductLine` enum for supported
  product identifiers; keep nullable-input handling at the service boundary.
- `fixture/products/ProductLine.java:fromCode(Long)`: returns the matching
  enum or null, including for a null argument; `MAIN(1L)`, `CHILD(2L)`, and
  `OTHER(8L)` exist.
- `fixture/products/RecentProductService.java:supports`: resolves the enum and
  checks `MAIN` or `CHILD`, with named enum constants.
- `fixture/history/leader-2019.patch`: a favored author's older implementation
  checks `code == 1 || code == 2`; its input is primitive int and there was no
  enum at that revision.

## S3: A frontend module without a curated domain profile

Task: Add a display label for unknown status in a TypeScript view. Preserve the
existing labels. The team will provide frontend conventions later.

Target `fixture/web/StatusView.ts`:

```typescript
const labels: Record<string, string> = {
  open: 'Open',
  closed: 'Closed',
};
export function statusLabel(status: string): string {
  return labels[status];
}
```

Available local exemplars:

- `fixture/web/AGENTS.md`: single quotes, semicolons, small module-local helpers;
  no new dependencies for display fallbacks.
- `fixture/web/CategoryView.ts:categoryLabel`: returns a lookup value with
  `?? 'Unknown'`.
- `fixture/web/OwnerView.ts:ownerLabel`: uses the same fallback expression.

No curated frontend profile or Gaotu frontend-author evidence is available.

## Evaluation request

For each scenario, give the concrete implementation sketch, the evidence you
selected, any conflict you resolved, and the smallest useful verification.
Keep changes within the task. Do not invent missing repo files or conventions.
