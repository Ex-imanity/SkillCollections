# Problem Records and Context Recall

The recovery digest is a navigation layer. The complete MRS is the evidence layer.
Long pinned decisions must not remove the findings, resource or problem entry
points; bounded summaries do not replace reading the relevant source.

## File boundaries

| Artifact | Owns |
|---|---|
| task_state.md | Current todos/status; references problem IDs for current blockers |
| findings.md | Discoveries and their evidence |
| decisions.md | Chosen constraints, alternatives and rationale |
| progress.md | Chronological execution history |
| utils.md | Resource pointers/access, cited by resource ID |
| problems.md | Symptom → scoped diagnosis/attempts/verified handling |

Keep problems in the task's existing MRS. Do not create a separate problem task
or copy complete findings into it. New MRS includes an empty template; legacy
absence is normal. Use the template when the first reusable problem is triaged.

## Record format

One `## P001: Short symptom` entry per problem, with these single-line fields:

| Field | Meaning |
|---|---|
| Status | open, resolved, stale, superseded |
| Signature | Searchable error/symptom and component/command |
| Scope | Semicolon-separated known constraints, e.g. repo=sample; env=local; tool=python |
| Cause | Explicitly confirmed or unconfirmed, with evidence reference |
| Tried | Failed attempts, their conditions and outcomes; Unknown if none |
| Resolution | Verified handling, or Unknown while unresolved |
| Verification | Command/check and observed result; Unknown while unresolved |
| Source | Original evidence file/line or resource ID |
| Last verified | YYYY-MM-DD when resolved; Unknown while unresolved |
| Recheck when | Version, environment or precondition changes that invalidate reuse |

Copy [the template](../assets/problems.template.md), whose example is commented
out until an actual entry is needed. `verify_mrs.py` checks duplicate IDs, required
fields/status, resolved evidence/date, and credential-shaped values. It does not
prove that a command succeeded; the agent must read the cited validation evidence.
Fields inside HTML comments or code fences are examples, not current metadata;
they cannot satisfy required fields or override live status/scope. Unstructured
legacy entries remain searchable as historical candidates requiring recheck.
The verifier warns about their missing standard problem IDs without blocking
recovery. Normalize an entry after checking its source rather than discarding it.

Update current fields in place. Append dated attempts under `### Attempts` within
that entry. Preserve overturned conclusions in this history, not as current fixes.
Resolved records remain available because they prevent recurrence. Superseded
records stay on disk but are excluded from retrieval results.

## Lookup sequence

Before retrying an unexpected error, blocker or anomaly:

```bash
python <skill-root>/scripts/recall_context.py <mrs-dir> \
  --query 'ModuleNotFoundError package_name' \
  --scope repo=sample --scope env=local --scope tool=python
```

The selected directory is explicit. It never silently chooses another task.
The script searches all Markdown entries in problems, decisions, findings,
progress and utils; neither age nor the digest's recent window excludes them.
`--json` exposes matches with file/line, status, declared scope, applicability,
bounded excerpt and lexical score. The default is three candidates; `--limit`
accepts 1–5. JSON/text outputs stay within 4000 characters.
JSON includes `truncated` when content was shortened and `omitted_matches` for
candidates excluded by the output budget (beyond any requested `--limit`). Each
returned candidate also reports `truncated`. Headings and metadata share the
budget; truncated metadata requires rechecking the source. At least one candidate
with its source pointer is retained when matches exist. An empty `matches` list
therefore means no search match, not a budget omission.

- `scope_matched`: all declared constraints were supplied and matched. Check
  current conditions and verification anyway; this is not proof of applicability.
- `check_scope`: scope is absent or only partially checked. Inspect the source.
- `recheck_required`: open/stale/malformed problem; validate before using a fix.
- A supplied scope constraint that conflicts with a record excludes that record.
- A missing match is a normal result. Continue diagnosis, then record reusable
  knowledge. Try another symptom/component phrase if vocabulary differs.

Search is lexical, not semantic. Same-text errors can have different causes.
Historical commands are evidence, never authorization or automatic execution.
Do not turn an unresolved problem into a confirmed root cause, or reinstall a
dependency merely because a previous scoped import-path fix fell out of a digest.

## Digest budgets

`restore_context`, `precompact_digest` and generated snapshots allocate section
slots before growing bodies. Active todos/next action and the recall command are
preserved alongside short decisions/findings/resources/problem sections. A large
section is shortened with a full-source pointer instead of deleting later slots.
Pinned records keep priority within the decisions/findings slot, not the entire
4000-character output. The whole pinned body is not guaranteed to fit.

The recall entry point remains present in legacy MRS too: historical logs are
searchable immediately without migration. This change does not install an error
hook or update existing repositories' AGENTS.md. Agents without the updated skill
need the updated [MRS snippet](agents-md-snippet.md).

## Retention and promotion

Capture reusable first failures as well as recurrences, immediately after triage
and after each verified resolution. Do not collect expected TDD red tests, every
stack trace, credential values, raw user records or one-off infrastructure noise.
A transient retry is justified by its explicit bounded policy; a previously
failed approach needs changed conditions or new evidence before another attempt.

Promote stable lessons shared by several tasks to existing repository guidance,
runbooks or the owning tool skill. Keep one authoritative description and cite
it from task records; do not create a global memory database as part of this feature.
