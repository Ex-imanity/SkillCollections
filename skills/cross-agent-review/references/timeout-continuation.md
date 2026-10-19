# Continue an unfinished local-agent review after timeout

This continues one interrupted gate. A finished review followed by artifact
changes is a new counted gate with prior findings and new evidence in its request.
Codex, Grok and ClaudeCode support this exception. ClaudeCode/Grok primaries use
the same source `to_codex` adapter for the Codex reviewer route.

## Start with recoverable identity

From the skill directory, start the usual Grok gate. Pass every actual reviewed
file using repeated `--artifact-path`; paths are relative to `--cd` unless absolute.

```bash
python -m scripts.to_grok \
  --request-file /repo/Review/ForGrok/request.md \
  --cd /repo \
  --handoff-dir /repo/.task-state/review/handoff \
  --marker-path /repo/.task-state/review/rounds.json \
  --gate-id feature-r1 \
  --artifact-key feature-current-content \
  --artifact-path src/feature.py \
  --artifact-path tests/test_feature.py \
  --cost-log /repo/.task-state/review/cost.jsonl \
  --output /repo/Review/ByGrok/feature-r1.md \
  --timeout-seconds 600
```

The adapter persists a new UUID before invoking native `grok --session-id=<UUID>`.
It does not depend on final stdout to discover which session to recover. Local
`grok --help` must support `--session-id` and `--resume`; a conclusive unsupported
probe fails before reserving an attempt. Model/auth/permissions stay unchanged.

For ClaudeCode, use its adapter with the same durable gate arguments and an
explicit approved budget. `--cd` sets the actual working directory; `--add-dir`
adds readable directories and does not substitute for the working directory.

```bash
python -m scripts.to_claude \
  --request-file /repo/Review/ForClaudeCode/request.md \
  --cd /repo --add-dir /repo \
  --handoff-dir /repo/.task-state/review/handoff \
  --marker-path /repo/.task-state/review/rounds.json \
  --gate-id feature-claude-r1 --artifact-key feature-current-content \
  --artifact-path src/feature.py --artifact-path tests/test_feature.py \
  --cost-log /repo/.task-state/review/cost.jsonl \
  --output /repo/Review/ByClaudeCode/feature-r1.md \
  --timeout-seconds 600 --max-budget-usd 10
```

ClaudeCode also preassigns a UUID, then uses native `--resume=<UUID>` for the
explicit continuation. Its read directories, auth mode, client-identity setting
and original budget ceiling must match. The adapter repeats the same approved
budget flag; continuation is not a new dollar allowance. Provider-side cumulative
budget/cost behavior across terminated processes still needs live validation;
do not claim an aggregate dollar guarantee from local fake-process tests.

## Codex reviewer

Use `to_codex` with the same durable arguments, working directory and actual files:

```bash
python -m scripts.to_codex \
  --request-file /repo/Review/ForCodex/request.md --cd /repo \
  --handoff-dir /repo/.task-state/review/handoff \
  --marker-path /repo/.task-state/review/rounds.json \
  --gate-id feature-codex-r1 --artifact-key feature-current-content \
  --artifact-path src/feature.py --artifact-path tests/test_feature.py \
  --cost-log /repo/.task-state/review/cost.jsonl \
  --output /repo/Review/ByCodex/feature-r1.md --timeout-seconds 60
```

Codex assigns its own initial UUID. The adapter captures the verified
`thread.started.thread_id` event from partial stdout when the owned subprocess
really times out, including byte-valued partial output. A timeout before a native
UUID is observed fails closed as `provenance_failure` and cannot claim a free
continuation. A pending pre-launch record is not a native session locator.

After an observed resumable timeout, repeat **all original arguments**, append
`--resume`, and set the approved extension. The native command is
`codex exec <original options> resume <recorded-UUID> -`; the request remains on
stdin. Parent exec options include `-C` and the permission flags, so they precede
`resume`. Never use `--last`, fork or `--ephemeral`.

`CODEX_HOME` (default `~/.codex`) is bound to the gate. Non-empty local native
history must exist under `sessions/` or `archived_sessions/` before a paid resume
starts; missing/pruned history is refused rather than replaced. The adapter checks
rollout filenames and leaves native transcript parsing to Codex. All user-owned
history/auth remains intact after success or failure.

The production subprocess owns its CLI launcher and native child together. On
POSIX timeout it kills and waits for the owned process group; Windows uses
`taskkill /T /F` for the launcher tree. This avoids leaving the native review
running behind a terminated npm Node launcher. Unobservable cleanup fails closed.

Success still requires a self-contained verdict, the same native UUID on resume
and a complete non-negative `turn.completed.usage` token pair. Codex reports no
USD amount in this route: cost remains `null`. A resumed timeout does not commit a
success or reset the attempt. Local CLI help is checked for native resume support
before reserving an attempt.

## After a real timeout

Retain and observe the original runner handle as required by the main protocol.
A terminal display returning early is still `in_progress`. Only after that
subprocess has exited and final stdout reports `status: timeout` with
`resumable: true`, continue within the user's approved time/cost scope. If they
authorized another ten minutes, repeat **all original arguments** above and append:

```bash
--resume --timeout-seconds 600
```

Keep the original gate ID, request file/content, artifact key, working directory,
model, output path, artifact paths and native session store. The runtime restores
the recorded UUID using the peer's native `--resume=<UUID>`, repeats the original request with
an instruction to continue saved progress, and retains the completion contract.
It never silently falls back to a new session or selects the latest session.

## Counting and audit

| Segment | attempts | successes | continuation |
|---|---:|---:|---:|
| New session times out | 1 | 0 | 0 |
| Same session times out again | 1 | 0 | 1 |
| Same session finishes a verified review | 1 | 1 | 2 |

The fixed cap remains two new attempts and two successful reviews per artifact.
An unfinished timeout can continue even when both fresh attempts were reserved.
Success is committed only once; a completed gate cannot resume for another free
review. A later counted attempt for that artifact invalidates the older timeout's
continuation binding.

Every segment still starts a provider call, has a finite positive timeout, and
appends a cost record with `attempt`, `continuation`, `resumed`, `session_id`,
wall time and provider-reported cost. Missing cost remains `null`. Do not
equate the attempt exemption with free billing or an unlimited approved runtime.
Do not automatically continue beyond the user's approval; an existing explicit
approval covering the extension remains sufficient.

The initial `review_started` lifecycle event remains unchanged. Continuations
also include `resumed: true`, their sequence number and session ID. They remain
in-progress signals, not review results. Final stdout includes `resumable`,
`continuation_state_path`, `attempt` and `continuation` alongside the normal result.

## State and refusal boundaries

- Counters keep their existing JSON format. Per-gate identity/state is in
  `<marker-path>.sessions/<gate-id-sha256>.json`, under the same exclusive lock.
  Preserve this directory with the marker, cost log and native session.
  It stores hashes and lifecycle metadata, not request text or credentials.
- Only `timed_out` records can resume. `running`, `completed`, other failures,
  missing/damaged records, reset/mismatched counters, and changed bindings fail
  closed without starting a reviewer or reserving another attempt. Do not edit
  record state to force an exemption.
- Actual files passed with `--artifact-path` are content hashed. A manifest file
  alone does not check its referenced files. For legacy callers omitting this
  option, only the request/key/scope/model/output/store binding is mechanical;
  the primary must still verify the artifact is unchanged. New skill-driven
  invocations must register the actual reviewed files.
- A resumed successful envelope must return the same session ID and satisfy
  its existing completion contract: Grok requires a complete token pair,
  `stopReason=end_turn` and verdict; Codex requires its verified thread UUID,
  token pair and verdict; ClaudeCode requires its non-error JSON result
  and self-contained verdict. Missing identity/history fails closed without
  fabricating a review, committing success or starting a replacement session.
- Cost-log or persistence failures do not become resumable timeouts. A partial
  output file or a `review_started` event is never a valid review.
- This requires a gate started by version 2.2.0 or later. Old timeouts without
  the new record are not automatically imported or refunded. Do not alter
  historical counters based on this new counting policy.

Deterministic tests and real local fake subprocesses cover timeout, native resume,
accounting, rejection and cleanup behavior. Report live provider evidence separately
for each route/version: a real timeout followed by another timeout verifies the
resume launch and attempt exemption, not successful completion. A final verified
success and its counter must be observed before claiming that full path passed.

## ClaudeCode history and authentication

Configured and explicitly injected proxy credentials use a fresh private
`CLAUDE_CONFIG_DIR` below the gate's `.json.runtime/<session-id>/claude-config`
directory. Its permissions are private on POSIX. The bridge injects credentials
through the child environment; it does not write them into the retained state.
A real timeout preserves that owned directory so the next segment sees the
original history. Final success or failure cleans up the owned directory.

Inherited OAuth/API-key auth keeps the existing user config/history location.
The bridge never deletes that user-owned directory. Native persistence must be
enabled; the bridge does not override user history settings or parse internal
transcript formats. A missing retained private store is rejected before launch.

References verified against local CLI help and official documentation:
[headless session resume and storage](https://code.claude.com/docs/en/sessions),
[budget limits](https://code.claude.com/docs/en/agent-sdk/agent-loop).

Codex native resume syntax and persistence were checked against local `codex-cli 0.163.0 --help`, [official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode), and the official `openai/codex` CLI source via Context7.
