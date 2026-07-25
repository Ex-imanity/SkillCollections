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
