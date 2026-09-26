# Multi-Skill Integration Guide

How `context-resilient-task` coordinates with other skills that produce plan files — chiefly
the superpowers workflow (`brainstorming` → `writing-plans` → `subagent-driven-development` /
`executing-plans` → `finishing-a-development-branch`). Both superpowers ≤ 4.x and ≥ 5.0 are
supported; the only differences that matter here are where files land and the 6.x ledger.

## Plan Roots by superpowers Version

| superpowers | brainstorming (design/spec) | writing-plans (implementation plan) |
|-------------|-----------------------------|-------------------------------------|
| ≤ 4.x | `docs/plans/YYYY-MM-DD-<topic>-design.md` | `docs/plans/YYYY-MM-DD-<feature>.md` |
| ≥ 5.0 | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` | `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` |

The default plan roots are therefore `docs/plans/`, `docs/superpowers/specs/` and
`docs/superpowers/plans/`. A project may hold all three (old plans kept, new ones added) — register
each file where it actually lives; never move old plans to match the new layout.

superpowers lets the user relocate plans and specs. When a project does, declare the extra roots on
one line inside the registry section so verification accepts them:

```markdown
## Plan Registry
Plan roots: docs/archive/plans/, design/specs/
```

Declared roots add to the defaults; they never replace them.

## The Plan Registry Problem

In long-running projects, `writing-plans` and `brainstorming` produce multiple plan files over time:

```
docs/plans/                                   ← superpowers ≤ 4.x
├── 2026-02-13-migration-design.md            ← brainstorming
├── 2026-02-13-migration-implementation.md    ← writing-plans
docs/superpowers/                             ← superpowers ≥ 5.0
├── specs/2026-09-26-sync-design.md           ← brainstorming
└── plans/2026-09-26-sync.md                  ← writing-plans
```

Without a registry, these become "orphan plan files" — the MRS has no record of them, and recovery
sessions miss their context entirely.

## Plan Registry Format

Every `plan.md` MUST include a Plan Registry section at the bottom. The `File` column is the
repo-relative path, so files from different roots never collide:

```markdown
## Plan Registry

| File | Source Skill | Date | Status |
|------|-------------|------|--------|
| docs/plans/2026-02-13-migration-implementation.md | writing-plans | 2026-02-13 | completed |
| docs/superpowers/specs/2026-09-26-sync-design.md | brainstorming | 2026-09-26 | completed |
| docs/superpowers/plans/2026-09-26-sync.md | writing-plans | 2026-09-26 | in_progress |
```

Legacy `## Plan Registry (docs/plans)` headings remain valid; there is no need to rename them.

**Strict boundary — only register files under the plan roots.** Do NOT register:
- `CLAUDE.md` / `AGENTS.md` — Agent auto-loads these; they are not plans
- `.task-state/*` — MRS files themselves; circular reference
- `docs/runbooks/*` — Operational guides, not execution plans
- `.superpowers/sdd/*` — superpowers 6.x execution ledgers; git-ignored and deleted when the plan
  finishes (see [Execution Ledgers](#execution-ledgers-superpowers-6x))

If other reference files need tracking, add a separate **Reference Index** section:

```markdown
## Reference Index
| File | Purpose |
|------|---------|
| docs/runbooks/dev-guide.md | Development setup |
| CLAUDE.md | Project constraints |
```

**Status values:**
- `pending` — File exists but execution not started
- `in_progress` — Currently being executed (only one file should have this at a time)
- `completed` — All phases in this file have been executed and verified
- `abandoned` — Superseded or no longer relevant

A spec is `completed` once the user approves it; its implementation plan carries execution status.

## Cross-Skill Handoff Protocol

When any other skill produces a new file under a plan root:

### Agent MUST immediately:

1. **Register the file** — Add a row to `plan.md` Plan Registry with `status: pending`
2. **Update task_state.md** — Set `Current Phase` to reference the new file if it becomes the active plan
3. **Generate a snapshot** — This is a key event trigger

### When starting execution of a registered plan:

1. Change its status in Plan Registry from `pending` → `in_progress`
2. Update `task_state.md` → Current Phase to point to it
3. If a previous plan was `in_progress`, set it to `completed` first

### When execution of a plan file is complete:

1. Change status in Plan Registry from `in_progress` → `completed`
2. Update `task_state.md` with summary of what was accomplished
3. Generate a snapshot

## Execution Ledgers (superpowers 6.x)

From 6.x, `subagent-driven-development` and `executing-plans` share a per-plan workspace under
`<git-toplevel>/.superpowers/sdd/`, resolved by upstream `sdd-workspace PLAN_FILE`. Its
`progress.md` is a ledger: one line per task (commit, test result), plus `Ruling:` lines for every
deviation from the plan. The workspace is git-ignored and **deleted** once the final review and its
fix pass are clean.

**Which workspace belongs to which plan:** the directory name is only a slug. Two plans sharing a
basename (`docs/alpha/plan.md`, `docs/beta/plan.md`) get disambiguated slugs such as `plan-beta`
or `plan-beta-2`. The authoritative owner is the workspace's `plan-path` marker (repo-relative, or
absolute for plans outside the repo); legacy marker-less workspaces name their plan on the ledger's
first line (`# SDD ledger — plan: <path>`). Never guess the directory from the plan's basename.

Workspaces live at the **git toplevel** of the worktree doing the work, even when the MRS belongs
to a project in a repo subdirectory; markers are relative to that toplevel. A Plan Registry row may
use either the toplevel-relative or the project-relative path.

**What the hooks do automatically** (within their 4000-character budgets):
- `restore_context.py` (SessionStart / after `/clear`), single MRS: shows up to **2** in-flight
  ledgers with owning plan, Plan Registry status (or `NOT in Plan Registry`) and tail, then a count
  of the rest. Plans marked `in_progress` in the Registry come first, then newest ledger first.
- `restore_context.py`, several MRS: asks which task to resume and indexes up to **3** ledgers
  (plan + last line) without assigning them to a task. After choosing, restore one MRS fully with
  `restore_context.py <dir> --mrs <mrs_dir>`.
- `precompact_digest.py` (PreCompact): the first ledger in the same order plus a count of the rest,
  and a restore command that keeps the current worktree as the start and names the MRS explicitly.
- `gate_check.py` (Stop): reminds when a ledger is newer than `snapshot.md`, independently of
  uncommitted-file drift — SDD commits every task, so drift alone misses that progress.
- `verify_mrs.py`: warns when a ledger belongs to an unregistered plan.
- A workspace that disappears mid-scan (upstream deletes finished ones) is skipped.

The ledger and the MRS answer different questions, so keep both and do not duplicate:

| Concern | Owner |
|---------|-------|
| Per-task progress *inside one plan* (task N done, test output, review packages) | superpowers ledger |
| Which plan is active, cross-plan / cross-session state, todos outside the plan | MRS `task_state.md` + `plan.md` |
| Stable decisions that must outlive the plan | MRS `decisions.md` |

Rules:
- Do not mirror every ledger line into `progress.md`; log plan-level milestones only
  (started plan X, task N of M reached, blocked, finished).
- During recovery, read the ledger tail the hook surfaced (or open the ledger) together with the
  MRS; for in-plan task progress the ledger and `git log` win over MRS prose. Then bring
  `task_state.md` up to the plan-level milestone the ledger shows.
- **Before the workspace is deleted** (after the final review and its fix pass, before
  `finishing-a-development-branch`), copy the `Ruling:` lines and `Final: minor (deferred)` items
  that should outlive the plan into `decisions.md` / `task_state.md`, and record the plan-level
  milestone. After deletion only git history remains.
- Persisting a selection into the MRS does **not** replace superpowers' own final report: upstream
  still requires every `Ruling:` line (in order) and every deferred minor item to be listed to the
  user before the workspace is deleted. Do both.
- Never register ledger paths in the Plan Registry and never cite them as sources in
  `decisions.md` — they will dangle. Cite the plan file or commit instead.

superpowers ≤ 5.x has no ledger; the MRS is the only execution record there.

## Git Worktrees (shared MRS)

superpowers `using-git-worktrees` isolates work in a linked worktree: 6.x prefers the harness's
native worktree tool (e.g. Claude Code's, under `.claude/worktrees/`), otherwise `git worktree add`
into `.worktrees/` or a user-chosen directory. A task spans the main checkout and its worktrees, so
**one MRS is shared**:

- Keep the MRS where the task started, normally the main checkout. Do not create a second MRS
  inside the worktree for the same task.
- Discovery walks up from the current directory, so a worktree nested in the project finds the main
  checkout's MRS. A worktree outside the project falls back to the repository's other worktrees
  from `git worktree list` (main checkout first), at the same relative path, so a project in a repo
  subdirectory is found too. Every candidate found is returned, so ambiguous layouts (several
  worktrees of a bare repository) ask which task to resume. Submodule checkouts are resolved through
  `core.worktree`. A `--separate-git-dir` main checkout is recorded nowhere by git, so it cannot be
  found from another worktree: use `restore_context.py <dir> --mrs <mrs_dir>`.
- What is per-worktree is the *work*: uncommitted-change drift (`restore_context.py`,
  `gate_check.py`, `generate_snapshot.py` default) is read from the project's counterpart inside
  the worktree you are in, and ledgers from that worktree's git toplevel — as long as it belongs to
  the same repository as the MRS project. The restore header shows
  `(shared MRS; current worktree: <path>)` when they differ.
- `finishing-a-development-branch` removes the worktree it created. An untracked MRS inside that
  worktree is deleted with it — another reason to keep it in the main checkout. An MRS committed
  on the feature branch travels with the merge instead.

## Recommended Directory Structure

```
project/
  ├── docs/plans/                  # superpowers ≤ 4.x designs + plans
  ├── docs/superpowers/
  │   ├── specs/                   # superpowers ≥ 5.0 designs (brainstorming)
  │   └── plans/                   # superpowers ≥ 5.0 plans (writing-plans)
  ├── .superpowers/sdd/<plan>/     # superpowers 6.x ledger (git-ignored, transient)
  │
  ├── .task-state/                 # MRS (context-resilient-task)
  │   ├── task_state.md            # Source of truth (in-place updated)
  │   ├── plan.md                  # Active plan + Plan Registry
  │   ├── snapshot.md              # Latest checkpoint
  │   ├── findings.md              # Discoveries (append-only)
  │   ├── progress.md              # Session log (append-only)
  │   ├── decisions.md             # ADRs (Tier 2)
  │   ├── blockers.md              # Blockers (Tier 2)
  │   └── archive/                 # Completed MRS snapshots
  │
  └── src/                         # Code being developed
```

**Key role separation:**
- Plan/spec files — Immutable after creation; read-only reference during execution
- `plan.md` — Living registry that tracks status of all registered plan files + current active plan
- `task_state.md` — Real-time execution state; in-place updated only

## Initialization from Existing Plans

When the MRS is being created after plan files already exist, the agent should:

1. **Run the bundled initializer** to create Tier 0 from templates:

   ```
   python <skill-root>/scripts/init_mrs.py --dir .task-state \
       --goal "<task goal>" --complexity <small|medium|large> \
       --requirements "<req1;req2;...>"
   ```

   Or invoke it without arguments for the interactive wizard. The script renders
   `task_state.md`, `plan.md`, `snapshot.md` (and `decisions.md` when `--complexity large` /
   `--multi-agent` / >10 requirements) from `assets/`.

2. **Seed plan.md from the most recent existing implementation plan.** Read the newest file in
   `docs/superpowers/plans/` (or, for older projects, the newest non-`-design` file in
   `docs/plans/`) and merge its phases into the freshly generated `.task-state/plan.md`. Preserve
   the Plan Registry section inserted by the initializer.

3. **Build the Plan Registry rows.** Scan every plan root (`docs/plans/`,
   `docs/superpowers/specs/`, `docs/superpowers/plans/`, plus any the project uses) and append one
   row per file with its repo-relative path, `Source Skill`, `Date`, and `Status` (typically
   `pending` or `completed`). If the project uses a non-default root, add the `Plan roots:` line.

4. **Update task_state.md to reference the active plan.** Set `Current Phase` to point
   at the in-progress plan file. Keep `Active Todos` near the top.

5. **Generate a snapshot** to capture this initial state:

   ```
   python <skill-root>/scripts/generate_snapshot.py .task-state
   ```

The exact tool used to read existing plan files (Read, cat, file viewer, etc.) is
agent-specific — only the resulting MRS structure matters.

## Skill Compatibility Matrix

Skill names are shown bare; when superpowers is installed as a plugin they appear as
`superpowers:<name>`.

| Skill | Relationship | Notes |
|-------|-------------|-------|
| brainstorming | ✅ Complements | Design/spec → register in Plan Registry (`docs/plans/` ≤ 4.x, `docs/superpowers/specs/` ≥ 5.0) |
| writing-plans | ✅ Complements | Plan → register, status=pending (`docs/plans/` ≤ 4.x, `docs/superpowers/plans/` ≥ 5.0) |
| using-git-worktrees | ✅ Compatible | Shared MRS in the main checkout; drift and ledgers follow the current worktree (see [Git Worktrees](#git-worktrees-shared-mrs)) |
| subagent-driven-development | ⚠️ Overlaps (6.x) | 6.x keeps a per-plan ledger; split duties per [Execution Ledgers](#execution-ledgers-superpowers-6x) |
| executing-plans | ⚠️ Overlaps | Both manage execution; 6.x shares the SDD ledger — same split applies |
| finishing-a-development-branch | ✅ Complements | Harvest ledger rulings first; on merge set task_state.md status=completed, archive MRS |

## Task Completion and Archival

When all work is done:

1. Set `task_state.md` → `status: completed`
2. Verify all Plan Registry entries are `completed` or `abandoned`
3. Generate final snapshot with `--archive` flag
4. Optionally move `.task-state/` to `.task-state/archive/YYYY-MM-DD/`

On next invocation, the skill detects `status=completed` and prompts archival instead of resuming.
