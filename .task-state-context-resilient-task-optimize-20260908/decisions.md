# Decisions

## 2026-09-08: Bounded context replay
- **Decision:** Recovery and pre-compaction output must include bounded latest entries from decisions, findings and utils; never load append-only histories wholesale.
- **Reason:** Real MRS logs reach 757 findings lines and 1102 progress lines, while the old digest only carried task_state fields.
- **Source:** `/Users/gaotu/Projects/qa-ai-search/.task-state/findings.md`, `/Users/gaotu/Projects/FeedbackEntrance/.task-state-ai-search-existing-service/progress.md`, previous `precompact_digest.py`.

## 2026-09-08: Utilities are a separate context class
- **Decision:** New MRS creates `utils.md` for stable tooling, environment, database/server/logging and local resource pointers; legacy MRS stays compatible with a warning.
- **Reason:** Real projects keep these pointers in architecture, findings, task state and custom documents, where they are easy to confuse with conclusions or deliverables.
- **Source:** `/Users/gaotu/Projects/qa-ai-search/.task-state/snapshot.md`, `/Users/gaotu/Projects/FeedbackProgress/.task-state-feedback-category-optimization/architecture.md`.

## 2026-09-08: Pinned invariants and bounded multi-MRS output
- **Decision:** `## Invariants (pinned)` is restored before recency-limited entries; multi-MRS recovery and precompact output are capped at 4000 characters and detail only the newest MRS.
- **Reason:** Long-lived constraints must survive beyond the newest-N window, while several active MRS histories otherwise overwhelm compaction context.
- **Source:** `Review/ByClaudeCode/2026-09-08-context-resilient-task-optimization-review.md` P0-1/P1-3.
