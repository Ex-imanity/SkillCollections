# Codex Primary + ClaudeCode Review Loop

Status: historical validated checklist. Its 2026-06-14 first-use evidence is provenance; the containing `cross-agent-review` skill has its own installed-version validation state.

This is a collaboration protocol for tasks where Codex should preserve continuity and do the main writing/implementation, while ClaudeCode should act as a source-grounded reviewer and risk finder.

## When To Use

Use this workflow when:

- A task spans multiple sessions, multiple agents, or multiple repos.
- Codex has the richest continuity through the active thread, MRS, branch, and recent implementation context.
- ClaudeCode can add value through source-path review, subagent fan-out, independent risk discovery, or evidence verification.
- The expected output needs review closure, not just a quick answer.

Do not use this workflow when:

- The task is a small local edit with low risk.
- No durable review artifact is needed.
- ClaudeCode cannot access the required repo/files and no alternative evidence path is available.
- The user asks for an immediate answer rather than a reviewed artifact.

## Roles

Current mapping: Codex is the primary continuity owner and ClaudeCode is the reviewer/risk-finder. If a future task has a different continuity owner, keep the functional split and update the agent mapping explicitly.

### Primary / Continuity Owner

The primary agent owns:

- MRS recovery and updates.
- Reading the project rules and relevant skills.
- Producing the plan, implementation, retrospective, workflow, or checklist.
- Keeping source citations attached to claims.
- Applying review findings.
- Writing review closure notes and updating `.task-state/`.

### Reviewer / Risk-Finder

The reviewer owns:

- Reviewing the produced artifact without directly editing it.
- Verifying citations, source paths, file/repo reach, evidence strength, and missing risks.
- Using subagents when the review naturally decomposes by repo, layer, or concern.
- Returning findings under `Review/ByClaudeCode/` with severity and concrete source paths.

The reviewer is not the primary continuity owner in this workflow. It should challenge, verify, and supplement; it should not silently replace the primary agent's MRS state or rewrite the artifact outside the agreed handoff.

## Required Inputs

- Active MRS files under `.task-state/`.
- The artifact to review, such as a plan, implementation summary, retrospective, workflow, checklist, or skill.
- Source evidence that supports the artifact:
  - raw Codex session locators
  - raw ClaudeCode session or subagent locators
  - project docs/plans/reviews
  - code paths, commits, tests, runbooks, inventories
- Evidence classification for any missing raw sessions:
  - if raw ClaudeCode sessions are absent after a live-store scan, mark them `verified-absent`, not merely "not found"
  - if a project-local `Review/ByClaudeCode/*.md` exists without a raw transcript, treat it as artifact evidence, not raw-session evidence
  - do not upgrade text mentions, review documents, or exported notes into transcript evidence
- A target review output path under `Review/ByClaudeCode/`.
- Explicit review questions.

For raw-session reading, use `/Users/gaotu/Projects/play-book/docs/reference/session-reading.md`. For evidence layering and artifact-only review handling, follow the Evidence Rules in `/Users/gaotu/Projects/play-book/docs/templates/evidence-indexed-retrospective.md`.

## Workflow

### 1. Codex Reconstructs State

Codex reads:

- project `AGENTS.md`
- `.task-state/task_state.md`
- `.task-state/progress.md`
- `.task-state/decisions.md`
- `.task-state/snapshot.md`
- relevant plans, retrospectives, workflows, or skills

Output: a clear current phase, known gaps, and the concrete artifact to produce.

### 2. Codex Produces The Primary Artifact

Codex writes or updates the primary artifact using the appropriate workflow:

- code implementation
- implementation plan
- project retrospective
- workflow/checklist
- skill or skill optimization

The artifact must name its evidence basis and boundary. If an implementation is incomplete, use explicit completion vocabulary instead of smoothing it into a finished story.

### 3. Codex Prepares Review Handoff

Create a review request under `Review/ForClaudeCode/`.

The request should include:

- review objective
- exact files to read
- source evidence to sample
- review questions
- expected output path
- instruction not to directly edit the reviewed artifact
- known limitations, such as verified-absent raw sessions, pruned sessions, artifact-only reviews, or repo access uncertainty

For multi-repo work, include the repo paths explicitly. If review needs subagents, suggest a partition:

- one reviewer per repo or owner
- one cross-service consistency critic
- one plan-vs-implementation reviewer when both plan and code exist

### 4. ClaudeCode Reviews With Source Paths

ClaudeCode writes review output under `Review/ByClaudeCode/`.

Expected review shape:

- Verdict: `APPROVE`, `APPROVE WITH NITS`, `REQUEST CHANGES`, or `BLOCKED`.
- Findings ordered by severity, such as P0/P1/P2/P3.
- Each finding cites exact paths, raw-session locators, file lines, commits, or command output.
- Explicit answers to the review questions.
- Recommendation for next step.

If ClaudeCode cannot access a target repo or raw session, it must mark the review area blocked or evidence-limited. If raw ClaudeCode sessions are verified absent but project-local review files exist, it must label those files as artifact evidence, not transcript evidence. It must not infer findings from memory.

### 4.5 Wait For A Final Gate Result

`review_started` is not a completed review and is not permission to inspect
the output path for closure. A terminal host may stream that stderr event while
the reviewer subprocess is still running. Keep the original command/session
(or its recorded PID) under observation until the parent command returns final
stdout JSON and an exit status, or its configured timeout actually expires.
While only the start event is available, report `in_progress`; do not spend a
retry, update MRS closure, or label the gate failed/successful.

### 5. Codex Applies Or Pushes Back

Codex processes the review:

1. Fix blockers and valid P1/P2 issues first.
2. Push back only with evidence, tests, or direct source citations.
3. Leave optional polish for later when it does not affect the current gate.
4. Update the reviewed artifact.
5. Add review closure notes that map findings to changes.

### 6. Codex Updates MRS

Codex updates:

- `.task-state/task_state.md` in place
- `.task-state/progress.md` append-only
- `.task-state/decisions.md` for stable decisions
- `.task-state/snapshot.md` by regeneration with archive

The next action should be one concrete step: continue, first-use, ask user, or wait for another review.

## Review Request Checklist

Before handing off to ClaudeCode, confirm:

- The review request names the exact artifact under review.
- The expected review output path is under `Review/ByClaudeCode/`.
- The request includes evidence sources, not just a prose summary.
- Multi-repo paths are absolute and readable from the review context, or the limitation is stated.
- Raw-session gaps are classified as pruned, verified-absent, artifact-only, or unknown.
- The request asks about overgeneralization, missing risks, and evidence strength.
- The request asks ClaudeCode not to edit the reviewed artifact directly.

## Review Closure Checklist

Before claiming the loop is complete, confirm:

- The ClaudeCode review file exists.
- The verdict and all blocker/P1 findings have been addressed or explicitly rejected with evidence.
- The reviewed artifact includes review closure notes or the MRS records the closure.
- MRS verification passes.
- Any remaining candidate/promotion decision is explicit.

## Stop Conditions

Stop and ask the user or record a blocker when:

- ClaudeCode review requires access to a repo that is not readable from its context.
- Raw sessions are claimed but cannot be resolved to source paths.
- Raw ClaudeCode sessions are absent but review documents are being treated as raw transcript evidence.
- The review output is only generic advice and contains no source-path findings.
- The artifact would be promoted from candidate to installed skill without first-use or review evidence.
- Codex and ClaudeCode disagree on a material fact and neither side can cite stronger evidence.

## Failure Modes

| Failure | Symptom | Guardrail |
|---|---|---|
| Review theater | Review says "looks good" without source paths. | Require exact findings, sampled citations, and explicit unanswered questions. |
| Wrong repo proof | A docs repo commit is cited as proof of app-code behavior. | Cite the implementation repo or mark the cross-repo gap. |
| Artifact evidence inflated to transcript evidence | Project-local `Review/ByClaudeCode/*.md` exists but raw ClaudeCode sessions are absent. | Label raw sessions as verified-absent after live-store scan; cite review files as artifact evidence only. |
| Subagent reach failure | Reviewer says a repo is inaccessible but the main artifact treats review as complete. | Record the limitation and rerun from a parent workspace or pass accessible repo paths. |
| Over-promotion | Candidate workflow is installed as a skill after one example. | Require review plus first-use before promotion. |
| Closure drift | Review findings are fixed but not traceable later. | Add review closure notes and MRS progress entries. |

## Evidence Basis

Primary extraction source:

- `/Users/gaotu/Projects/play-book/docs/retrospectives/FeedbackEntrance.md`
- `/Users/gaotu/Projects/play-book/Review/ByClaudeCode/2026-06-13-feedbackentrance-retrospective-review.md`
- `/Users/gaotu/Projects/play-book/docs/playbook-index.md`

Supporting evidence:

- `/Users/gaotu/Projects/play-book/Review/ByClaudeCode/2026-06-13-skillcollections-retrospective-review.md`
- `/Users/gaotu/Projects/play-book/Review/ByClaudeCode/2026-06-13-casegeneratorv2-retrospective-review.md`
- `/Users/gaotu/Projects/play-book/Review/ByClaudeCode/2026-06-13-linglong-first-use-retrospective-review.md`
- `/Users/gaotu/Projects/play-book/docs/templates/evidence-indexed-retrospective.md`
- `/Users/gaotu/Projects/play-book/docs/reference/session-reading.md`
- `/Users/gaotu/Projects/play-book/Review/ByClaudeCode/2026-06-14-codex-primary-claudecode-review-loop-review.md`
- `/Users/gaotu/Projects/play-book/docs/checks/2026-06-14-codex-primary-claudecode-review-loop-first-use-check.md`

High-signal FeedbackEntrance anchors:

- 05-15 algorithm subagent review: `/Users/gaotu/.claude/projects/-Users-gaotu-Projects-FeedbackEntrance/07dac409-ca9d-437a-aaa0-94f256c59f8f/subagents/agent-ab40c045d2225b741.jsonl#record_index=51`
- 05-15 mweb blocker review: `/Users/gaotu/.claude/projects/-Users-gaotu-Projects-FeedbackEntrance/07dac409-ca9d-437a-aaa0-94f256c59f8f/subagents/agent-aaf093e9f45e7d1ec.jsonl#record_index=13`
- 05-15 cross-service consistency critic: `/Users/gaotu/.claude/projects/-Users-gaotu-Projects-FeedbackEntrance/07dac409-ca9d-437a-aaa0-94f256c59f8f/subagents/agent-a7833fd283dd09d3e.jsonl#record_index=19`
- 05-15 blocked platform review: `/Users/gaotu/.claude/projects/-Users-gaotu-Projects-FeedbackEntrance/07dac409-ca9d-437a-aaa0-94f256c59f8f/subagents/agent-aa6095f56b20ef988.jsonl#record_index=11`
- 05-28 plan-vs-reality review: `/Users/gaotu/.claude/projects/-Users-gaotu-Projects-FeedbackEntrance/b6998722-5296-4114-a5e8-d3a0b97d1e95/subagents/agent-a7cca2ce822a79119.jsonl#record_index=66`
- 05-28 implemented-code review: `/Users/gaotu/.claude/projects/-Users-gaotu-Projects-FeedbackEntrance/b6998722-5296-4114-a5e8-d3a0b97d1e95/subagents/agent-ac842129364440301.jsonl#record_index=92`

## Promotion Gate

This workflow moved from `repo-staged` to `validated checklist` after:

1. ClaudeCode reviews this workflow and approves the evidence/boundary.
2. Codex uses it on one real review-heavy task.
3. The first-use produces a review file, closure notes, and MRS updates.

The 2026-06-14 first-use was self-referential, so it validates the checklist but does not justify an installed skill. Only consider a formal installed skill if a future non-self-referential use shows that agents fail to follow the workflow without an explicit trigger.

## Review Closure Notes

ClaudeCode reviewed this workflow in `/Users/gaotu/Projects/play-book/Review/ByClaudeCode/2026-06-14-codex-primary-claudecode-review-loop-review.md` with verdict `APPROVE WITH NITS`.

Applied changes:

- Added the review-artifact-only / verified-absent rule: when raw ClaudeCode sessions are absent after live-store verification, project-local review documents are artifact evidence, not transcript evidence.
- Cross-referenced the Evidence Rules in `/Users/gaotu/Projects/play-book/docs/templates/evidence-indexed-retrospective.md`.
- Changed role headings from agent-hardcoded names to functional names: `Primary / Continuity Owner` and `Reviewer / Risk-Finder`, while preserving the current Codex-primary / ClaudeCode-reviewer mapping.
- Tightened handoff, checklist, stop-condition, and failure-mode wording for pruned, verified-absent, artifact-only, and unknown evidence gaps.

First-use result:

- `/Users/gaotu/Projects/play-book/docs/checks/2026-06-14-codex-primary-claudecode-review-loop-first-use-check.md` records `PASS with caveat`.
- Promotion decision: validated checklist, not installed skill.
