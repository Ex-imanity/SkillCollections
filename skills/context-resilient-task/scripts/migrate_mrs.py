#!/usr/bin/env python3
"""Preview or explicitly migrate legacy MRS; preserve historical text and path maps."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

from _mrs_discovery import has_mrs_artifacts, is_mrs_dir, validate_slot
from _mrs_paths import CURRENT_POINTERS, absolute, format_locator, map_path, resolve_locator, safe_path, split_locator
from _state_probe import has_sensitive_value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree(path: Path) -> dict:
    if path.is_symlink():
        raise ValueError("symlink migration requires manual ownership review")
    if path.is_file():
        return {".": digest(path.read_bytes())}
    result = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError("symlink migration requires manual ownership review")
        key = item.relative_to(path).as_posix()
        result[key + "/" if item.is_dir() else key] = "directory" if item.is_dir() else digest(item.read_bytes())
    return result


def atomic(path: Path, data: bytes, mode: int = 0o600, mtime_ns: int | None = None) -> None:
    temporary = path.with_name(path.name + ".tmp-" + uuid4().hex)
    try:
        with temporary.open("xb") as handle:
            os.chmod(temporary, mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if mtime_ns is not None:
            os.utime(path, ns=(mtime_ns, mtime_ns))
    finally:
        if temporary.exists():
            temporary.unlink()


def save(path: Path, value: dict) -> None:
    atomic(path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def add_move(report: dict, root: Path, source: Path, destination: Path) -> None:
    if source.is_symlink():
        report["blocked"].append("symlink source: " + str(source.relative_to(root)))
        return
    if destination.exists() or destination.is_symlink():
        report["blocked"].append("destination already exists: " + str(destination.relative_to(root)))
    try:
        signature = tree(source)
    except (OSError, ValueError) as exc:
        report["blocked"].append(str(exc))
        return
    report["moves"].append({"source": source.relative_to(root).as_posix(),
                            "destination": destination.relative_to(root).as_posix(),
                            "kind": "directory" if source.is_dir() else "file", "before_tree": signature})
    candidates = source.rglob("*.json") if source.is_dir() else [source] if source.suffix == ".json" else []
    for file in candidates:
        if not file.parent.name.endswith(".sessions"):
            continue
        try:
            state = json.loads(file.read_text(encoding="utf-8")).get("state")
            if state in {"running", "timed_out"}:
                report["blocked"].append("unfinished reviewer gate: " + file.relative_to(root).as_posix())
        except (OSError, ValueError, AttributeError):
            report["blocked"].append("damaged reviewer record: " + file.relative_to(root).as_posix())


def future_exists(path: Path, root: Path, record: dict) -> bool:
    if map_path(path, root, [record]) != path:
        return False
    if path.exists():
        return True
    return map_path(path, root, [record], inverse=True).exists()


def references(text: str, root: Path):
    """Local state paths, Markdown targets and explicit ./ or ../ code paths.

    This is a literal-reference audit, not a shell/programming-language parser.
    It deliberately excludes URLs and another repository's absolute paths.
    """
    def state_reference(value):
        bare, _ = split_locator(value)
        # Classify the prefix only; audit_file reports a decoded NUL without
        # asking filesystem APIs to inspect that invalid reference.
        bare = bare.partition("\x00")[0]
        path = Path(bare)
        if path.is_absolute():
            try:
                path = absolute(path).relative_to(root)
            except ValueError:
                return False
        return bool(path.parts and re.fullmatch(r"\.task-state(?:-[a-zA-Z0-9_-]+)?", path.parts[0]))

    found = []
    # Delimited targets own their entire span, including spaces; a shorter
    # literal match must not suppress the surrounding Markdown/code target.
    for pattern, code in ((r"\[[^\]\n]*\]\(([^)\n]+)\)", False), (r"`([^`\n]+)`", True)):
        for match in re.finditer(pattern, text):
            value = match.group(1)
            left = 1 if value.startswith("<") and value.endswith(">") else 0
            value = value[left:len(value) - left or None]
            if not value or value.startswith("#") or re.match(r"[a-zA-Z][\w+.-]*:", value):
                continue
            kind = "state" if state_reference(value) else "relative"
            if kind != "state" and (Path(split_locator(value)[0]).is_absolute()
                                    or code and not value.startswith(("./", "../"))):
                continue
            start, end = match.start(1) + left, match.end(1) - left
            if not any(a < end and start < b for a, b, _, _ in found):
                found.append((start, end, value, kind))
    state = re.compile(r"(?<![\w./\\-])(?:/[^\s`<>\"'\]\[|(){}]+/|\./)?"
                       r"\.task-state(?:-[a-zA-Z0-9_-]+)?(?![\w-])"
                       r"(?:/[^\s`<>\"'\]\[|(){}，；。]*)?")
    for match in state.finditer(text):
        value = match.group().rstrip(".,;")
        start, end = match.start(), match.start() + len(value)
        if state_reference(value) and not any(a < end and start < b for a, b, _, _ in found):
            found.append((start, end, value, "state"))
    return sorted(found)


def audit_file(file: Path, root: Path, report: dict, current: bool) -> tuple[bytes, list[dict]]:
    raw = file.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        report["skipped"].append(file.relative_to(root).as_posix())
        if current:
            report["blocked"].append("current pointer is not UTF-8: " + file.relative_to(root).as_posix())
        return raw, []
    after_file = map_path(file, root, [report])
    changes, audited = [], []
    for start, end, value, kind in references(text, root):
        sensitive = has_sensitive_value(value)
        bare, suffix = split_locator(value)
        if not bare:
            continue
        entry = {"file": file.relative_to(root).as_posix(), "line": text.count("\n", 0, start) + 1}
        if "\x00" in bare:
            entry.update(reference="[withheld]" if sensitive else value,
                         status="invalid_reference", reason="decoded path contains a null byte")
            audited.append(entry)
            if current:
                report["blocked"].append("invalid reference in current pointer: " + entry["file"])
            continue
        pointer = Path(bare)
        if not pointer.is_absolute():
            pointer = (root if kind == "state" else file.parent) / pointer
        pointer = absolute(pointer)
        mapped = map_path(pointer, root, [report])
        raw_after = (pointer if Path(bare).is_absolute() or kind == "state"
                     else absolute(after_file.parent / bare))
        replacement = value
        if current and pointer.exists() and future_exists(mapped, root, report):
            replacement_path = None
            if Path(bare).is_absolute():
                replacement_path = str(mapped)
            elif kind == "state":
                # An unselected task may be a symlink to another checkout.
                # Its project-relative spelling remains valid and is not ours to move.
                if mapped == root or root in mapped.parents:
                    relative = mapped.relative_to(root)
                    if relative.parts and re.fullmatch(r"\.task-state(?:-[a-zA-Z0-9_-]+)?", relative.parts[0]):
                        replacement_path = relative.as_posix()
                    else:
                        # Decoded .. may leave the state namespace. Such a
                        # pointer must use its document's new relative base.
                        replacement_path = Path(os.path.relpath(mapped, after_file.parent)).as_posix()
            else:
                replacement_path = Path(os.path.relpath(mapped, after_file.parent)).as_posix()
            if replacement_path is not None:
                replacement = format_locator(replacement_path, suffix, value)
            if replacement != value:
                changes.append((start, end, replacement))
        status = ("preexisting_missing" if not pointer.exists() else
                  "rewritten" if replacement != value else
                  "historical_alias" if raw_after != mapped else "preserved")
        if pointer.exists() and not future_exists(mapped, root, report):
            status = "unresolved_after_migration"
            report["blocked"].append("reference cannot be resolved after migration: " + file.relative_to(root).as_posix())
        if sensitive:
            entry.update(reference="[withheld]", status="withheld_sensitive", outcome=status)
        else:
            entry.update(reference=value, after_reference=replacement, status=status,
                         resolved=format_locator(mapped, suffix, value))
        audited.append(entry)
    for start, end, replacement in reversed(changes):
        text = text[:start] + replacement + text[end:]
    return text.encode(), audited


def plan(root: Path, slots: list[str], included: list[str]) -> tuple[dict, list[tuple]]:
    report = {"version": 1, "state": "preview", "project_root": str(root), "moves": [],
              "legacy_default": False, "blocked": [], "references": [], "rewrites": [], "skipped": []}
    selected = set(slots)
    for name in selected:
        validate_slot(name)
    for name in included:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name) or name in {"main", "archive"}:
            raise ValueError("include-default-dir must name a single non-reserved child directory")
    bases = []
    for source in sorted(root.glob(".task-state-*")):
        slot = source.name[len(".task-state-"):]
        if not source.is_dir() or selected and slot not in selected:
            continue
        try:
            validate_slot(slot)
        except ValueError:
            report["blocked"].append("invalid legacy slot: " + source.name)
            continue
        if not has_mrs_artifacts(source):
            report["blocked"].append("no MRS artifacts in legacy directory: " + source.name)
            continue
        add_move(report, root, source, root / ".task-state" / slot)
        bases.append(source)
    container = root / ".task-state"
    if container.is_symlink():
        raise ValueError("migration container must be owned by this checkout, not a symlink")
    if has_mrs_artifacts(container) and (not selected or "main" in selected):
        report["legacy_default"] = True
        if (container / "main").exists() or (container / "main").is_symlink():
            report["blocked"].append("main already exists beside a legacy default MRS")
        for child in sorted(container.iterdir()):
            if child.name.startswith(".") or child.name == "archive" or child.name == "main":
                continue
            if child.is_dir() and is_mrs_dir(child):
                continue
            if child.is_dir() and child.name not in {"snapshots", *included}:
                report["blocked"].append("unclassified default directory (use --include-default-dir): " + child.name)
                continue
            add_move(report, root, child, container / "main" / child.name)
        bases.append(container)
    # Validate the whole plan, not only destinations already on disk. A
    # legacy default and .task-state-main would otherwise both claim main.
    for index, move in enumerate(report["moves"]):
        target = Path(move["destination"])
        for other in report["moves"][:index]:
            previous = Path(other["destination"])
            if target == previous or target in previous.parents or previous in target.parents:
                report["blocked"].append("planned destinations overlap: " + move["destination"])
    candidates = {}
    for move in report["moves"]:
        source = safe_path(root, move["source"])
        for file in source.rglob("*.md") if source.is_dir() else [source] if source.suffix == ".md" else []:
            if not file.is_symlink():
                candidates[file] = file.parent in bases and file.name in CURRENT_POINTERS
    for name in ("AGENTS.md", "CLAUDE.md", "README.md"):
        file = root / name
        if file.is_file() and not file.is_symlink():
            candidates[file] = name in {"AGENTS.md", "CLAUDE.md"}
    edits = []
    for file, current in sorted(candidates.items()):
        data, refs = audit_file(file, root, report, current)
        report["references"].extend(refs)
        before = file.read_bytes()
        if data != before:
            stat = file.stat()
            metadata = {"source": file.relative_to(root).as_posix(),
                        "path": map_path(file, root, [report]).relative_to(root).as_posix(),
                        "before_sha": digest(before), "after_sha": digest(data),
                        "mtime_ns": stat.st_mtime_ns, "mode": stat.st_mode & 0o777}
            report["rewrites"].append(metadata)
            edits.append((metadata, before, data))
    return report, edits


@contextmanager
def locked(root: Path):
    container = root / ".task-state"
    if container.is_symlink():
        raise ValueError("migration container must not be a symlink")
    created = False
    try:
        container.mkdir()
        created = True
    except FileExistsError:
        pass
    lock = container / ".migration.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise ValueError("another migration holds .migration.lock; preserve it until its owner has exited") from exc
    try:
        handle.write(str(os.getpid()))
        handle.close()
        yield
    finally:
        lock.unlink()
        if created:
            try:
                container.rmdir()
            except OSError:
                pass  # Successful migrations or another writer left data here.


def rollback(root: Path, manifest: Path) -> dict:
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if record.get("version") != 1 or record.get("state") not in {"completed", "in_progress", "failed", "rolling_back"}:
        raise ValueError("migration is not in a rollback-capable state")
    # Validate every guard before modifying any file. Newly written task work
    # or an edited project entry point must never be silently overwritten.
    for move in record["moves"]:
        source, target = safe_path(root, move["source"]), safe_path(root, move["destination"])
        if (source.exists() or source.is_symlink()) and (target.exists() or target.is_symlink()):
            raise ValueError("rollback source and destination both exist")
        if not target.exists() and not source.exists():
            raise ValueError("migration data is missing at both paths")
        at_target = target.exists()
        where = target if at_target else source
        expected = dict(move.get("after_tree", move["before_tree"]) if at_target else move["before_tree"])
        for edit in record["rewrites"]:
            file = safe_path(root, edit["path"] if at_target else edit["source"])
            try:
                key = file.relative_to(where).as_posix() if where.is_dir() else "." if file == where else None
            except ValueError:
                continue
            if key is not None and file.is_file():
                actual = digest(file.read_bytes())
                if actual in {edit["before_sha"], edit["after_sha"]}:
                    expected[key] = actual
        if tree(where) != expected:
            raise ValueError("post-migration task files changed; rollback refused")
    for edit in record["rewrites"]:
        target = safe_path(root, edit["path"])
        original = safe_path(root, edit["source"])
        where = target if target.is_file() else original
        if not where.is_file() or digest(where.read_bytes()) not in {edit["before_sha"], edit["after_sha"]}:
            raise ValueError("a rewritten entry point changed; rollback refused")
        backup = manifest.parent / edit["backup"]
        if (backup.is_symlink() or backup.parent != manifest.parent / "backups"
                or digest(backup.read_bytes()) != edit["before_sha"]):
            raise ValueError("migration backup is damaged")
    record["state"] = "rolling_back"
    save(manifest, record)
    for edit in record["rewrites"]:
        target = safe_path(root, edit["path"])
        where = target if target.is_file() else safe_path(root, edit["source"])
        stat = where.stat()
        if (digest(where.read_bytes()) != edit["before_sha"] or stat.st_mtime_ns != edit["mtime_ns"]
                or stat.st_mode & 0o777 != edit["mode"]):
            atomic(where, (manifest.parent / edit["backup"]).read_bytes(), edit["mode"], edit["mtime_ns"])
    for move in reversed(record["moves"]):
        source, target = safe_path(root, move["source"]), safe_path(root, move["destination"])
        if target.exists():
            target.rename(source)
    if record["legacy_default"]:
        main = root / ".task-state/main"
        if main.is_dir() and not any(main.iterdir()):
            main.rmdir()
    record["state"] = "rolled_back"
    save(manifest, record)
    return record


def apply(root: Path, slots: list[str], included: list[str]) -> dict:
    with locked(root):
        for previous in (root / ".task-state/.migrations").glob("*/manifest.json"):
            state = json.loads(previous.read_text(encoding="utf-8")).get("state")
            if state not in {"completed", "rolled_back"}:
                raise ValueError("recover the unfinished migration before applying another: " + previous.parent.name)
        report, edits = plan(root, slots, included)
        if report["blocked"]:
            raise ValueError("; ".join(report["blocked"]))
        if not report["moves"]:
            return {**report, "state": "no_op"}
        ident = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
        directory = safe_path(root, ".task-state/.migrations/" + ident)
        directory.mkdir(parents=True, mode=0o700)
        os.chmod(directory.parent, 0o700)
        (directory / "backups").mkdir(mode=0o700)
        for index, (metadata, before, _) in enumerate(edits):
            metadata["backup"] = "backups/" + str(index) + ".bin"
            atomic(directory / metadata["backup"], before)
        record = {**report, "id": ident, "state": "in_progress"}
        manifest = directory / "manifest.json"
        save(manifest, record)
        try:
            if record["legacy_default"]:
                (root / ".task-state/main").mkdir()
            for move in record["moves"]:
                source, target = safe_path(root, move["source"]), safe_path(root, move["destination"])
                if tree(source) != move["before_tree"]:
                    raise ValueError("MRS changed during migration; stop its writers first")
                if target.exists() or target.is_symlink():
                    raise ValueError("destination appeared during migration; refusing to overwrite it")
                source.rename(target)
                save(manifest, record)
            for metadata, _, data in edits:
                file = safe_path(root, metadata["path"])
                if digest(file.read_bytes()) != metadata["before_sha"]:
                    raise ValueError("entry point changed during migration")
                atomic(file, data, metadata["mode"], metadata["mtime_ns"])
                save(manifest, record)
            for move in record["moves"]:
                move["after_tree"] = tree(safe_path(root, move["destination"]))
            record["state"] = "completed"
            save(manifest, record)
        except Exception:
            try:
                rollback(root, manifest)
            except Exception:
                record["state"] = "failed"
                save(manifest, record)
            raise
        return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="Move legacy tasks and update current pointers")
    action.add_argument("--rollback", metavar="ID", help="Restore a recorded migration if data is unchanged")
    action.add_argument("--resolve", metavar="PATH", help="Resolve a historical path without modifying anything")
    parser.add_argument("--from-file", type=Path, help="Document containing a historical relative reference")
    parser.add_argument("--slot", action="append", default=[], help="Migrate only this legacy task (repeatable)")
    parser.add_argument("--include-default-dir", action="append", default=[], help="Confirm an extra old-default directory belongs to main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.project).resolve()
    try:
        if not root.is_dir():
            raise ValueError("project must be an existing directory")
        if args.resolve:
            result = resolve_locator(args.resolve, root, args.from_file)
        elif args.rollback:
            if not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{8}", args.rollback):
                raise ValueError("invalid migration ID")
            with locked(root):
                result = rollback(root, root / ".task-state/.migrations" / args.rollback / "manifest.json")
        elif args.apply:
            result = apply(root, args.slot, args.include_default_dir)
        else:
            result, _ = plan(root, args.slot, args.include_default_dir)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.resolve:
            print(result["resolved"])
        else:
            print("MRS migration: " + result["state"])
            for move in result["moves"]:
                print(f"  {move['source']} -> {move['destination']}")
            for blocker in result["blocked"]:
                print("  BLOCKED: " + blocker)
            for file in result["skipped"]:
                print("  SKIPPED (not UTF-8): " + file)
            for reference in result["references"]:
                if reference["status"] == "invalid_reference":
                    print(f"  SKIPPED invalid reference: {reference['file']}:{reference['line']} ({reference['reason']})")
            counts = {status: sum(r["status"] == status for r in result["references"])
                      for status in {r["status"] for r in result["references"]}}
            print("  Reference audit: " + json.dumps(counts, ensure_ascii=False))
            if result.get("id"):
                print("  Migration ID: " + result["id"])
            elif result["state"] == "preview":
                print("  No files changed. Stop task writers and pass --apply to migrate.")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        if args.json:
            print(json.dumps({"state": "refused", "error": str(exc)}, ensure_ascii=False))
        else:
            print("MRS migration refused: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
