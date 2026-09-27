# Automatic Hooks Setup

The MRS is always readable on disk, but reading it still depends on *someone
remembering to*. The auto-hooks close that gap: they make an agent rehydrate,
flush, and self-check the MRS at the right moments **without being asked**.

Three events, three scripts. All are **read-only by default**, **non-blocking**
(always exit 0), and **silent when no `.task-state/` exists** — so they are safe
to install once, globally, for every project.

| Event | Script | What it does |
|-------|--------|--------------|
| Session start / after `/clear` | `restore_context.py` | Prints a "Reconstructed Task State" block (goal, status, active todos, next action, artifacts, drift warning, in-flight superpowers ledgers) so the fresh context starts oriented. |
| Before compaction | `precompact_digest.py` | Prints a minimal survival digest (including the newest superpowers ledger tail) so the compaction summarizer keeps the essentials; the full state is already on disk. |
| (all three) | | In a linked git worktree, the MRS of the main checkout is shared, while drift and superpowers ledgers are read from the current worktree. `restore_context.py <dir> --mrs <mrs_dir>` restores one chosen MRS. |
| End of turn (`Stop`) | `gate_check.py` | If the working tree drifted past the last snapshot, or a superpowers ledger advanced past it on a clean tree, prints a reminder to update `snapshot.md` / `progress.md`. Never blocks. |

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

## Codex

Codex reads project-native hooks from `.codex/hooks.json`. Use the same installer
with `--codex`:

```bash
SKILL=~/.codex/skills/context-resilient-task

# Project-scoped (Codex hook definitions are project-local)
python3 "$SKILL/scripts/install_hooks.py" --codex

# Preview without writing / remove only this skill's hooks
python3 "$SKILL/scripts/install_hooks.py" --codex --dry-run
python3 "$SKILL/scripts/install_hooks.py" --codex --uninstall
```

The installer merges into an existing `.codex/hooks.json`, is idempotent, and
uses atomic writes. It installs `SessionStart`, `PreCompact`, and `Stop`; Codex
will request trust approval before executing newly added definitions. Moving the
skill requires re-running the installer so the embedded absolute paths refresh.

## Grok

Grok discovers hooks from `~/.grok/hooks/*.json` (global, always trusted) and
`<project>/.grok/hooks/*.json` (project, requires folder trust). Use `--grok`:

```bash
SKILL=~/.grok/skills/context-resilient-task   # or wherever this skill lives

# Global (recommended) — ~/.grok/hooks/context-resilient-task.json
python3 "$SKILL/scripts/install_hooks.py" --grok

# Project-scoped — ./.grok/hooks/context-resilient-task.json
python3 "$SKILL/scripts/install_hooks.py" --grok --project

# Preview / uninstall
python3 "$SKILL/scripts/install_hooks.py" --grok --dry-run
python3 "$SKILL/scripts/install_hooks.py" --grok --uninstall
```

The installer writes a dedicated hook file (not merged into unrelated Grok
config), is idempotent, atomic, and sets `timeout: 30` on each command (Grok's
default observe-hook timeout is 5s). Uninstall removes only our
`crt-auto-hook:` entries; if the dedicated file becomes empty it is deleted.
`$GROK_HOME` is honored when set. The hook scripts start discovery from the
current directory; when no MRS is found there they fall back to
`$GROK_WORKSPACE_ROOT`, then `$CLAUDE_PROJECT_DIR`, which Grok sets for every
hook, so the hooks still find the project if Grok spawns them elsewhere. Project hooks need `/hooks-trust` (or
`--trust`) once per repo.

**Grok also scans Claude Code hooks** when `[compat.claude] hooks = true`
(default), so a Claude Code install already reaches Grok. Grok deduplicates
identical handlers across sources; with both installs present, `grok inspect`
lists each CRT hook once, from `~/.grok/hooks`. Check `grok inspect` after
installing; native `--grok` is the
right choice for Grok-only setups.

**Context-injection limit:** Grok treats `SessionStart` / `PreCompact` as
passive events and **does not inject hook stdout into the model context** (see
Grok Hooks guide, Passive Hooks). The scripts still run (useful for side
effects and scrollback), but the model will not automatically "see" the
reconstructed state the way Claude Code does. Mitigations:

1. Keep the AGENTS.md auto-recovery block so the model runs `restore_context.py`
   at session start when needed.
2. `Stop` → `gate_check.py` still runs, but Grok reads Stop stdout only as a JSON
   decision; plain-text output means "allow the stop", so the reminder is not
   shown to the model. The skill keeps it that way on purpose: returning
   `additionalContext` or `block` would keep the agent working for another
   round, which contradicts the non-blocking design.
3. After `/clear` or a new session, you can still ask the agent to restore, or
   run `python <skill-root>/scripts/restore_context.py` yourself.

## Gemini CLI and other agents

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

Codex and Grok users should use the native installers above. Do **not** use
Codex's `notify` program for this: it fires only on `agent-turn-complete`
(post-turn) and cannot restore context at session start.

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
