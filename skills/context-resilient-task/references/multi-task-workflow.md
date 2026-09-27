# Multi-Task Workflow

Use this reference when one project needs multiple independent MRS directories.

## When to Use Multiple MRS

Default to one MRS per project. Create a sibling MRS only when one of these holds:

1. Independent subdirectories: a repo contains modules whose work is unrelated, such as a SkillCollections repo with several independent skills.
2. Interrupt scenario: a high-priority task arrives while a long task is mid-flight, and the original MRS must stay untouched.
3. Cross-cutting work alongside feature work: for example, a repo-wide upgrade running in parallel with feature development.

Do not create multiple MRS directories for:

- Sub-phases of a single goal. Use `plan.md` phases.
- Short bugfixes that finish within one session.
- Branch-per-feature isolation that git already provides, unless cross-session recovery is also needed.

## Naming Convention

```text
.task-state/                 # default MRS
.task-state-<slug>/          # additional concurrent task
```

Slug guidance:

- Use lowercase letters, numbers, and hyphens.
- Keep it short and meaningful, such as `auth-refactor`, `bugfix-x42`, or `analytics-v2`.
- Avoid date-prefixed slugs. The mtime is already shown by `list_mrs.py`.

## Discovery and Selection

The skill walks up from CWD and finds `.task-state/` or `.task-state-<slug>/` directories at the first ancestor level where any exist.

| Found | Action |
|---|---|
| 0 | Initialization mode |
| 1 | Use it; no ambiguity |
| 2+ | List goal/status/mtime, ask the user which task is current, and recommend the most recently updated entry without assuming |

Run:

```bash
python <skill-root>/scripts/list_mrs.py
python <skill-root>/scripts/list_mrs.py --json
```

## Switching Tasks

The skill does not store a "current task" pointer. Switching is a conversation act:

1. User names the target task, such as "switch to auth".
2. Agent runs `list_mrs.py`.
3. Agent reads `task_state.md` from the selected MRS and runs the normal recovery flow.
4. Agent confirms the recovered goal before continuing.

## Interrupt Protocol

When work on task A is interrupted by urgent task B:

```bash
# A is already at .task-state/ or .task-state-a/
python <skill-root>/scripts/generate_snapshot.py .task-state --archive

python <skill-root>/scripts/init_mrs.py \
    --dir .task-state-bugfix-x42 \
    --goal "Fix auth bypass" \
    --complexity small
```

The original MRS is untouched. When B is done, archive it rather than delete:

```bash
mkdir -p .task-state/archive
mv .task-state-bugfix-x42 .task-state/archive/bugfix-x42-completed
```

## Anti-Patterns

| Anti-pattern | Why it breaks | Correct approach |
|---|---|---|
| `--force` to overwrite an active MRS | Destroys recovery state | Use `--dir .task-state-<slug>` |
| Mixing two tasks in one `task_state.md` | Recovery output becomes incoherent | One MRS per independent task |
| Tracking current task in `CLAUDE.md` or `AGENTS.md` | Easy to drift from filesystem reality | Discover from filesystem and ask on ambiguity |
| Cross-referencing one MRS from another | Defeats task isolation | Promote shared findings to project docs |
| Date-prefixed slugs | Adds redundant naming noise | Use semantic slugs |

## Archive Layout

```text
project/
├── .task-state/                          # active
├── .task-state-feature-y/                # active
└── .task-state/archive/
    ├── bugfix-x42-completed/             # archived
    └── feature-x-completed/              # archived
```

Archives do not pollute `list_mrs.py` output because discovery checks only the first ancestor level where MRS siblings exist.

## Multi-Agent Note

When multiple agents work in the same repo:

- Each agent uses the same discovery walk.
- Multiple discovered MRS directories require asking the user before resuming.
- Concurrent writes to the same MRS remain a coordination risk. Use one MRS per active session when work is independent.

Copy [agents-md-snippet.md](agents-md-snippet.md) into project `AGENTS.md` when other agents need the same rules.
