# ClaudeCode → Codex adapter

**Primary path (distributable, no plugin dependency):** the repo-owned direct
adapter `scripts/claude_to_codex.py`, wrapping
`codex exec --sandbox danger-full-access --dangerously-bypass-approvals-and-sandbox --json --output-last-message`. It enforces the
same protocol guards as the codex→claude adapter (fail-closed, fixed started
attempt and successful-review caps, redaction, result-based readiness, hardcoded unattended full access) and
parses the `--json` stream for real `thread_id` / token-usage provenance. Run
`python -m scripts.claude_to_codex --help`. This is the route
the skill ships with, so it works for users who never installed the plugin.

**Optional fallback (only if already installed):** the official Codex plugin
(`/Users/gaotu/.claude/plugins/cache/openai-codex/codex/1.0.6`). Use it only
for its job/session conveniences; do NOT depend on it for distribution and do
NOT reimplement its broker. Note the 2026-07-22/-24 evidence that plugin jobs
stalled in a restricted sandbox — the direct adapter also avoids that. The
mapping below documents the optional plugin path.

## Review-type → command mapping

| Review need | Command | Notes |
|---|---|---|
| Code implementation defects | `/codex:review` | git-diff scoped (`--scope auto\|working-tree\|branch`, `--base <ref>`); review-only; returns Codex output verbatim. |
| Approach / design / tradeoff challenge ("is this the right design?") | `/codex:adversarial-review` | Positioned as a challenge review of assumptions and design, not just stricter defect-finding; also git-state scoped. |
| Open-ended plan/doc investigation that cannot be expressed through the review commands | `/codex:rescue` (`codex:codex-rescue` subagent) | Exceptional fallback only. NOT review-only — it may propose/apply fixes. The primary MUST constrain it to review-only in the prompt and treat its output as advisory. |
| Hand the current session to Codex to continue | `/codex:transfer` | Session handoff, not a review. Preserve the returned `codex resume <id>`. |

**Hard routing constraint:** plan, approach, and design review MUST default to
`/codex:adversarial-review`. The primary MUST NOT default to `/codex:rescue`.
Use `rescue` only when the work requires cross-repo, non-diff investigation
that the review commands cannot express; always frame it review-only and treat
the result as advisory.

## Safety constraints (this direction)

- Choose `--background` or `--wait` explicitly; avoid interactive stalls.
- Record the returned Codex session id for later cross-check.
- Keep the plugin's long-loop review gate **disabled by default** (README warns it can create runaway Claude/Codex loops and drain usage).
- The primary verifies each finding against evidence before applying — no blind acceptance.
- Do not chain a Codex review that itself calls ClaudeCode back (no recursion).
- A review-only plugin job is launched with `write=false`. Do not require that reviewer to create `Review/ByCodex/*.md`; require the full review in its final result, retrieve it with `/codex:result`, and let the primary persist it verbatim with the plugin job id and Codex thread id.

## Evidence this direction already runs

- `/Users/gaotu/.claude/projects/-Users-gaotu-PycharmProjects-SkillCollections/62f44f55-78c3-42ad-b20e-abba93d4b109/subagents/agent-a3391206f5975fbcd.jsonl#record_index=6` — CC invoking Codex review via `codex-companion.mjs task`.
- Resulting Codex review thread: `/Users/gaotu/.codex/sessions/2026/07/19/rollout-2026-07-19T17-25-47-019f79b2-29af-7590-a0a3-0a3f12e8de51.jsonl#record_index=9`.
- 2026-07-22 reverse review job `task-mruvbers-v57cv7` confirmed the write boundary: analysis completed with verdict `REQUEST CHANGES`, but its `write=false` sandbox rejected repository review-file creation. The primary must own persistence.
