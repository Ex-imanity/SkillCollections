# Cross-Agent Review Protocol (CLI-mechanized)

> **Bundled copy note (SkillCollections):** in this skill bundle the adapters live under `scripts/` (run `python -m scripts.<module>` from the skill dir) and the reference docs under `references/`. Historical evidence citations below (raw session paths, play-book file:line, test counts) point at the source play-book repo and are advisory provenance, not bundle paths.


Status: **installed local bundle; P1 hardening and the 2026-07-25 Codex→ClaudeCode gateway-compatibility gate passed**. Historical validation cited below remains provenance for prior versions, not proof for later installed versions.

This protocol adds **mechanical CLI enforcement** on top of the validated, agent-agnostic checklist `references/codex-primary-claudecode-review-loop.md`. It does not restate that checklist's roles, stop conditions, or failure modes — read it first as the base protocol. Here we add: how the two host agents actually call each other, how readiness/credentials/cost/rounds are enforced, and how failures fail closed.

## Direction map

| Direction | Mechanism | Owner |
|---|---|---|
| Codex → ClaudeCode | `python -m scripts.codex_to_claude` wrapping `claude -p` | this repo (locally tested) |
| ClaudeCode → Codex | `python -m scripts.claude_to_codex` wrapping `codex exec --sandbox read-only` | this repo (locally tested); official Codex plugin is an OPTIONAL fallback (see `references/claude-to-codex-mapping.md`) |

Portability: the skill depends only on the `claude` and `codex` CLIs — NOT on the official Codex plugin. The plugin is an optional convenience path; the primary/distributable route is the repo-owned `claude_to_codex` adapter, so the skill still works for users who never installed the plugin.

Task-state portability: the protocol does **not** require the `context-resilient-task` skill. It requires the primary to preserve durable continuity, review rounds, cost provenance, and closure. The `.task-state/cross-agent-review/...` locations below are project conventions passed through CLI arguments, not imports or runtime coupling; callers may use equivalent durable paths or another MRS implementation.

Guarantee boundary: mechanical guarantees now apply to BOTH directions. Each repo adapter enforces fail-closed behavior, a concurrency-safe fixed cap of two started calls and two successful reviews per artifact (one exclusive marker lock spans check through commit; a call reserves its attempt immediately before the reviewer subprocess begins), redaction, and result-based readiness; the reviewer is physically read-only (`--permission-mode plan` plus fixed `Read,Grep,Glob` for claude, hardcoded `--sandbox read-only` for codex — none are caller-tunable). Codex success additionally requires source-verified provenance — a `thread.started.thread_id` session id AND a `turn.completed.usage.{input_tokens,output_tokens}` pair (codex rust-v0.144.1; verified optional `cached_input_tokens`/`reasoning_output_tokens` captured when present). Only these verified event-type + field paths gate success; the `--json` stream is unversioned, so on a rename the adapter fails closed loudly and records diagnostic hints (observed event types + any conventional alias names seen) rather than accepting an unverified alias as success. Missing USD is recorded as `total_cost_usd: null`, never a fabricated 0. The primary still verifies every returned finding.

Continuity: exactly one primary/continuity owner at a time (owns MRS + fixes + closure). The reviewer is read-only and returns evidence-cited findings; it must not silently edit MRS or the reviewed artifact.

## Readiness contract (both directions)

Readiness = a **real minimal result envelope**, never `claude auth status`.

- For `claude -p`: ready iff `exit_code == 0 && is_error == false && api_error_status == null`.
- `claude auth status` is explicitly rejected as a readiness signal: on this machine it reports `firstParty/oauth` while the live credential is actually supplied by the `~/.claude/settings.json` proxy env block. Auth status is not just insufficient — it is misleading about which credential path is live. Keep the endpoint and token redacted in repository artifacts. (Evidence: `Review/ByClaudeCode/2026-07-21-cross-agent-review-skill-feasibility-review.md` P1-B.)

Historical 403 timeline (not a generic troubleshooting rule): the 2026-07-21 403 came from a corrupted `claude` npm install and was cleared by reinstall. A distinct 2026-07-24/25 failure was isolated with request capture and no-model provider probes: the configured bearer credential was identical, while one third-party gateway rejected Claude Code's default `claude-cli/... (external, sdk-cli)` User-Agent with 403 and accepted a derived plain `claude-cli/<version>` identity far enough to return the expected non-auth 400 for the invalid no-model body. A real adapter gate then succeeded. That evidence establishes a gateway client-identity policy for that environment, not a universal token or 403 diagnosis. Treat each execution context's real result envelope as authoritative.

## Credential rule (verify-then-fallback)

The Codex→ClaudeCode adapter, before invoking the model:

1. **Verify** `~/.claude/settings.json` has non-empty `env.ANTHROPIC_BASE_URL` and `env.ANTHROPIC_AUTH_TOKEN` → use that configured source (`settings-env`). For the child process, create a fresh temporary `CLAUDE_CONFIG_DIR` and explicitly inject those verified values; do not rely on host-specific CLI settings resolution.
2. **Fallback**: only if either configured value is missing, require both values from the explicit subprocess env (`explicit-inject`).
3. **Inherit**: if no proxy gateway is configured (neither source supplies both keys) → `inherited`. The child runs with the local `claude` CLI's own existing auth (subscription/OAuth login in the default config dir, or an ambient `ANTHROPIC_API_KEY`) — no proxy is injected and the default `CLAUDE_CONFIG_DIR` is kept. This is the common case for installers who are NOT behind a custom gateway. Auth is still judged on the real result envelope, never pre-asserted; an unauthenticated CLI classifies as `auth_failure` and fails closed.

Portability note: the proxy-env path (`settings-env`/`explicit-inject`) is for gateway deployments like this machine's; it is not a precondition for using the skill. The `inherited` path makes the forward gate work on official Claude auth without any `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`.

Never log the token. Never run `claude auth login/logout`.

## Gateway client-identity compatibility

The default and preferred path keeps Claude Code's official `sdk-cli` identity. If the gateway has been evidenced to reject that identity with a pre-model 403, ask its operator to allow it. The adapter exposes one narrow fallback only after explicit user approval:

```bash
--gateway-compat-cli-identity
```

With the flag, the adapter resolves local `claude`, runs that exact binary's `--version`, derives `claude-cli/<semantic-version>`, and uses the same resolved binary for the paid review. It removes inherited `ANTHROPIC_CUSTOM_HEADERS`, `CLAUDE_CODE_ENTRYPOINT`, and `CLAUDE_AGENT_SDK_VERSION` from the child environment, then adds only the derived User-Agent. It accepts no caller-supplied identity, `claude-vscode`, or arbitrary custom headers; an unavailable/non-semantic local version fails before reserving a paid attempt. The parent Codex environment is unchanged.

## Safety envelope

- **Least privilege**: `--permission-mode plan` + fixed `--allowedTools 'Read,Grep,Glob'`. The public API and CLI expose no tool-permission override. If a diff requires commands, persist the diff as a readable artifact before opening the gate.
- **Fresh session per gate**: every gate starts a new reviewer session. A re-review is a second fresh gate for the same artifact; its request file must explicitly include the prior findings and new evidence. The adapter exposes no resume/session override, so hidden context cannot cross artifact boundaries.
- **Attempt and success caps** (cost is treated as real): at most two started calls and at most two successful reviews per artifact. One exclusive marker lock spans cap check, attempt reservation, paid call, durable persistence, and success commit. Because all artifact counters at one marker path share that lock, cross-artifact gates using the same marker serialize; lock acquisition has no independent timeout, and a waiter normally waits behind the holder's configured subprocess timeout (600 seconds by default) plus local I/O. A started call consumes an attempt even when it later fails, times out, or cannot be persisted; a call rejected before the subprocess boundary does not. Beyond either cap → fail closed. A tampered/malformed marker fails closed (`invalid_marker`) without reset; recovery = delete the shared per-artifact marker file.
- **Marker and lock recovery**: all artifact counters at one `--marker-path` live in a shared single marker JSON file. Its adjacent `<marker-path>.lock` is a normal persistent flock coordination file: it can remain after a successful or failed gate, contains no review counts, and its mere existence is not evidence of an active or failed gate. Put both paths under an ignored task-state location. Do not manually delete the lock while a gate might hold it. A damaged marker JSON fails closed for every artifact in that file and is never reset automatically; preserve it for diagnosis, then delete only the marker file manually to recover. The next readiness-qualified review attempt recreates the marker.
- **Lifecycle visibility**: after durable attempt reservation and immediately before the reviewer subprocess begins, both adapters emit one redacted, stderr-only `review_started` JSON record containing the gate ID, artifact key, attempt number, and timeout. It never contains prompt text, commands, credentials, endpoint values, headers, or reviewer output. This is an active-gate signal only; the final structured result remains the stdout contract.
- **Cost/latency audit**: record provider-reported `total_cost_usd` + wall time per gate (`log_cost`); absent USD is `null`, not zero. Rationale: a trivial proxied call reported ~$0.55 (parent review P2-B).
- **Bounded execution**: both adapters enforce a wall-time timeout. The Codex→ClaudeCode adapter requires a user-approved `--max-budget-usd` at invocation time. Codex does not expose a matching USD cap in this route, so ClaudeCode→Codex requires explicit user approval plus the fixed attempt cap; do not describe that path as mechanically USD-capped.
- **Fail closed**: any non-success writes a durable handoff (`fail_closed`) for a human to continue in an interactive ClaudeCode session. Never fabricate reviewer output.
- **Durable success**: a verified, non-empty reviewer result is written as Markdown with only gate/session/cost metadata. The raw result envelope is not persisted.
- **No recursion**: the reviewer prompt forbids calling the other agent back; the plugin review gate stays disabled by default.

## Codex → ClaudeCode invocation contract

Canonical adapter form:

```bash
python -m scripts.codex_to_claude \
  --request-file Review/ForClaudeCode/YYYY-MM-DD-review-request.md \
  --add-dir <repo-root> \
  --handoff-dir Review/ForClaudeCode \
  --marker-path .task-state/cross-agent-review/rounds.json \
  --gate-id <stable-gate-id> \
  --artifact-key <stable-artifact-key> \
  --cost-log .task-state/cross-agent-review/cost.jsonl \
  --output Review/ByClaudeCode/YYYY-MM-DD-review.md \
  --timeout-seconds 600 \
  --max-budget-usd <user-approved-per-call-budget>
```

Append `--model <optional-claude-model>` only when the user explicitly selects
the Claude reviewer model; omit it to retain the local CLI default.

For a confirmed gateway client-identity 403 only, append the user-approved `--gateway-compat-cli-identity` option described above. A materially revised artifact version gets a fresh artifact key; an unchanged artifact keeps its key so the fixed cap cannot be bypassed.

Run `python -m scripts.codex_to_claude --help` for all options. The adapter assembles `claude -p --output-format json --permission-mode plan --allowedTools Read,Grep,Glob`; these permissions cannot be widened by the caller.

`--model` is optional in both directions. Omit it to let the local CLI choose
its configured default. A valid value is passed as one native
`--model=<value>` argv token and written as `requested_model` only in the
post-invocation cost record; it is not evidence of an effective provider model.
The adapter accepts provider-defined identifiers without an allowlist, but
rejects empty, leading-`-`, ASCII-control-containing, or over-128-character
values before any attempt reservation. A conclusive local `--help` result that
lacks `--model` fails closed before the subprocess; an inconclusive probe does
not block and never asserts that a particular model is available.

Must be passed explicitly (the reviewer starts blind — no MRS/context auto-discovery): target artifact paths, review questions, evidence/acceptance criteria, readable dirs (`--add-dir`), output language, and a user-approved `--max-budget-usd`. Judge readiness on a non-empty success envelope. Any runner exception, timeout, invalid envelope/provenance, auth failure, setup/cost/persistence I/O failure, damaged marker, or cap refusal returns non-zero and makes a best effort to write a redacted durable handoff; if handoff persistence itself fails, the structured result records `handoff_error`.

Use `scripts/codex_to_claude.py::review_gate(...)` which applies readiness → fixed-cap check → attempt reservation → stdin invoke → classify → cost-log → fail-closed in order. A readiness failure never consumes an attempt. The request prompt is passed through stdin rather than argv, so long or flag-like prompt text cannot become a CLI option.

## ClaudeCode → Codex invocation contract

Primary path: the repo-owned direct adapter `python -m scripts.claude_to_codex` wrapping `codex exec --sandbox read-only --json --output-last-message`. It enforces the same guards as the codex→claude adapter (fail-closed, fixed attempt/success caps, redaction, result-based readiness, hardcoded read-only) and parses the `--json` stream for real `thread_id`/token-usage provenance. It also accepts the optional common `--model <MODEL>` flag; omit it for Codex's configured default. Codex reports no per-call USD cap here: require explicit user approval, then use the timeout and fixed attempt cap. A chosen model can change this bounded-but-not-USD-capped exposure; do not infer a Claude-style budget ceiling. No official-plugin dependency is required.

Optional fallback (only if the plugin is already installed): full mapping in `references/claude-to-codex-mapping.md`. Summary: code defects → `/codex:review`; plan/approach/design review MUST default to `/codex:adversarial-review`; `/codex:rescue` only for exceptional non-diff investigation, output advisory; session handoff → `/codex:transfer`. A plugin job launched read-only has `write=false`; require full review text in the job result, then persist it with job/thread provenance. Do NOT reimplement the plugin broker.

## First-use honesty

Distinguish, in any check doc:

- `CLI-path verified (manual probe)` — a reviewer envelope succeeded from a controlled probe.
- `adapter end-to-end first-use (pending/passed)` — the adapter drove a real review gate start-to-finish under a primary turn.

Do not merge these into one "bidirectional first-use passed" claim.

## Evidence basis

- `Review/ByClaudeCode/2026-07-21-cross-agent-review-skill-feasibility-review.md`
- `Review/ForCodex/2026-07-24-plugin-independence-closure.md`
- `skills/cross-agent-review-workspace/iteration-2/eval2-direct-reverse/closure-review.md`
- `references/codex-primary-claudecode-review-loop.md` (base checklist)
- `tools/cross_agent_review/{codex_to_claude,claude_to_codex}.py` + both adapter test modules
- Optional plugin mapping backed by `/Users/gaotu/.claude/plugins/cache/openai-codex/codex/1.0.6/commands/`
