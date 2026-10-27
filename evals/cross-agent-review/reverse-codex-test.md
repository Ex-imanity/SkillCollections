# Test ClaudeCode/Grok primary → Codex reviewer from repository source

Use the repository bundle explicitly before installation. A change in this
repository does not require synchronizing global installed skills. Ask the
primary to read this bundle's `SKILL.md` and protocol, then run from its directory.
Both ClaudeCode and Grok use the same primary-agnostic `to_codex` entry point:

```bash
cd /path/to/SkillCollections/skills/cross-agent-review
python -m scripts.to_codex \
  --request-file /repo/Review/ForCodex/request.md \
  --cd /repo \
  --handoff-dir /repo/.task-state/review/handoff \
  --marker-path /repo/.task-state/review/rounds.json \
  --gate-id claude-to-codex-r1 \
  --artifact-key reviewed-content-identity \
  --artifact-path src/feature.py --artifact-path tests/test_feature.py \
  --cost-log /repo/.task-state/review/cost.jsonl \
  --output /repo/Review/ByCodex/claude-r1.md \
  --timeout-seconds 600
```

For the Grok primary, use a distinct `grok-to-codex-r1` gate ID and output path.
Keep the artifact key for unchanged content so tests cannot bypass its fixed cap.
Use different marker files if these are independent test campaigns; the same
marker deliberately shares the per-artifact cap and serializes calls.

The request must name actual files/revisions, review questions, evidence,
acceptance criteria, language, no-modification scope, and the user's approved
time/cost limit. Omit `--model` unless the user selected one. Codex has no USD
ceiling on this route; do not invent one or infer test approval from this example.

Check the original runner until it exits, then validate final stdout first.
Success must persist a self-contained verdict with genuine session/token
provenance. Inspect the marker, cost log and artifact hashes. A partial file or
`review_started` is not completion. The source test suite exercises both parent
environments with a fake local Codex process; the user runs live-provider tests.

Codex **as reviewer** now supports the same explicit timeout continuation.
For a real timeout test, choose a user-approved short initial limit (for example
`--timeout-seconds 60`), retain the runner handle and wait for exit. Only if final
stdout reports `status=timeout` and `resumable=true`, repeat the original command
with `--resume` and an approved extension. Keep request, files, gate/artifact key,
working directory, model, CODEX_HOME, output and cost-log path unchanged.

The adapter saves the native UUID from partial `thread.started` events; a timeout
before that event is not resumable. It invokes `codex exec ... resume <UUID> -`,
never latest/fork, and checks existing local session history before launching.
Verify both returned UUIDs, native history, `attempts` remaining unchanged and a
single success commit on completion. A second timeout proves continuation launch
and accounting only, not a completed review. See [timeout continuation](../../skills/cross-agent-review/references/timeout-continuation.md).
