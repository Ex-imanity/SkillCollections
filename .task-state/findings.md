# Findings

<!-- Append research notes and discoveries below this line. -->

## 2026-07-25 — P1 verification evidence
- Existing marker entries were non-negative integers and represented successful reviews only. New structured entries preserve separate `attempts` and `successes`; legacy values are normalized to both counters.
- The forward adapter previously accepted an omitted `max_budget_usd`; the reverse adapter has no corresponding USD budget option.
- The installed bundle had no local adapter tests. The new regression file covers both directions without invoking real model CLIs.

## 2026-07-25 — First P1 review-gate attempt
- The authorized `$2` Codex-to-ClaudeCode gate returned a real `auth_failure` envelope with `403 Forbidden`; this is a runtime-context failure, not a successful review.
- The adapter persisted a redacted handoff, no `Review/ByClaudeCode` output, and a marker entry of `{"attempts": 1, "successes": 0}`. This validates the new failed-started-call accounting in a real gate.

## 2026-07-25 10:09 — 403 root-cause (interactive ClaudeCode diagnosis)
Investigated per MRS by reproducing the adapter's exact credential/env path from an interactive ClaudeCode Bash context. Ran 5 nested `claude -p` calls with the adapter's exact argv; all succeeded.

Elimination (all disproven):
- Stale/rotated token: `~/.claude/settings.json` mtime `2026-07-24 15:54` predates the gate and is unchanged; the same token succeeds now.
- Adapter dropped a good env token: settings.json token and live process-env token are byte-identical (len 67, tail `73d6`, same `https://sub2api7.baijia.com`).
- `ANTHROPIC_API_KEY` leak from Codex: injecting a bogus key still succeeds; Codex `shell_environment_policy.set` injects only BROWSER/NODE_REPL vars, no `ANTHROPIC_*`.
- Model-override leak: none injected by Codex.
- `--max-budget-usd` / permission-mode / allowedTools: reproduced success with the full flag set.
- Provider swap at gate time: settings.json unchanged → same provider (sub2api7) throughout.
- Concurrency limit: 5 nested `claude -p` from an active claude session against the same token all succeeded → proxy allows concurrency.
- cc-switch local proxy: claude connects directly to `sub2api7.baijia.com`; cc-switch `proxy_request_logs` has 7082×200 and 0×403 → that 403 never touched the local proxy.

Interim conclusion here (a "transient remote 403") is **SUPERSEDED** by the 10:20 entry below: Codex's 04:05 direct probe reproduced the 403, so it is deterministic and host-environment-specific, not transient.

Follow-up design note (still valid): a 403 is pre-model (zero tokens, no `usage`/`total_cost_usd`); consuming a scarce attempt for a non-billable external failure is over-strict. Candidate refinement: 4xx-auth envelopes with no usage/cost should not permanently burn an attempt (or use a separate expiring `transient` counter).

## 2026-07-25 — Disposition of interactive review findings
- N1 was confirmed by a regression test: without a PATH precheck, the forward adapter invoked its runner after reserving an attempt. `claude_available()` now rejects this before any lock or marker action.
- N2 coverage now verifies the successful-review cap and the reverse CLI's lack of `--max-rounds`.
- N3 is an intentional consequence of one shared marker lock held around the reviewer call; documentation now exposes the serialization and absent acquisition deadline.
- N4 remains unknown at the provider boundary: local tests cannot prove a provider enforces `--max-budget-usd`; the protocol must continue to state that limit honestly.

## 2026-07-25 — Codex-environment proxy probe
- The configured base URL returned HTTP 200 from the current Codex environment, and both required proxy values were non-empty without exposing their contents.
- A real `claude -p` request in the same environment returned 403 before model processing (`duration_api_ms: 0`, zero token usage, zero reported cost). Network reachability and CLI availability therefore do not establish token acceptance or proxy authorization.

## 2026-07-25 — Adapter remedy for Codex host credential resolution
- The current Codex host exports neither `ANTHROPIC_*` nor `CLAUDE_CONFIG_DIR`; the decisive difference is that its spawned CLI does not apply the same settings file as the interactive ClaudeCode host.
- The forward adapter now creates an empty temporary `CLAUDE_CONFIG_DIR` and explicitly injects credentials read from the selected settings file. The temp directory exists only while the subprocess runs, and setup completes before attempt reservation.

## 2026-07-25 — Post-remedy host boundary evidence
- The post-remedy gate still returned pre-model 403 with zero reported cost. Its new artifact marker records one started attempt and no success.
- A real local `/usr/bin/env` child received both settings credentials and the intended empty temporary config directory. The Codex host has no proxy, Node, or SSL override environment variables. This rules out adapter argv/stdin/env assembly as the current cause.
- The equivalent direct-shell probe from the Codex host also returned 403; only execution from the normal terminal/ClaudeCode main host is known to succeed. A comparison artifact is `Review/ForClaudeCode/codex-vs-terminal-runtime-comparison.md`.

## 2026-07-25 10:20 — Conclusive 403 diagnosis (credential-resolution delta between host processes)
Ran controlled `claude -p` experiments from the interactive ClaudeCode host (all with the adapter's exact flags). Evidence:

| Test | Setup | Result |
|------|-------|--------|
| A | Byte-exact Codex command, interactive host | success, api_error_status=None |
| B | env `ANTHROPIC_AUTH_TOKEN=bogus` + good settings.json | success → **settings.json env WINS over process env** |
| C | env `ANTHROPIC_BASE_URL=bogus` + good settings.json | success → settings.json wins |
| D | empty `CLAUDE_CONFIG_DIR` (no settings.json) + good token via env | success → **env-injection is a valid credential path** |
| E | empty `CLAUDE_CONFIG_DIR` + no token | `is_error`, `"Not logged in · Please run /login"`, **NOT 403** |
| F | env `ANTHROPIC_MODEL="claude-opus-4-8[1m]"` + good settings.json | success → model override (incl. `[1m]`) not the cause |

Additional scans: no `ANTHROPIC_*`/`CLAUDE_*` exports in any shell startup file; `~/.codex/auth.json` holds only `OPENAI_API_KEY`.

Reasoning: Codex's probe returned **403 "Failed to authenticate"**, not the "Not logged in" that a no-credential run produces (Test E). So Codex's child `claude -p` **did send a credential and the proxy rejected it**. Because settings.json deterministically overrides process-env creds from an interactive host (Tests B/C), the only way Codex's child gets a wrong credential is if, under the Codex host process, it **does not apply `~/.claude/settings.json`** and instead sends a foreign/stale Anthropic token. Net root cause: a **credential-resolution difference between the two host processes** — the interactive ClaudeCode host resolves the good sub2api7 token from `~/.claude/settings.json`; the Codex host's child does not, and sends a token the proxy 403s.

Confidence: PROVEN — the settings.json token is valid and works via both file and env paths; env cannot break it from an interactive host; no-cred ≠ 403. INFERRED (high) — Codex host remaps config resolution (`HOME`/`CLAUDE_CONFIG_DIR`/sandbox read) and/or exposes a foreign `ANTHROPIC_AUTH_TOKEN` to the child. Missing confirmatory datum: `env | grep -iE 'ANTHROPIC|CLAUDE_CONFIG|^HOME='` captured inside the Codex host process.

Remedy (proven in principle by Test D): make the adapter's child credential deterministic and host-independent. In `resolve_subprocess_env`, for `credential_source=='settings-env'`, instead of popping the proxy vars and relying on the child re-reading settings.json, (1) point the child at a fresh empty `CLAUDE_CONFIG_DIR` (temp dir) so no stale/foreign settings.json can apply, and (2) inject `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` from the adapter-read settings.json values into the child env. Test D shows empty-config-dir + injected good token authenticates. No token is written to disk. This is an adapter-source change owned by the primary (Codex) and needs a fresh budget-approved gate to verify end-to-end.

## 2026-07-25 11:14 — Corrected root cause: gateway rejects `sdk-cli` client identity
- This entry **supersedes** the 10:20 inference that the Codex child sends a foreign/stale token. A local HTTP capture of the actual Claude CLI request showed `Authorization: Bearer` with a hash exactly matching the configured token's complete bearer-header hash. Removing all `CODEX_*` environment variables did not change the header or request identity. The hash value itself is intentionally not persisted.
- The material host difference is `User-Agent`: Codex-launched `claude -p` sends `claude-cli/2.1.216 (external, sdk-cli)`, while the working ClaudeCode extension context uses `claude-vscode`/Agent SDK identity.
- No-model provider A/B with the same endpoint, token, path, and invalid `{}` body isolated the policy: `sdk-cli` User-Agent returns `403`; `claude-vscode`, no User-Agent, and truthful plain `claude-cli/2.1.216` all return `400`. Here `400` is the expected request-validation failure after authentication, so the credential is accepted.
- `ANTHROPIC_AUTH_TOKEN` versus `x-api-key` is not the cause: `x-api-key` and both-header variants remain `403` when paired with `sdk-cli`.
- Claude Code honors `ANTHROPIC_CUSTOM_HEADERS` for `User-Agent`; local capture proved a plain truthful header replaces the blocked suffix. Do not hardcode or impersonate `claude-vscode`. Preferred repair is for the gateway to allow the official `sdk-cli` identity; a child-only truthful plain User-Agent is an explicit compatibility workaround requiring user approval and a fresh paid gate.

## 2026-07-25 11:32 — Compatibility gate and installed fix verified
- With explicit user approval and `--max-budget-usd 2`, a real adapter gate using child-only `User-Agent: claude-cli/2.1.216` succeeded. ClaudeCode returned `APPROVE WITH NITS`; session `4b709883-e03d-474f-9270-8ce32f968bdd`; provider-reported cost `$0.64111725`; wall time `136.546s`; marker `attempts=1, successes=1`.
- The review found no P0/P1 blocker and required the fallback to remain explicit, truthful, narrowly validated, and documented as a gateway workaround. The implementation accepts only `claude-cli/<semantic-version>`, rejects `claude-vscode`/arbitrary values before reserving an attempt, and does not expose arbitrary custom headers.
- The child environment now discards inherited `ANTHROPIC_CUSTOM_HEADERS`, `CLAUDE_CODE_ENTRYPOINT`, and `CLAUDE_AGENT_SDK_VERSION`. Without the option it preserves Claude Code's own default identity; with the option it sets only the validated User-Agent header. The parent environment is unchanged.
- Candidate and installed copies both pass 12 regression tests and Python compilation; a recursive comparison excluding work/cache directories reports no differences.

## 2026-07-25 — Phase 7 local CLI discovery and documentation reconciliation
- The raw `--claude-user-agent claude-cli/<version>` interface validated only a string shape. It could not prove that the claimed version belonged to the binary subsequently reached through `PATH`, despite the documentation calling it truthful.
- New RED tests demonstrated that the derived compatibility flag was absent and the raw parameter was still accepted. The replacement resolves `claude`, runs that exact executable's `--version`, derives the only allowed plain identity, and invokes the review through the same resolved path. An unavailable or unparsable version fails before marker locking or attempt reservation.
- The no-review capability report runs known candidate `--version` commands in a `PATH`-only child environment and never selects detected-but-unsupported CLIs. The actual 2026-07-25 report found supported `claude` `2.1.216 (Claude Code)` and `codex` `codex-cli 0.144.1`; all other catalog entries were absent.
- The 403 documentation now distinguishes the historical corrupted-install incident from the separately proven third-party gateway User-Agent policy. It does not present either as a universal token or 403 diagnosis.
- Source and installed bundles both passed 14/14 regression tests and compilation after synchronization. A recursive comparison excluding only cache/metadata directories reported no content differences.

## 2026-07-26 — Phase 8 compatibility review (will other installers be able to use this?)
Reviewed the installed skill purely for third-party portability. Four blockers found; all fixed. Distribution hygiene is otherwise clean (`git ls-files` confirms `__pycache__/` and the stray `.omc/state/...` are untracked local artifacts, not shipped).

**P1-a — Windows import crash (severity: total failure on Windows).** `codex_to_claude.py` did `import fcntl` unconditionally at module top level. `fcntl` is POSIX-only; on Windows CPython the import raises `ModuleNotFoundError` before any logic runs. Because `claude_to_codex.py` does `from .codex_to_claude import (...)`, the reverse direction crashes at import too — so a Windows installer can use *neither* direction, with a cryptic traceback. SKILL.md/README claimed the only dependency was the two CLIs; the hidden OS dependency was undocumented.

**P1-b — Forward gate hard-coded a proxy/gateway deployment (severity: unusable for standard-auth installers).** `check_readiness` treated a credential as present only if both `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` were set (settings.json `env` or injected), else `missing` → fail closed with `credential_missing`. That matches this machine's CC-switch/LiteLLM proxy, but installers on official Claude auth (subscription OAuth login or `ANTHROPIC_API_KEY`) have neither var set — the `claude -p` child would work with inherited auth, yet the gate refused to start. Biggest "installed but can't use it" risk.

**P2-a — `claude` CLI version coupling.** The forward gate makes `--max-budget-usd` required; it is a relatively new `claude` flag. On an older CLI it is rejected → non-success envelope → fail closed with a confusing handoff instead of "upgrade claude". No minimum version was documented.

**P2-b — codex `--json` schema pinned to a probe date.** `_parse_codex_json_stream` required exactly `thread.started.thread_id` + `turn.completed.usage.{input_tokens,output_tokens}` ("probed 2026-07-24"). A future codex rename would turn every reverse gate into a silent `provenance_failure`. Fails safe (no fabricated review) but is an undiagnosable "reviews stopped working after codex updated" trap.

## 2026-07-26 — Codex source-verification of its own `--json` schema (rust-v0.144.1)
Asked the local Codex CLI (through cross-agent review) to empirically probe `codex exec --json`. Live capture on this host FAILED — the managed sandbox denies Codex's in-process app-server init (`Error: failed to initialize in-process app-server client: Operation not permitted`), stdout was 0 bytes. Codex instead read the upstream source at the exact matching tag `rust-v0.144.1` (this host is `codex-cli 0.144.1`), so the following is source-verified, not guessed:
- Eight event types: `thread.started`, `turn.started`, `turn.completed`, `turn.failed`, `item.started`, `item.updated`, `item.completed`, `error`.
- Session id: `thread.started` → `thread_id` (matches the adapter's primary path). ✅
- Usage: `turn.completed` → `usage.input_tokens` + `usage.output_tokens` (matches). ✅ The usage struct ALSO carries real optional `cached_input_tokens` + `reasoning_output_tokens`.
- v0.144.1 does NOT define `prompt_tokens`, `session_id`, `thread.id`, or nesting under `turn`/`response` — so the adapter's defensive fallbacks are inert-but-harmless on the real schema.
- The stream is UNVERSIONED (union tagged only by `type`, no `schema_version`). Documented historical drift exists for item payloads (`item_type` → `item.type`, `assistant_message` → `agent_message`, codex issue #4776), which validates a tolerant-but-fail-closed parser.
- Codex's guidance: treat "no JSONL / process exit" as startup failure (not malformed provenance); match exact keys, never arbitrary recursion (avoid grabbing collab fields like `sender_thread_id`); keep verified paths as the contract and treat fallbacks as telemetry-flagged compatibility. The adapter already complies (exact `.get()` keys; startup failure → non-`provenance_failure`).

## 2026-07-26 — Codex main-session review of the Phase 8 diff (round 1) + resolution
Codex reviewed the working diff and raised three valid findings; all fixed (suite 29→31 passing).
- **P1 — unverified provenance fallback loosened the success criterion (CORRECT, important).** The rewrite had broadened the *primary* path to accept `thread_id`/`usage` from any event type and let alias names (`session.created`, `prompt_tokens`, `token_usage`) gate a `success`. That could persist an unverified review as "verified". Fix: only the source-verified event-type+field paths gate success (`thread.started`→`thread_id`, `turn.completed`→`usage.{input_tokens,output_tokens}`); alias names became diagnostic-only `drift_hints` recorded in the failure detail and never flip failure→success.
- **P2 — authoritative protocol doc not synced (CORRECT, I missed it).** `references/cross-agent-review-protocol.md` (SKILL.md declares it authoritative) still described the proxy-only `missing` credential rule and strict codex fields. Synced it with the `inherited` credential step and the verified-only-with-diagnostics provenance rule.
- **P2 — Windows lock retried all `OSError` (CORRECT).** The msvcrt branch retried every `OSError`, so a non-contention error (EACCES/EINVAL/EBADF) would hang forever instead of failing closed. Fix: retry only the confirmed contention errno (`EDEADLOCK`/`EDEADLK`), re-raise the rest; added mock-msvcrt tests for both paths.
- Codex confirmed the other three fixes are sound (non-proxy `inherited` auth, budget preflight, Windows import) and that this host reports `claude 2.1.216` / `codex 0.144.1`, doctor `max_budget_supported: true`, no provider calls made.
- Open Question resolved per Codex: keep only source-verified fields as success provenance; speculative aliases are diagnostic hints only.

## 2026-07-26 — Phase 8 closure review
- **Result:** No further blocking finding after re-review of the resolved Phase 8 diff. The three round-1 fixes preserve the stated guarantees: only verified provenance succeeds, non-contention Windows lock errors fail closed, and the authoritative protocol matches the implementation.
- **Verification:** `python -m pytest cross-agent-review/tests/ -q` reported 31 passed; `python -m py_compile scripts/*.py tests/*.py` from `cross-agent-review/` and `git diff --check` passed. No provider call was made.
- **Residual risk:** The Windows `msvcrt.locking` branch is covered by mocks only. The user accepted deferral of real-Windows validation until a Windows use case exists.

## 2026-07-27 — ClaudeCode model-selection plan review
- **Verdict:** `APPROVE WITH NITS` through the verified Codex-to-ClaudeCode adapter gate. Session `6c28687b-8f1f-4ca4-a6cd-cb2d666f9b15`; reported cost `$1.30125925`; one attempt and one success for artifact `cross-agent-review-model-selection-plan-v1`.
- **P2-1 incorporated:** A two-token `['--model', value]` form could let a leading-dash value be parsed as an option. Plan now rejects leading `-` and emits one `--model=<value>` token.
- **P2-2 incorporated:** Documentation and the plan now state that explicit model choice on Codex review changes a route with no provider USD ceiling; it remains bounded only by explicit user approval, fixed attempts, and timeout.
- **P2-3 adopted:** Add an injected, no-network, inconclusive-safe `--help` preflight for an explicitly supplied model. It detects only an absent CLI flag before reservation, never model availability.
- **P3 clarifications incorporated:** set a 128-character bound; document that control checks protect audit/handoff hygiene rather than shell injection; record `requested_model` only in the one post-invoke cost row, never as an effective model.
- **Source:** `Review/ByClaudeCode/2026-07-27-cross-agent-review-model-selection-plan-review.md`.

## 2026-07-27 — Model-selection implementation verification
- **Result:** Implemented the reviewed plan without widening the review authority surface. Omitted `--model` leaves both native CLIs at their own configured default; explicit models are one `--model=<value>` argv token, validated before any marker activity, checked against conclusive local help only, and audited as `requested_model` after subprocess start.
- **Verification:** `python -m pytest tests/ -q` reported 37 passed; `python -m py_compile scripts/*.py tests/*.py`, both module help commands, and `git diff --check` passed. No live reviewer/model request was made.
