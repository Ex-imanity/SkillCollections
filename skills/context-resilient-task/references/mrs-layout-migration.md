# Nested MRS layout and explicit migration

New tasks use `.task-state/main/` by default or `.task-state/<slot>/` for an
independent task. `main` is a name, not a current-task pointer. Discovery still
reads legacy `.task-state/` records and `.task-state-<slot>/` records alongside
nested slots. Updating the skill does not relocate existing data.

The container is not an MRS. A surviving known MRS artifact identifies a partial
record that needs repair; missing Tier 0 must not hide it. `archive`, `snapshots`,
`cross-agent-review` and hidden control directories are reserved, not slot names.
Discovery examines direct slots only and deduplicates real filesystem aliases.

## Upgrade readers before moving data

Use the new skill/scripts in every agent or hook that reads these tasks before
migrating. Old installed scripts and literal `cat`/editor links do not acquire
compatibility automatically. This workflow does not install skills or hooks.
The MRS document schema, authority rules and worktree sharing remain unchanged.

## Preview

From any directory, pass the owning project explicitly:

```bash
python <skill-root>/scripts/migrate_mrs.py /repo
python <skill-root>/scripts/migrate_mrs.py /repo --json
python <skill-root>/scripts/migrate_mrs.py /repo --slot auth
```

Preview is read-only: moves, reference findings, current-pointer edits and
blockers are reported without creating a container, journal or backup. The audit
covers Markdown in moved MRS data and root AGENTS.md/CLAUDE.md/README.md. It checks
literal local state paths, Markdown links and explicit `./` / `../` code paths;
it is not a parser for arbitrary scripts, computed paths or external settings.
Likely credential values are withheld from audit output.
Delimited Markdown/code targets retain spaces. Query and line/fragment suffixes
are preserved while the filesystem path is mapped; audit records with sensitive
values show only a withheld reference and the mapping outcome. A current-pointer
document that is not UTF-8 blocks application; undecodable history remains
byte-identical and appears in `skipped` in JSON and text output.
Percent-encoded filenames retain their encoding when rewritten, including
spaces and literal `#`, `?`, `%`, parentheses or line-like colons. A decoded
parent-directory reference that leaves the state namespace is rebased from the
document's new location. Sentence punctuation stays outside bare path edits;
punctuation inside a delimited filename remains part of the filename.
Decoded NUL references are reported as `invalid_reference`: a current pointer
blocks application, while invalid history stays unchanged and the audit checks
the remaining references. Text output identifies the skipped reference's line.

Unquoted paths with spaces, Markdown link titles and computed/concatenated paths
remain outside this literal scan's guarantees; inspect these manually before
applying a migration.

Reference statuses distinguish `preexisting_missing`, `preserved`, `rewritten`,
`historical_alias`, `withheld_sensitive` and `unresolved_after_migration`.
`invalid_reference` identifies an unusable local pointer rather than a missing
file; it never becomes a filesystem probe.
Pre-existing missing examples/resources do not count as new migration failures.

## Apply after task writers have stopped

```bash
python <skill-root>/scripts/migrate_mrs.py /repo --apply
python <skill-root>/scripts/migrate_mrs.py /repo --slot auth --apply
```

- `.task-state-auth/` moves intact to `.task-state/auth/`.
- A real legacy default MRS moves its task files into `.task-state/main/`.
  Existing nested slots and `archive/` stay in the container. `snapshots/` belongs
  to the old task; other child directories require explicit ownership with
  repeated `--include-default-dir <name>` (for example `cross-agent-review`).
- Runtime-only containers do not manufacture an empty `main` MRS.
- Existing destinations, symlinks requiring ownership review, damaged or
  unfinished native-review records, and unfinished earlier migrations refuse
  application. A permanent reviewer `.lock` sentinel alone is not an active gate.
  Never reset review counters/bindings just to move a task.
- The migration lock serializes migration tools, not old agents. Stop those
  writers first; content fingerprints also detect changes during application.

Current top-level `task_state.md`, `plan.md`, `utils.md`, plus root `AGENTS.md` and
`CLAUDE.md`, receive targeted path/link updates. Other Markdown, including
progress, findings, snapshots and backup documents, stays byte-identical. Files
retain their modification times and permissions. No root-wide text replacement
or symlink aliases are created.

Each transaction has a private `.task-state/.migrations/<id>/manifest.json` and
backups of rewritten files. The manifest stores relative moves, hashes and path
findings, not whole document bodies. Keep it with the MRS: it is a relocation map,
not a second source of task status or a current-task selector.

## Resolve historical references

CRT's explicit restore, verify, snapshot, recall and resource-scan commands use
the map when given a migrated legacy path. An existing new task at that old path
takes precedence. A migrated default-root alias is exact; it never captures
unrelated new slots or archive contents.

```bash
python <skill-root>/scripts/migrate_mrs.py /repo --resolve '.task-state-auth/progress.md:42'
python <skill-root>/scripts/migrate_mrs.py /repo --resolve '../docs/design.md' \
  --from-file '.task-state/auth/progress.md' --json
```

`--from-file` interprets a historical relative link from its original document
location, then maps the target. For current-pointer documents it uses the current
location. Bare `.task-state` references are project-relative. Line/fragment
and query suffixes are preserved. Existing path prefixes are canonicalized, so
symlink spellings of the same project, including macOS `/var` and `/private/var`,
use the same map. `via_migration` indicates a map changed the canonical path.
JSON `path` is the native filesystem path; `resolved` is a reusable locator with
reserved filename characters escaped separately from its suffix.
Raw historical Markdown links and old third-party tools
are not filesystem redirects; use the resolver instead of claiming they all
became directly clickable. Later manual moves/archival need their own updated
entry points; the recorded map describes this migration only.

An explicit container with several slots is ambiguous unless a recorded legacy
default alias specifies its old meaning. Automatic discovery never chooses main
over another task merely because of its name.

## Guarded rollback

```bash
python <skill-root>/scripts/migrate_mrs.py /repo --rollback <id>
```

Rollback checks every moved tree and rewritten entry point before changing any
file. It restores original bytes/metadata and paths, retains the audit journal,
and disables that transaction's aliases. If task work changed afterwards it
refuses to overwrite it. Repeating apply after completed migration is a no-op.

Ordinary I/O failure attempts automatic rollback. After a crash, inspect the
saved `in_progress`/`failed`/`rolling_back` manifest and recover it before starting another
migration. If `.migration.lock` survived the crash, first establish that its
owner exited; do not automatically delete another process's lock.
Rollback records `rolling_back` before restoring bytes or paths. Retrying the
same rollback accepts already restored pointers and moves, while still refusing
unrecognized changes at either location. This supports ordinary write/rename or
journal failures; power-loss durability has not been independently tested.
