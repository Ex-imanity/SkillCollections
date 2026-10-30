"""Read-only relocation maps. They resolve paths, never select a current task."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, unquote

CURRENT_POINTERS = {"task_state.md", "plan.md", "utils.md", "AGENTS.md", "CLAUDE.md"}


def safe_path(root: Path, relative: str) -> Path:
    part = PurePosixPath(relative)
    if (part.is_absolute() or not part.parts or ".." in part.parts
            or "\\" in relative or any(":" in p for p in part.parts)):
        raise ValueError("migration record contains an unsafe relative path")
    path = root.joinpath(*part.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("migration path escapes the owning project") from exc
    return path


def migrations(root: Path) -> list[dict]:
    records = []
    for path in sorted((root / ".task-state/.migrations").glob("*/manifest.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("version") != 1 or not isinstance(record.get("moves"), list):
            raise ValueError("invalid MRS migration manifest")
        for move in record["moves"]:
            safe_path(root, move["source"])
            safe_path(root, move["destination"])
        if record.get("state") == "completed":
            records.append(record)
    return records


def _replace_prefix(path: Path, source: Path, destination: Path, directory: bool) -> Path | None:
    if path == source:
        return destination
    if directory:
        try:
            return destination / path.relative_to(source)
        except ValueError:
            pass
    return None


def map_path(path: Path, root: Path, records: list[dict], inverse: bool = False) -> Path:
    """Map exact files or whole moved directories; default-container alias is exact-only."""
    path, root = absolute(path), absolute(root)
    for record in (reversed(records) if inverse else records):
        moves = sorted(record["moves"], key=lambda m: len(m["source"]), reverse=True)
        for move in moves:
            source, destination = safe_path(root, move["source"]), safe_path(root, move["destination"])
            if inverse:
                source, destination = destination, source
            changed = _replace_prefix(path, source, destination, move["kind"] == "directory")
            if changed is not None:
                path = changed
                break
        else:
            if record.get("legacy_default"):
                source, destination = root / ".task-state", root / ".task-state/main"
                if path == (destination if inverse else source):
                    path = source if inverse else destination
    return path


def absolute(path: Path) -> Path:
    # Resolve existing prefixes even when the old task itself has already moved.
    return path.expanduser().resolve()


def resolve_path(path: Path, root: Path | None = None) -> Path:
    path = absolute(path)
    # Existing files/new tasks win over an old alias. A migrated default root
    # still exists as a container, so its exact alias is the one exception.
    if path.exists():
        from _mrs_discovery import has_mrs_artifacts
        if path.name != ".task-state" or has_mrs_artifacts(path):
            return path.resolve()
    roots = [root.resolve()] if root is not None else list(path.parents)
    for owner in roots:
        records = migrations(owner)
        mapped = map_path(path, owner, records)
        if mapped != path:
            return mapped.resolve()
    return path.resolve()


def split_locator(value: str) -> tuple[str, str]:
    path, marker, fragment = value.partition("#")
    suffix = marker + fragment
    path, marker, query = path.partition("?")
    suffix = marker + query + suffix
    before, sep, line = path.rpartition(":")
    if sep and re.fullmatch(r"\d+(?:-\d+)?", line):
        path, suffix = before, ":" + line + suffix
    return unquote(path), suffix


def format_locator(path: Path | str, suffix: str, original: str) -> str:
    """Serialize a native path without turning filename characters into suffixes."""
    value = str(path)
    original_path = original.partition("#")[0].partition("?")[0]
    if re.search(r"%[a-fA-F0-9]{2}", original_path):
        value = quote(value, safe="/")
    else:
        for character, escaped in (("%", "%25"), ("#", "%23"), ("?", "%3F"), (":", "%3A")):
            value = value.replace(character, escaped)
    return value + suffix


def resolve_locator(value: str, root: Path, from_file: Path | None = None) -> dict:
    root = absolute(root)
    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        raise ValueError("only local filesystem references are supported")
    bare, suffix = split_locator(value)
    if "\x00" in bare:
        raise ValueError("local reference contains a null byte")
    pointer = Path(bare)
    if not pointer.is_absolute():
        base = root
        state_bare = bare[2:] if bare.startswith("./") else bare
        if from_file is not None and state_bare != ".task-state" and not state_bare.startswith((".task-state/", ".task-state-")):
            document = resolve_path(from_file if from_file.is_absolute() else root / from_file, root)
            # Historical text remains byte-identical. Interpret its relative
            # links at the original document location, then map their targets.
            from _mrs_discovery import is_mrs_dir
            current = document.name in CURRENT_POINTERS and (document.parent == root or is_mrs_dir(document.parent))
            if not current:
                document = map_path(document, root, migrations(root), inverse=True)
            base = document.parent
        pointer = base / pointer
    original = absolute(pointer)
    resolved = resolve_path(original, root)
    return {"resolved": format_locator(resolved, suffix, value), "path": str(resolved),
            "exists": resolved.exists(), "via_migration": resolved != original}
