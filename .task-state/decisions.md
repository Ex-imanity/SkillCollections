# Decisions

<!--
Append-only log of stable conclusions and design decisions.

Rules:
- New entries go at the BOTTOM of the file.
- Never edit or remove past entries (except to fix typos).
- This file is the destination for "Latest Stable Conclusions" content.
  NEVER append such content to task_state.md.
- Required when: multi-session, multi-agent, or >10 phases. Optional otherwise.

Entry shape (copy below the "## Entries" marker):

  ## YYYY-MM-DD: <short title>
  - **Decision:** <what was decided>
  - **Reason:** <why>
  - **Source:** <session id, artifact reference, or user confirmation>
-->

## Entries

<!-- Append new entries below this line. -->

## 2026-07-25: Fixed review-attempt accounting
- **Decision:** Use fixed limits of two started calls and two successful reviews per artifact; reserve an attempt immediately before entering either reviewer subprocess.
- **Reason:** The old caller-controlled `max_rounds` and success-only counter allowed unbounded potentially billable failure retries.
- **Source:** P1 assessment and `cross-agent-review/tests/test_review_limits.py`.

## 2026-07-25: Budget contract is direction-specific
- **Decision:** Require a positive `--max-budget-usd` for Codex-to-ClaudeCode calls. Document the reverse route as requiring explicit user approval, timeout, and attempt cap because Codex exposes no equivalent USD cap.
- **Reason:** Do not claim a mechanical monetary limit that the provider CLI cannot enforce.
- **Source:** Protocol budget requirement and current Codex CLI contract.

## 2026-07-25: P1 review call approval
- **Decision:** Invoke one Codex-to-ClaudeCode review gate with `--max-budget-usd 2`.
- **Reason:** The user explicitly approved a $2 maximum for this review.
- **Source:** User message in the active task.

## 2026-07-25: Fail closed after Codex-subprocess 403
- **Decision:** Do not retry the Codex-to-ClaudeCode adapter automatically and do not mutate authentication. Continue only through the persisted handoff in an interactive ClaudeCode context.
- **Reason:** The protocol treats the actual reviewer result envelope as authoritative and explicitly prohibits auth mutation or fabricated review output.
- **Source:** `Review/ForClaudeCode/handoff-cross-agent-review-p1-20260725.md`.

## 2026-07-25: Interactive review result is artifact evidence
- **Decision:** Accept `Review/ByClaudeCode/cross-agent-review-p1.md` as the interactive handoff's review artifact, but do not increment adapter success counts or call it a verified adapter result.
- **Reason:** The adapter did not receive a success envelope or execute `persist_success`; the review file accurately declares its interactive origin.
- **Source:** `Review/ByClaudeCode/cross-agent-review-p1.md`.

## 2026-07-25: Disposition of ClaudeCode review N1-N4
- **Decision:** Implement N1; add the missing N2 regressions; document N3; retain N4 as a declared live-provider test limitation.
- **Reason:** N1 was reproducibly unsafe before the subprocess boundary, N2 and N3 were valid coverage/documentation omissions, and N4 cannot be made truthful without a successful provider-backed gate.
- **Source:** `Review/ByClaudeCode/cross-agent-review-p1.md` and `cross-agent-review/tests/test_review_limits.py`.

## 2026-07-25: Do not install after failed Codex-environment probe
- **Decision:** Do not install the P1 bundle as provider-validated and do not retry the provider call automatically.
- **Reason:** A fresh authorized direct probe reached the configured base URL but received pre-model 403 with zero token usage; the authentication/authorization boundary remains unresolved.
- **Source:** Direct `claude -p` probe in the Codex environment under the user's `$2` authorization.

## 2026-07-25: 403 root cause = host-process credential resolution, not a bad token
- **Decision:** Classify the Codex-environment 403 as a credential-resolution difference between host processes. The `~/.claude/settings.json` token is valid and works from the interactive ClaudeCode host via both the settings-file and env-injection paths; under the Codex host the child `claude -p` does not apply that settings.json and sends a foreign/stale token the proxy rejects.
- **Reason:** Interactive host runs the byte-exact command successfully; settings.json `env` overrides process env (Tests B/C); a no-credential run returns "Not logged in", not 403 (Test E), so Codex sent a wrong credential rather than none.
- **Source:** `Review/ByClaudeCode/codex-environment-403-diagnosis-result.md`; findings.md 2026-07-25 10:20.

## 2026-07-25: Deterministic child-credential remedy (proposed, primary-owned)
- **Decision:** The smallest fix is to make the adapter's child credential host-independent: in `codex_to_claude.resolve_subprocess_env` (settings-env branch), set a fresh empty `CLAUDE_CONFIG_DIR` for the child and inject the settings.json `ANTHROPIC_BASE_URL/AUTH_TOKEN` into the child env, rather than popping them and relying on the child re-reading settings.json. Codex (primary) applies it; a fresh budget-approved gate verifies it.
- **Reason:** Test D (empty config dir + injected good token → success) proves the shape authenticates and it covers all inferred sub-cases (foreign env token, remapped HOME/CLAUDE_CONFIG_DIR, sandboxed settings read). No token is written to disk.
- **Source:** Diagnosis experiments A–F; `Review/ByClaudeCode/codex-environment-403-diagnosis-result.md`.

## 2026-07-25: Deterministic child-credential remedy implemented
- **Decision:** Apply the proposed settings-env remedy: pass a fresh temporary `CLAUDE_CONFIG_DIR` and explicitly inject the credentials read from the selected settings file, then remove the temporary directory after the reviewer subprocess ends.
- **Reason:** The Codex host does not reliably apply the same Claude settings configuration as the interactive host; the test-proven explicit path removes that host-dependent behavior without persisting a credential.
- **Source:** `Review/ByClaudeCode/codex-environment-403-diagnosis-result.md` and `tests/test_review_limits.py`.

## 2026-07-25: Stop adapter retries after post-remedy host 403
- **Decision:** Do not spend the second attempt for the verification artifact automatically. Move investigation to a normal-terminal versus Codex-host runtime comparison.
- **Reason:** The provider still returned pre-model 403 after the OS child was independently shown to contain the intended credentials and config directory; retrying without a changed host condition would not distinguish another cause.
- **Source:** `Review/ForClaudeCode/handoff-codex-credential-remedy-verification-20260725.md` and post-remedy environment trace.

## 2026-07-25: Supersede wrong-token diagnosis with provider User-Agent rejection
- **Decision:** Treat the gateway's rejection of Claude Code print mode's official `sdk-cli` User-Agent as the root cause. Do not claim that Codex sends a wrong token, and do not impersonate `claude-vscode` in the adapter.
- **Reason:** Local request capture proves the transmitted bearer token hash matches settings exactly. Same-token invalid-body probes differ only by User-Agent: `sdk-cli` is rejected at authentication (`403`), while a truthful plain Claude CLI identity reaches request validation (`400`).
- **Source:** 2026-07-25 local HTTP header capture and no-model provider A/B; `.task-state/findings.md` 11:14 entry.

## 2026-07-25: Use a strict truthful CLI identity as an explicit gateway fallback
- **Decision:** Keep the default Claude Code `sdk-cli` identity. When this gateway returns the diagnosed pre-model 403 and the user approves, allow only `--claude-user-agent claude-cli/<semantic-version>` in the child process; reject IDE identities and arbitrary headers before an attempt is reserved.
- **Reason:** The real compatibility gate succeeded, while strict validation preserves an honest client identity and prevents the workaround from becoming a general header-injection or impersonation channel. Provider allowlisting of `sdk-cli` remains preferred.
- **Source:** `Review/ByClaudeCode/codex-sdk-cli-user-agent-verification.md` (`APPROVE WITH NITS`) and 12-test TDD verification.

## 2026-07-25: Install the verified SkillCollections bundle
- **Decision:** Synchronize the verified `cross-agent-review/` candidate into `/Users/gaotu/.cc-switch/skills/cross-agent-review`, including its bundled tests, while excluding `.omc` and Python caches.
- **Reason:** The installed copy was stale relative to the repo-staged P1 fixes and the now-verified gateway compatibility implementation; installation-path tests and file parity passed after synchronization.
- **Source:** Installed-copy `py_compile`, 12/12 unittest result, and recursive source/install comparison.

## 2026-07-25: Derive the gateway compatibility identity from the executing CLI
- **Decision:** Replace the caller-supplied `--claude-user-agent` value with explicit `--gateway-compat-cli-identity`. When approved, the adapter resolves local `claude`, reads its semantic version through `--version`, derives the plain `claude-cli/<version>` header, and invokes the review through that same resolved binary.
- **Reason:** Regex validation alone could not establish that a user-provided version described the binary actually making the request. Derivation removes that truthfulness gap while preserving an explicit, narrow, child-only fallback.
- **Source:** User request for robust local CLI discovery; `tests/test_review_limits.py` RED/GREEN evidence; local capability report.

## 2026-07-25: Capability discovery is diagnostic, not auto-routing
- **Decision:** Ship `scripts.runtime_capabilities` with an explicit catalog of known agent CLI names. Only `claude` and `codex` are marked as supported review routes; other discovered CLIs are reported but never used automatically.
- **Reason:** A generic executable scan cannot safely infer a review protocol, permissions, result envelope, or cost contract for a different agent. Reporting availability and version retains useful local compatibility evidence without widening authority.
- **Source:** User request for best-compatible local agent discovery; `tests/test_runtime_capabilities.py`.

## 2026-07-26: Cross-platform file lock instead of POSIX-only fcntl
- **Decision:** Bind `fcntl` (POSIX) / `msvcrt` (Windows) conditionally and route the marker lock through `_lock_exclusive`/`_unlock`; fail closed (raise `OSError`) on a platform with neither, never silently skip serialization.
- **Reason:** The unconditional top-level `import fcntl` crashed both adapters at import on Windows (the reverse adapter imports from the forward one), making the skill unusable for any Windows installer despite docs claiming only the two CLIs as dependencies.
- **Source:** Phase 8 compatibility review; `tests/test_review_limits.py::CompatibilityTests` (portable lock + fail-closed-when-no-primitive); Windows-simulation smoke test.

## 2026-07-26: `inherited` credential source for non-proxy installers
- **Decision:** When neither settings.json nor injected env supplies both proxy keys, `check_readiness` returns `inherited` (not `missing`), and the child runs with ambient auth and the default `CLAUDE_CONFIG_DIR` (no temp-dir override, no proxy injection). Auth truth is still decided on the real result envelope.
- **Reason:** The proxy-only readiness gate made the forward direction unusable for the majority of installers who use official Claude auth (subscription OAuth or `ANTHROPIC_API_KEY`), even though `claude -p` would work with inherited auth. An unauthenticated CLI still classifies as `auth_failure` and fails closed, so no guarantee is weakened.
- **Source:** Phase 8 compatibility review; `tests/test_review_limits.py::CompatibilityTests` (inherited fallback + gate runs without injecting proxy env under a cleaned environment).

## 2026-07-26: Opt-in `--max-budget-usd` preflight, plus doctor reporting
- **Decision:** Add `claude_supports_max_budget()` (a `--help` probe returning True/False/None). The forward gate runs the preflight ONLY when the caller injects a help runner (the CLI does; hermetic unit tests do not); a conclusive "unsupported" fails closed with an upgrade message before reserving an attempt; inconclusive never blocks. The doctor reports `max_budget_supported`.
- **Reason:** `--max-budget-usd` is a required forward flag but a relatively new `claude` feature; older CLIs otherwise fail with a cryptic non-success envelope. Opt-in keeps existing hermetic tests from making real subprocess calls.
- **Source:** Phase 8 compatibility review; `tests/test_review_limits.py::CompatibilityTests` (probe True/False/inconclusive; gate fails closed without starting the subprocess).

## 2026-07-26: Tolerant-but-fail-closed codex provenance extraction
- **Decision:** Parse the codex `--json` stream with source-verified primary names first (`thread.started.thread_id`, `turn.completed.usage.input_tokens/output_tokens`), then defensive fallbacks (camelCase ids, `prompt_tokens`/`completion_tokens`, `token_usage`), using exact-key matching only. Capture the verified optional `cached_input_tokens`/`reasoning_output_tokens` for telemetry. Keep the fail-closed rule (real id + real non-negative token pair required; never fabricate) and record observed event types in the `provenance_failure` detail for diagnosis.
- **Reason:** The prior parser pinned one probe-date schema; a future codex rename would silently break every reverse gate. Codex source-verified rust-v0.144.1 (this host) confirming the primary names, the real optional fields, and that the stream is unversioned with documented historical item-field drift.
- **Source:** Phase 8; Codex source verification of `rust-v0.144.1` `codex-rs/exec/src/exec_events.rs`; `tests/test_review_limits.py::CodexProvenanceTests`.
- **SUPERSEDED by the 2026-07-26 review-round decision below:** the "defensive fallbacks participate in extraction" part was over-broad and is replaced by verified-only-gates-success + diagnostic-only aliases.

## 2026-07-26: Resolve Codex review round 1 (verified-only provenance; strict Windows lock; protocol sync)
- **Decision (P1 — provenance):** Only the source-verified paths gate a successful review — session id ONLY from a `thread.started` event's `thread_id`, usage ONLY from a `turn.completed` event's `usage.{input_tokens,output_tokens}`. Conventional alias names (`session_id`/camelCase ids, `prompt_tokens`/`completion_tokens`, `token_usage`) NO LONGER flip a `provenance_failure` into success; they are collected as diagnostic `drift_hints` and surfaced in the failure detail so a human can extend the verified contract WITH fresh source evidence. Verified optional `cached_input_tokens`/`reasoning_output_tokens` still captured for telemetry.
- **Decision (P2 — Windows lock):** `_lock_exclusive` retries the non-blocking `msvcrt.locking` ONLY on a genuine contention errno (`EDEADLOCK`/`EDEADLK`); any other `OSError` (EACCES/EINVAL/EBADF) propagates so the gate fails closed instead of spinning forever.
- **Decision (P2 — protocol sync):** Updated `references/cross-agent-review-protocol.md` (the declared authoritative source) to add the `inherited` credential step and the verified-only-with-diagnostics provenance rule, matching SKILL.md/README.
- **Reason:** Codex main-session review (2026-07-26) correctly flagged that (1) accepting unverified aliases as success would persist an unverified review — violating the "only verified provenance" guarantee; (2) retrying all `OSError` turns a non-contention failure into an infinite hang instead of the documented fail-closed; (3) the authoritative protocol doc still described the old proxy-only `missing` credential rule and strict codex fields, contradicting the new implementation.
- **Source:** Codex review findings (screenshot, 2026-07-26); `tests/test_review_limits.py::CodexProvenanceTests::test_alias_shapes_do_not_flip_failure_to_success`, `::CompatibilityTests::test_windows_lock_retries_only_on_contention` / `::test_windows_lock_reraises_non_contention_error`; 31/31 passing.

## 2026-07-26: Defer real Windows lock validation
- **Decision:** Accept the mock-backed Windows lock tests for this release and defer a real Windows smoke/CI run until a Windows usage scenario exists.
- **Reason:** The reviewed implementation retries only `EDEADLOCK`/`EDEADLK` contention and re-raises all other `OSError` values, so it fails closed. The remaining uncertainty is platform-runtime behavior, not a known correctness defect; the user explicitly accepted the deferral.
- **Source:** User direction in the active task; Codex re-review with 31 passing local tests.

## 2026-07-27: Reviewed model-selection boundary
- **Decision:** Add a common optional `--model` parameter for both review adapters. It is omitted by default, validated as an opaque identifier (empty, leading `-`, ASCII control characters, and length greater than 128 rejected), emitted as a single `--model=<value>` argv token, and audited as `requested_model` only after a reviewer subprocess starts. Do not expose arbitrary provider configuration, profiles, reasoning knobs, permissions, or sandbox settings.
- **Reason:** Both current native CLIs advertise `--model`; a bounded opaque identifier retains gateway/provider compatibility without a stale allowlist or argv passthrough. The single-token form removes option-like-value ambiguity. Codex's `--model` is sufficient model selection; profile/config are not required and could bypass safety boundaries.
- **Cost policy:** Claude-direction selection remains bounded by required `--max-budget-usd`. Codex-direction selection has no provider USD ceiling, so model choice remains governed by explicit user approval, fixed attempt cap, and timeout. Add an injected, inconclusive-safe `--help` flag preflight only when a model is supplied; it detects an absent CLI flag but never asserts a particular model is available.
- **Source:** `Review/ByClaudeCode/2026-07-27-cross-agent-review-model-selection-plan-review.md` (`APPROVE WITH NITS`); local CLI help and official CLI documentation queried on 2026-07-27.
