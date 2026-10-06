# Debugging and Incident Analysis Adapter

Use when the cause is uncertain or evidence may be lost across layers.

- Record expected behavior, actual behavior, environment/revision/time window, exact
  evidence, and the hypothesis being tested.
- Rank hypotheses by evidence and falsifiability. Distinguish confirmed cause, contributing
  factor, workaround, and unverified possibility.
- Trace source data, normalization, transport, persistence, cache, and rendering in order;
  inspect the observed user/data result before naming the first failing layer.
- Do not call an empty log query, timeout, or HTTP 200 a root cause by itself. Verify the
  full flow and include partial success, retries, idempotency, and stale data where relevant.
- Close with a reproducible signal or state exactly why the remaining cause is unverified.
