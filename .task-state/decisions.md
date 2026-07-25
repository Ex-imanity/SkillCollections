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
