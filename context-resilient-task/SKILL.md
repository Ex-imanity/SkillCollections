---
name: context-resilient-task
description: Context-resilient task management via a filesystem Minimum Recovery Set (MRS in .task-state/). Reconstructs task state from on-disk artifacts so work survives /clear, session interruption, agent switches, and context-window loss. Use this skill whenever the user mentions multi-phase tasks, multi-session work, cross-session recovery, task state restoration, MRS, .task-state, lost context, hallucinated todos, forgotten work, 任务状态恢复, 跨会话任务, 多会话开发, 上下文丢失, /clear 后继续, 任务恢复, or asks the agent to remember a task across sessions. Also trigger proactively when starting any task likely to span more than one session, even if the user doesn't explicitly request recovery — the upfront MRS structure prevents context-loss surprises later.
---

# Context-Resilient Task

> **Context is not input, it's output.** Never rely on conversational memory. Always reconstruct task state from artifacts on disk.

## File Authority

- **`task_state.md`** — Source of truth. Always update **in-place** (edit existing fields). Never append dated sections.
- **`progress.md`** — Append-only chronological log. Never overwrite.
- **`snapshot.md`** — Latest checkpoint. **Overwrite** entire file on each update (archive previous first).
- **`decisions.md`** — Stable conclusions and decisions. Append-only. Required for long tasks (see Tier 1 below).
- On conflict between files, `task_state.md` wins.

## Minimum Recovery Set (MRS)

### Tier 0: Core Required (MUST exist)
- `task_state.md` — Current state (in-place updated, Active Todos in header)
- `plan.md` — Task plan + Plan Registry
- `snapshot.md` — Latest checkpoint (overwrite, not append)

**If missing:** STOP, run initialization wizard.

### Tier 1: Important Context (SHOULD exist)
- `findings.md` — Research and discoveries
- `progress.md` — Session execution log (append-only)
- `architecture.md` — Architecture (for system-level tasks)
- `decisions.md` — Stable conclusions/decisions (**required** when: multi-session, multi-agent, or >10 phases; otherwise optional)

**If missing:** WARN, ask user to confirm continuation.

### Tier 2: Optional Context (MAY exist)
- `blockers.md` — Current blockers
- Domain-specific artifacts

**If missing:** No action, continue normally.

Full MRS specification: [references/minimum-recovery-set.md](references/minimum-recovery-set.md)

## On-Invoke Detection

```
1. Discover MRS: walk up from CWD; collect `.task-state/` and `.task-state-<slug>/`
   at the first ancestor level where any exist (run: `python <skill-root>/scripts/list_mrs.py`)
2. If 0 MRS found → Initialization mode
3. If 1 MRS found → use it; proceed to step 5
4. If >1 MRS found → ASK user which task to resume
   - List each with goal/status/updated timestamp
   - Recommend most recently updated (*) but never assume
5. Scan selected MRS for Tier 0 files
6. If status=completed → Skip recovery, prompt archival
7. If all Tier 0 present → Recovery mode
8. If any Tier 0 missing → Initialization mode
9. Check Tier 1, emit warnings if missing
10. Output "Reconstructed Task State"
11. Continue from last checkpoint
```

Task lifecycle: `active` → `paused` / `blocked` → `active` → `completed`

For parallel/interrupted tasks (multiple MRS in one project), see [references/multi-task-workflow.md](references/multi-task-workflow.md).

## Structured Output Template

At key checkpoints (recovery, phase transition, major decision, status request, error/blocker), output:

```markdown
## Reconstructed Task State
### Goal
(from artifact: task_state.md)
### What Has Been Done
- <action> (source: <filename>)
### Current Artifacts
- <filename> (last updated: <timestamp>)
### Unknown / Missing
- <info not in artifacts>
### Next Required Action
<single concrete step>
### Artifact to Be Produced
<filename> - <purpose>
```

Full template specification: [references/output-template.md](references/output-template.md)

## Anti-Hallucination Rules

1. **Source Attribution:** Every fact cites source file
2. **Explicit Unknowns:** If not in artifacts, mark "Unknown"
3. **No Inference:** Don't fill gaps with assumptions
4. **Single Next Action:** Only one concrete step at a time
5. **Output Artifact:** Every action produces/updates an artifact

## Todo Management

`task_state.md` maintains two sections as the **only** authoritative source for todos:

- **Active Todos** — Located near the **top of the file** (immediately after Status), ensuring recovery always reads them first.
- **Completed Items** — Single-line summaries only. Details belong in `progress.md`.

Rules: completing a todo = remove from Active, append to Completed. Never infer status from `progress.md`. Each todo is a single line; detailed context references external files.

Full rules: [references/artifact-standards.md](references/artifact-standards.md)

## Failure Modes

| Condition | Severity | Action |
|---|---|---|
| Missing Tier 0 file | STOP | Run initialization wizard |
| Missing Tier 1 file | WARN | Ask user to confirm continuation |
| Stale snapshot (>7 days) | WARN | Offer to regenerate |
| Conflicting artifacts | STOP | Ask user which is correct |
| Task completed | PROMPT | Offer archive / new task / reopen |

Full failure mode details: [references/recovery-workflow.md](references/recovery-workflow.md)

## Initialization Wizard

If Tier 0 missing, run the bundled script (CLI or interactive):

```bash
# CLI form
python <skill-root>/scripts/init_mrs.py \
  --dir .task-state \
  --goal "Build payment service" \
  --complexity medium \
  --requirements "Stripe integration;3DS handling;Webhook verifier"

# Interactive form (omit --goal/--complexity to be prompted)
python <skill-root>/scripts/init_mrs.py
```

Behavior:
1. Collects: Task Goal, Complexity (small/medium/large), Key Requirements (optional)
2. Renders Tier 0 from templates: `task_state.md`, `plan.md`, `snapshot.md`
3. Creates empty Tier 1 core logs: `findings.md`, `progress.md`
4. Auto-creates `decisions.md` if `--complexity large`, `--multi-agent`, or >10 requirements
5. Refuses to write into a non-empty target unless `--force`
6. **Reminds you to copy MRS rules to project AGENTS.md** for Codex/other agent compatibility (see [references/agents-md-snippet.md](references/agents-md-snippet.md))

If you prefer manual setup, copy templates from `assets/` (`task_state.template.md`, `plan.template.md`, `snapshot.template.md`, `decisions.template.md`) and fill the `{...}` placeholders.

## Plan Registry

`plan.md` must include a Plan Registry tracking all `docs/plans/*.md` files:

```markdown
## Plan Registry (docs/plans)
| File | Source Skill | Date | Status |
|------|-------------|------|--------|
```

**Strict boundary:** Only register files under `docs/plans/*.md`. Do NOT register CLAUDE.md, AGENTS.md, `.task-state/*`, or `docs/runbooks/*`.

Full cross-skill protocol: [references/multi-skill-integration.md](references/multi-skill-integration.md)

## File Standards

| File | Update Trigger | Method |
|------|----------------|--------|
| task_state.md | Phase transition, decision, todo change | **In-place edit**. Compress if >300 lines. |
| plan.md | Phase status change, new plan file | **In-place edit** (Registry append) |
| snapshot.md | Phase complete, blocker, major decision, session end | **Overwrite** (archive previous) |
| decisions.md | Stable conclusion reached | **Append only** |
| findings.md | After discoveries | **Append only** |
| progress.md | After each significant action | **Append only** |

**Forbidden paths:** `/.cursor/`, `/agent-tools/`, `/temp/`, `/tmp/`, `/.cache/`

Full standards: [references/artifact-standards.md](references/artifact-standards.md)

## Scripts

Locate scripts relative to this SKILL.md.

```bash
# Initialize a fresh MRS (CLI or interactive)
python <skill-root>/scripts/init_mrs.py --dir .task-state \
    --goal "..." --complexity medium --requirements "a;b;c"
python <skill-root>/scripts/init_mrs.py                       # interactive wizard

# Check MRS health
python <skill-root>/scripts/verify_mrs.py .task-state
python <skill-root>/scripts/verify_mrs.py --json .task-state  # JSON for agents

# List all MRS directories discoverable from CWD
python <skill-root>/scripts/list_mrs.py
python <skill-root>/scripts/list_mrs.py --json  # JSON for agents

# Generate snapshot (overwrites snapshot.md)
python <skill-root>/scripts/generate_snapshot.py .task-state
python <skill-root>/scripts/generate_snapshot.py .task-state --project-root .  # explicit source scan root
python <skill-root>/scripts/generate_snapshot.py --archive .task-state  # also archive

# Auto-hook scripts (read-only, non-blocking, silent when no MRS) — see Automatic Hooks below
python <skill-root>/scripts/restore_context.py     # rehydrate task state (session start / after /clear)
python <skill-root>/scripts/precompact_digest.py   # survival digest before compaction
python <skill-root>/scripts/gate_check.py          # remind to flush state if the tree drifted
python <skill-root>/scripts/install_hooks.py       # install into Claude Code settings.json
python <skill-root>/scripts/install_hooks.py --codex  # install into .codex/hooks.json
```

All scripts read templates from `assets/` so the rendered MRS files always match the documented schema. When the snapshot target is `.task-state` or `.task-state-<slug>`, `generate_snapshot.py` scans that directory's parent project for recently modified source files unless `--project-root` is provided.

## Automatic Hooks (optional)

Reading the MRS still depends on *remembering to*. The auto-hooks make an agent
rehydrate, flush, and self-check the MRS at the right moments unprompted. All are
read-only, non-blocking (exit 0), and **silent when no `.task-state/` exists**, so
a single global install is safe for every project.

| Event | Script | Effect |
|-------|--------|--------|
| Session start / after `/clear` | `restore_context.py` | Prints "Reconstructed Task State" so a fresh context starts oriented |
| Before compaction | `precompact_digest.py` | Surfaces a survival digest the summarizer should keep |
| End of turn (`Stop`) | `gate_check.py` | Reminds (never blocks) when the tree drifted past the last snapshot |

**Claude Code:** `python <skill-root>/scripts/install_hooks.py` (add `--project` to
scope to one repo, `--uninstall` to remove, `--dry-run` to preview). Merges into
`settings.json`, idempotent, refuses invalid JSON.

**Codex:** `python <skill-root>/scripts/install_hooks.py --codex` installs the
same three hooks into the current project's `.codex/hooks.json`. Add `--dry-run`
to preview or `--uninstall` to remove only these hooks. Codex will request trust
approval for new hook definitions.

**Codex / Gemini / other agents:** wire the same scripts via `AGENTS.md` — see the
auto-recovery block in [references/agents-md-snippet.md](references/agents-md-snippet.md).

Full details: [references/hooks-setup.md](references/hooks-setup.md).

## Codex / Multi-Agent Compatibility

When initializing MRS for a project that uses multiple agents (Claude Code, Codex, etc.):

1. Copy the content of [references/agents-md-snippet.md](references/agents-md-snippet.md) into the project's root `AGENTS.md`
2. This ensures all agents follow the same MRS update rules regardless of whether they have access to this skill

## Best Practices

**DO:**
- Update `task_state.md` in-place; keep Active Todos near the top
- Append to `progress.md` for every action
- **Overwrite** `snapshot.md` on key events (never append sections)
- Append stable conclusions to `decisions.md` (not `task_state.md`)
- Cite source files in all statements
- Register every new `docs/plans/` file in Plan Registry immediately
- Compress `task_state.md` when it exceeds 300 lines

**DON'T:**
- Rely on conversational memory
- Append dated sections to `task_state.md` (use `progress.md` / `decisions.md`)
- Leave completed todos in Active Todos list
- Infer todo status from `progress.md`
- Put non-plan files in Plan Registry
- Use forbidden temp paths
