# Findings

<!-- Append research notes and discoveries below this line. -->

## 2026-09-08: Real MRS inventory
- Found 15 MRS directories under `/Users/gaotu/Projects` across qa-ai-search, FeedbackEntrance, FeedbackProgress, PlaywriteTest, Chats2Obsidian, play-book and testCases.
- Real MRS use custom stable-context files such as `evidence-index.md`, `test-observability.md`, `open_questions.md`, meeting reconciliation and technical recommendations; these do not fit the old fixed artifact list.
- `/Users/gaotu/Projects/testCases/.task-state-ai-search-multi-agent/task_state.md` contains four authoritative todo-section headings, despite the documented exactly-two rule.
- `/Users/gaotu/Projects/qa-ai-search/.task-state` contains 757 lines in `findings.md`, 661 lines in `decisions.md`, and 523 lines in `progress.md`; `/Users/gaotu/Projects/FeedbackEntrance/.task-state-ai-search-existing-service/progress.md` contains 1102 lines.

## 2026-09-08: ClaudeCode review
- Verdict: `REQUEST CHANGES`; reviewer session `c8ba2dca-e8f7-4096-9f1b-53ae3c71498a`, reported cost `$3.683073`, wall time `747.166s`.
- P0 findings: no global precompact budget across multiple MRS; duplicate todo validation misses suffixed sections such as `Completed Items（第一轮）`; untitled append-only files replay the oldest head rather than the newest tail.
- P1 findings: snapshot embedded headings remain top-level `##`; multi-MRS recovery omits new context; recency-only replay lacks pinned invariants; utils sensitivity/retention/ownership schema is incomplete; two reference docs have misplaced decision bullets; truncation lacks source pointers; Tier-1 drift is not detected.
- Positive evidence: bounded replay did recover the latest 2026-09-04 decisions in `qa-ai-search`, so the direction is useful; it needs budget, pinning and real-shape fixtures before promotion.
