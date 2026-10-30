# Multi-Task Workflow

Use multiple MRS only for independent goals, an interrupting task, or unrelated
modules. Keep phases of one goal in its existing plan. A branch alone does not
need a new MRS unless cross-session recovery is needed.

## Layout and naming

```text
project/
└── .task-state/
    ├── main/               # default task
    ├── auth-refactor/      # independent task
    ├── bugfix-x42/         # interrupting task
    └── archive/            # excluded from normal discovery
```

Slots use lowercase letters/numbers/hyphens. Prefer semantic names over dates.
`main` is not a current-task pointer. Reserved names: archive, snapshots,
cross-agent-review and hidden control directories.

Legacy `.task-state/` with task artifacts and `.task-state-<slug>/` remain
readable. An empty/runtime-only container is not a task. Partial records remain
visible for repair; missing one core file does not erase their identity.

## Discovery and selection

Walk upward from CWD to the first owning project with records. Enumerate direct
nested slots alongside its legacy records; do not recursively scan archive or
runtime directories. Physical aliases to the same MRS are deduplicated. Inside
a selected slot/evidence directory, the containing slot is explicit scope.

- No records: initialize.
- One record: use it.
- Multiple records: list goal/status/mtime and select explicitly. An already
  user-selected task in the current conversation is sufficient; never assume
  main or the latest entry merely from its name/mtime.
- Linked worktrees keep sharing MRS; changes and SDD ledgers follow the current
  worktree, not the physical state directory.

```bash
python <skill-root>/scripts/list_mrs.py --json
python <skill-root>/scripts/restore_context.py --mrs .task-state/auth-refactor
```

Switching remains a conversation act, with no global current-task pointer.

## Interrupt protocol

Checkpoint the selected task before starting an independent slot:

```bash
python <skill-root>/scripts/generate_snapshot.py .task-state/main --archive
python <skill-root>/scripts/init_mrs.py --slot bugfix-x42 \
    --goal "Fix auth bypass" --complexity small
```

Keep the original task untouched. When done, mark the task completed and archive
the selected leaf (not the container). Update explicit entry points when moving
again; a prior migration map does not guess future archive names.

## Existing repositories

Do not move existing data on invoke. Upgrade readers/hooks first, then use the
explicit [migration workflow](mrs-layout-migration.md). Preview is read-only;
application checks conflicts, ownership, unfinished reviews and content changes.
Historical text stays intact and old CRT paths can use a recorded relocation map.

## Avoid

- `--force` over active state: choose a new slot.
- Two unrelated goals in one task_state.md: keep separate MRS.
- A duplicate current-task status in a project index: discover, then select.
- Assuming the container itself needs initialization because it lacks Tier 0.
- Automatically merging same-named legacy and nested slots.
- Migrating while another agent/reviewer is writing that task.

Copy [agents-md-snippet.md](agents-md-snippet.md) into project AGENTS.md when
other agents need the same rules; no global installation is performed here.
