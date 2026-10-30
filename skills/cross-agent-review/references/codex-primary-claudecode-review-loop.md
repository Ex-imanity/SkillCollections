# Primary + Cross-Agent Review Loop

Status: historical validated checklist (originally Codex primary + ClaudeCode reviewer). Its 2026-06-14 first-use evidence is provenance; the containing `cross-agent-review` skill has its own installed-version validation state. The functional split below is agent-agnostic: any of Codex / ClaudeCode / Grok may be primary or reviewer, as long as they are **different** local peers and the mechanical adapters in `scripts/` are used for the reviewer leg.

This is a collaboration protocol for tasks where one local agent should preserve continuity and do the main writing/implementation, while a different local agent should act as a source-grounded reviewer and risk finder.

## When To Use

Use this workflow when:

- A task spans multiple sessions, multiple agents, or multiple repos.
- The primary has the richest continuity through the active thread, MRS, branch, and recent implementation context.
- A different local peer can add value through source-path review, subagent fan-out, independent risk discovery, or evidence verification.
- The expected output needs review closure, not just a quick answer.

Do not use this workflow when:

- The task is a small local edit with low risk.
- No durable review artifact is needed.
- The chosen reviewer cannot access the required repo/files and no alternative evidence path is available.
- The user asks for an immediate answer rather than a reviewed artifact.

## Roles

Example mapping: Codex primary + ClaudeCode reviewer. Equivalent mappings include Grok primary + ClaudeCode/Codex reviewer, or Codex/ClaudeCode primary + Grok reviewer. Keep the functional split and name the mapping explicitly in the review request.

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
- Returning findings under the reviewer-owned directory (`Review/ByClaudeCode/`, `Review/ByCodex/`, or `Review/ByGrok/`) with severity and concrete source paths.

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
- A target review output path under `Review/ByClaudeCode/`, `Review/ByCodex/`, or `Review/ByGrok/`.
- Explicit review questions.
- For source-code changes: repository/module and comparison base, actual changed
  and new/untracked files, applicable conventions, accessible local profile/style
  evidence, recent substantive comparators and justified older fallbacks,
  file-placement/capability ownership and self-review/deviation rationale.
  If the implementation has no such record, the
  reviewer reconstructs it from source rather than assuming compliance or failure.

For evidence classification, use the Required Inputs above and the
[bundled protocol](cross-agent-review-protocol.md). Read only evidence authorized
by the review request. If raw sessions are unavailable, state that limitation and
keep review artifacts distinct from transcript evidence. Author-machine paths in
Evidence Basis and Review Closure Notes below are optional historical provenance,
not prerequisites for an installed bundle.

## Workflow

### 1. Primary Reconstructs State

The primary reads:

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
- the actual review/verification snapshot and file scope; when CR inputs exist,
  the original item dispositions, verification evidence and inherited open items

For code, include the style evidence above and ask the reviewer to independently
open pre-existing same-role implementations. Provide paths to an available
`repository-code-style` skill and only applicable references when readable by the
peer; otherwise include the necessary checklist in the request. The bundled
shared prompt already supplies a minimal checklist without a skill dependency.

Validate the profile against its branch/base, relevant committed and dirty
changes, and scoped source. Prefer roughly the last six months of substantive
same-role changes, compare conflicts and later CR, and explain older still-valid
examples. Recent formatting or the reviewed batch itself is not new authority.
Review file/class necessity, directories, layer ownership and production/framework
use before reuse/semantic parity and internal expression. Keep runtime checks of
async proxies, transactions, failure handlers and extension points separate.

If the profile is inaccessible, inline authorized minimal evidence: mechanism
identity for key types (annotation/interface/registration), the closest
same-mechanism production peer's path + symbol + commit, and relevant capability
or configuration ownership, together with repository/scope/base. These map to
the organization, examples and capability sections of the local profile
template. Mark unavailable fields as gaps for source reconstruction; do not
copy a whole private profile or assume the peer can read a private path.

Ask the reviewer to compare deleting/merging new layers or directly using
existing capabilities, and verify adopted APIs, effective versions and semantic
equivalence. Candidate names and actual callers alone do not justify reuse or
an extra layer. Reconcile original CR items without promoting suggestions into
requirements; retain unresolved items and separate implementation from
verification. Check changed business documentation for accuracy after refactoring.
Bind conclusions to the reviewed snapshot, including declaration/reference/
registration and release dependencies for moves or renames. Working-tree
success does not prove a partially staged snapshot passes.

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
- For code, a separate `Style consistency: PASS | NEEDS CHANGES | NOT VERIFIED`
  conclusion with changed-file and historical-comparator paths/lines, relevant
  scope and deviations. Review directory ownership, injection/annotations, naming,
  reuse/query/object construction, errors/logging, comments and tests as relevant.
  Verify implementer claims; generic best-practice praise is not repository
  evidence. Use `NOT APPLICABLE` for plans/documents without source-code changes;
  apply the code checklist only to the code portion of mixed artifacts.
- Recommendation for next step.

If ClaudeCode cannot access a target repo or raw session, it must mark the review area blocked or evidence-limited. If raw ClaudeCode sessions are verified absent but project-local review files exist, it must label those files as artifact evidence, not transcript evidence. It must not infer findings from memory.

### 4.5 Wait For A Final Gate Result

Before launching, retain a **trackable runner handle**: the terminal-runner
session ID or parent adapter PID; prefer a recorded PID whenever the host
exposes it, because it survives loss of a terminal display handle. Where the
host allows it, record the gate ID, parent process start time or command
identity, and redacted stdout/stderr capture paths in primary-owned task state;
never record request text or credentials.

`review_started` is not a completed review and is not permission to inspect
the output path for closure. A terminal tool returning early, releasing its
display handle, or streaming only stderr does not prove the reviewer subprocess
has exited. Until it does, report only `in_progress`; do not spend another
retry, declare a verdict, inspect final artifacts, or update MRS closure state.

Poll only the original handle. For a recorded PID, use a process-status check
on POSIX and the platform process API on Windows. PIDs can be reused, so where
the host exposes process start time or command identity, confirm it matches the
recorded parent before treating that PID as the original process; a mismatch or
unavailable comparison after session loss means report the process as
unobservable. If the terminal session is lost, reattach through the recorded
PID. If neither identifier is available, report the process as unobservable and
wait through the configured timeout rather than infer failure or launch a
replacement gate. Only after the original process is observed to have exited,
or the configured timeout truly expires, validate final stdout JSON first, then
the output or handoff and update durable state.

For a Codex/Grok/ClaudeCode gate whose final result is a recorded resumable `timeout`, an
explicit continuation may reuse that gate and native session after the original
subprocess exits. It does not consume a new attempt, but it still consumes time
and provider cost. Follow `timeout-continuation.md`; remain within the user's
approved scope, never automatically start a replacement session, and never use
this exception to re-review an already completed or changed artifact.

### 5. Codex Applies Or Pushes Back

Codex processes the review:

1. Fix blockers and valid P1/P2 issues first.
2. Push back only with evidence, tests, or direct source citations.
3. Leave optional polish for later when it does not affect the current gate.
4. Update the reviewed artifact.
5. Add review closure notes that map findings to changes, retained suggestions
   or justified exceptions, and verification evidence or remaining gaps.

For style findings, distinguish explicit rule violations, supported local-pattern
deviations, justified exceptions, suggestions and unavailable evidence. Determine
severity from impact; do not dismiss an explicit convention violation merely
because it was labeled P3, or treat every style suggestion as a blocker.
When original CR inputs exist, preserve each item's source/scope and strength,
inherit unresolved items, and keep implementation and verification states
separate. New findings do not erase old ones, and a TODO is not closure.

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
- For code, the request provides a comparison base and style evidence/questions;
  the reviewer can access the actual source and pre-existing comparators or the
  limitation is explicit. A skill name alone is not a self-contained handoff.
- The request identifies the actual snapshot/file scope and, when applicable,
  original CR item dispositions and open findings; inaccessible profiles have
  the authorized minimum inline evidence or explicit gaps described above.

## Review Closure Checklist

Before claiming the loop is complete, confirm:

- The ClaudeCode review file exists.
- The verdict and all blocker/P1 findings have been addressed or explicitly rejected with evidence.
- The reviewed artifact includes review closure notes or the MRS records the closure.
- MRS verification passes.
- Any remaining candidate/promotion decision is explicit.
- For code, the style conclusion and both sides' evidence match the delivered
  revision, and confirmed required changes are resolved or supported exceptions
  are recorded. Missing evidence remains `NOT VERIFIED`; it cannot be called
  style closure. A passing envelope/verdict or functional test is not proof of
  this check. Pure documents/plans are not blocked for having no code diff.
- Original CR items and inherited findings each retain a disposition and
  verification status. Review and check results correspond to the delivered
  snapshot; unverified staged/commit/PR content is not certified by worktree checks.

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
