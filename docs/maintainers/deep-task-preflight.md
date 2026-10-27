# Adapter Template

This is a source-repository maintenance template, not an installed runtime asset.
Add domain adapters under `skills/deep-task-preflight/references/adapters/` when
a recurring task family needs specialized checks. Keep the core Skill unchanged
unless the rule applies to nearly every task.

Each adapter should state:

1. when to read it;
2. representative inputs and the reference implementation or contract;
3. boundary checks and consumer read-back;
4. failure, rollback, and ambiguity cases;
5. evidence required to close the universal verification ladder.
