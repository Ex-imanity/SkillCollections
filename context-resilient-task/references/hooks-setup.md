# Automatic Hooks Setup

The MRS is always readable on disk, but reading it still depends on *someone
remembering to*. The auto-hooks close that gap: they make an agent rehydrate,
flush, and self-check the MRS at the right moments **without being asked**.

Three events, three scripts. All are **read-only by default**, **non-blocking**
(always exit 0), and **silent when no `.task-state/` exists** — so they are safe
to install once, globally, for every project.

| Event | Script | What it does |
|-------|--------|--------------|
| Session start / after `/clear` | `restore_context.py` | Prints a "Reconstructed Task State" block (goal, status, active todos, next action, artifacts, drift warning) so the fresh context starts oriented. |
| Before compaction | `precompact_digest.py` | Prints a minimal survival digest so the compaction summarizer keeps the essentials; the full state is already on disk. |
| End of turn (`Stop`) | `gate_check.py` | If the working tree drifted past the last snapshot, prints a reminder to update `snapshot.md` / `progress.md`. Never blocks. |

## Claude Code

Claude Code reads hooks from `settings.json`. Use the installer:

```bash
SKILL=~/.claude/skills/context-resilient-task   # or wherever this skill lives

# Global (recommended) — every project, ~/.claude/settings.json
python3 "$SKILL/scripts/install_hooks.py"

# Project-scoped — ./.claude/settings.json (committable, per-repo)
python3 "$SKILL/scripts/install_hooks.py" --project

# Preview without writing
python3 "$SKILL/scripts/install_hooks.py" --dry-run

# Remove (surgically removes only our hooks, keeps yours)
python3 "$SKILL/scripts/install_hooks.py" --uninstall
```

The installer:
- **merges** into existing `settings.json` (keeps your other keys and hooks);
- is **idempotent** (re-running never duplicates), and **atomic** (writes via a
  temp file, so a crash never leaves a truncated `settings.json`);
- **refuses** to touch invalid JSON (never clobbers a broken file);
- writes a **shell-portable** command: a bare launcher (`python3` on POSIX,
  `python` on Windows) + the absolute script path, with a `--tag
  crt-auto-hook:<Event>` marker so `--uninstall` removes exactly its own entries
  (and only those, even when a group also holds one of your hooks).

> After moving or reinstalling the skill, re-run the installer so the absolute
> paths point at the new location (re-running is safe — it refreshes in place).

### Cross-platform notes

The generated command deliberately contains **no shell operators** (`2>/dev/null`,
`; exit 0`, `#` comments), so the same string runs under every shell Claude Code
might use:

| OS | Hook shell | Works because |
|----|------------|---------------|
| macOS / Linux | `sh -c` | plain `python3 "…"` invocation |
| Windows (Git Bash present) | Git Bash (POSIX) | same as above |
| Windows (no Git Bash) | PowerShell | bare launcher is a command, not a quoted string; script path is a quoted arg |

Requirements / gotchas:
- **`python3` (POSIX) / `python` (Windows) must be on PATH** in the non-interactive
  shell. The scripts are stdlib-only, so any Python ≥ 3.8 works — it need not be
  the interpreter that ran the installer.
- Non-blocking is guaranteed by the **scripts** (they always exit 0 in `--hook`
  mode and print nothing to stderr), not by shell tricks — so dropping the
  operators is safe on the `Stop` hook.
- Windows without Git Bash: if hooks misbehave under PowerShell, install Git for
  Windows and set `CLAUDE_CODE_GIT_BASH_PATH` in `~/.claude/settings.json` to
  route hooks through Git Bash.

## Codex, Gemini CLI, and other agents

The scripts are plain, dependency-free Python that only read the MRS and print to
stdout, so any agent that can run a shell command and read the output is
compatible. The reliable, universal way to wire them is via the agent's
instruction file.

**AGENTS.md guidance (works everywhere — the recommended baseline).** Copy the
auto-recovery block from [`agents-md-snippet.md`](./agents-md-snippet.md) into the
project's `AGENTS.md` (or `GEMINI.md`). It instructs the agent to run
`restore_context.py` at the **start** of a session and `gate_check.py` **before
ending**. This is guidance the model follows, not enforced execution — but it
needs no agent-specific hook support and degrades gracefully.

**Codex native hooks (optional enhancement).** Recent Codex builds support their
own command hooks (e.g. `SessionStart`) that can run `restore_context.py`
directly, giving enforced execution instead of guidance. The exact config path
and each event's required output contract change between Codex versions — check
the current Codex docs before wiring them, and note that non-managed hooks
require a trust/review step. Do **not** use Codex's `notify` program for this: it
fires only on `agent-turn-complete` (post-turn) and passes a JSON argument these
scripts don't parse, so it cannot restore context at session start.

> Verified via a Codex self-review of these scripts (2026-07): the scripts are
> stdlib-only and agent-agnostic; the `notify`-at-session-start approach is not
> feasible; AGENTS.md guidance and native `SessionStart` hooks are.

## Design choices

- **Read-only.** Hooks never rewrite `snapshot.md`; keeping snapshots accurate
  stays the agent's deliberate act. Auto-generation would risk overwriting a
  careful snapshot with a heuristic one.
- **Non-blocking Stop.** `gate_check.py` reminds but never prevents ending a
  turn (`exit 0`). A blocking gate is easy to get wrong and annoying when it does.
- **Drift = source only.** Changes confined to `.task-state/`, `.omc/`, or
  `.git/` are the agent's own bookkeeping and never count as drift.
- **Minimal event set.** Only `SessionStart`, `PreCompact`, `Stop` — the three
  moments where context is actually lost or flushed. No per-prompt or per-edit
  hooks, to keep the transcript quiet.
