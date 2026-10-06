# Code Changes Adapter

Use for implementation, refactoring, bug fixes, compatibility work, and tests.

- Map user behavior to entry point, state/data flow, changed modules, and tests.
- Compare the closest existing implementation on the same input; preserve callers and
  local conventions unless an intentional contract change is recorded.
- Check API compatibility, persistence, permissions, retries, concurrency, migrations,
  feature flags, rollback, and failure paths when applicable.
- Validate at the narrowest meaningful level first, then exercise the changed boundary and
  consumer path. Inspect the final diff and run `git diff --check` when supported.
- Do not treat a passing unit test as proof that serialization, deployment configuration,
  or user-visible behavior is correct.
