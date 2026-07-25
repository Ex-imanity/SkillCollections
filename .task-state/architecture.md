# P1 Safety Architecture

## Scope

Harden the bundled `cross-agent-review` adapters without changing their
reviewer roles, read-only permissions, or output format.

## Marker State

Each `artifact_key` stores two durable counters in the shared marker file:

- `attempts`: a review invocation that has crossed the subprocess boundary.
- `successes`: a verified, persisted reviewer result.

Both counters have a fixed maximum of two. This preserves one review plus one
re-review while ensuring a timeout or provider failure cannot be retried
without bound after it may have incurred cost.

## Compatibility

Legacy marker entries that are non-negative integers are read as matching
`attempts` and `successes` counts. New writes use the structured state.

## Boundaries

- The Codex to ClaudeCode adapter retains the provider's `--max-budget-usd`
  option and requires an explicit user-approved value at the CLI boundary.
- The ClaudeCode to Codex adapter has no provider-supported USD cap; its
  documentation must say that clearly and rely on the fixed attempt cap,
  timeout, and explicit user approval.
- The primary remains responsible for the final acceptance of review findings.
