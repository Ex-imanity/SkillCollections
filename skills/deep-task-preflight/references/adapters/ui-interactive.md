# UI and Interactive Behavior Adapter

Use for web, mobile, desktop, review consoles, and any workflow with visible state.

- Treat the existing UI path as the reference for state, rendering, navigation, and
  loading/empty/error behavior unless the requirement intentionally changes it.
- Exercise the changed flow in the supported browser/device/UI harness at relevant viewport
  sizes. Inspect the rendered result, not just DOM or API output.
- After a write, perform write → read back → display through the same read path used by the
  page. Verify labels, counts, filters, navigation, detail views, and persistence update
  together.
- Cover success, partial, empty, error, retry, refresh, and stale-state behavior that the
  user can encounter. Record request, response, read-back source, and rendered evidence
  separately.
