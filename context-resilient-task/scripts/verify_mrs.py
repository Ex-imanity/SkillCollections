#!/usr/bin/env python3
"""
Verify Minimum Recovery Set (MRS) completeness and consistency.

Usage:
    python verify_mrs.py [--json] [directory]

Exit codes:
    0: All Tier 0 files present and valid (may have warnings)
    1: Missing Tier 0 files (recovery impossible)
    2: Tier 1 files missing (recovery degraded)
    3: Validation errors (files malformed)
"""

from __future__ import annotations  # Python 3.7+ compatible type hints

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import re

# MRS Tiers
TIER_0 = ["task_state.md", "plan.md", "snapshot.md"]
# Tier 1 core: always checked
TIER_1_CORE = ["findings.md", "progress.md"]
# Tier 1 conditional: only required for multi-session/multi-agent/>10 phases
TIER_1_CONDITIONAL = ["architecture.md", "decisions.md"]
TIER_1_OPTIONAL = ["utils.md"]
TIER_2 = ["blockers.md"]

FORBIDDEN_SUBSTRINGS = ["/.cursor/", "/agent-tools/", "/temp/", "/tmp/", "/.cache/"]

MAX_TASK_STATE_LINES = 300
MAX_ACTIVE_TODOS_LINE = 50


def check_file_exists(directory: Path, filename: str) -> bool:
    """Check if file exists in directory."""
    return (directory / filename).exists()


def find_section_line(content: str, section: str) -> int | None:
    """Find the line number (1-based) of a section header. Returns None if not found."""
    for line_number, line in enumerate(content.splitlines(), 1):
        if line.strip() == section:
            return line_number
    return None


def extract_section_content(content: str, section: str) -> str:
    """Extract content under an exact markdown section header."""
    lines = content.splitlines()
    section_line = find_section_line(content, section)
    if section_line is None:
        return ""

    section_content = []
    for line in lines[section_line:]:
        if line.strip().startswith("#"):
            break
        section_content.append(line)

    return "\n".join(section_content).strip()


def validate_task_state(filepath: Path) -> tuple[bool, str, list[str]]:
    """Validate task_state.md structure. Returns (valid, message, warnings)."""
    warnings = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        line_count = len(lines)

        # Required sections
        required = [
            "# Task State",
            "## Goal",
            "## Status",
            "## Active Todos",
            "## Current Phase",
            "## Next Action",
            "## Completed Items",
        ]
        missing = [section for section in required if find_section_line(content, section) is None]

        if missing:
            return False, f"Missing sections: {', '.join(missing)}", warnings

        for section in ("Active Todos", "Completed Items"):
            prefix = f"## {section}".lower()
            exact_count = sum(1 for line in lines if line.strip().lower() == prefix)
            suffixed = [line.strip() for line in lines if line.strip().lower().startswith(prefix) and line.strip().lower() != prefix]
            if suffixed:
                warnings.append(f"Suffixed {section} subsections preserved for legacy compatibility: {', '.join(suffixed[:3])}")
            if exact_count > 1:
                message = f"Duplicate authoritative section: {section} appears {exact_count} times"
                warnings.append(message)
                return False, message, warnings

        # Check for timestamp
        if "**Last Updated:**" not in content:
            return False, "Missing Last Updated timestamp", warnings

        # Check status enum
        status = extract_section_content(content, "## Status")
        valid_statuses = {"active", "paused", "blocked", "completed"}
        if status not in valid_statuses:
            return False, f"Invalid Status '{status}' (expected: active, paused, blocked, completed)", warnings

        # WARNING: line count exceeds threshold
        if line_count > MAX_TASK_STATE_LINES:
            warnings.append(
                f"task_state.md is {line_count} lines (limit: {MAX_TASK_STATE_LINES}). "
                "Consider compressing completed phases."
            )

        # WARNING: Active Todos not near top
        active_todos_line = find_section_line(content, "## Active Todos")
        if active_todos_line and active_todos_line > MAX_ACTIVE_TODOS_LINE:
            warnings.append(
                f"Active Todos at line {active_todos_line} (should be within first {MAX_ACTIVE_TODOS_LINE} lines). "
                "Move it closer to the top to prevent recovery truncation."
            )

        return True, "Valid", warnings

    except Exception as e:
        return False, f"Error reading file: {e}", warnings


def validate_plan(filepath: Path) -> tuple[bool, str, list[str]]:
    """Validate plan.md structure. Returns (valid, message, warnings)."""
    warnings = []
    try:
        content = filepath.read_text(encoding="utf-8")

        # Should have at least one phase
        if not re.search(r"##?\s+Phase\s+\d+", content):
            return False, "No phases found", warnings

        # Check for phase statuses
        valid_statuses = ["pending", "in_progress", "complete", "blocked"]
        has_status = any(status in content.lower() for status in valid_statuses)

        if not has_status:
            return False, "No phase statuses found", warnings

        # WARNING: Plan Registry boundary check (positive match: must start with docs/plans/)
        registry_section = False
        for line in content.splitlines():
            if "Plan Registry" in line:
                registry_section = True
                continue
            if registry_section:
                # Stop at next heading
                if line.startswith("#"):
                    break
                if line.startswith("| "):
                    cells = [c.strip() for c in line.split("|") if c.strip()]
                    if cells and not cells[0].startswith("---") and not cells[0].startswith("File"):
                        entry = cells[0]
                        if not entry.startswith("docs/plans/"):
                            warnings.append(
                                f"Plan Registry contains non-plan entry: '{entry}'. "
                                "Only docs/plans/*.md should be registered."
                            )

        return True, "Valid", warnings

    except Exception as e:
        return False, f"Error reading file: {e}", warnings


def validate_snapshot(filepath: Path) -> tuple[bool, str, list[str]]:
    """Validate snapshot.md structure and recency. Returns (valid, message, warnings)."""
    warnings = []
    try:
        content = filepath.read_text(encoding="utf-8")

        # Extract timestamp from header (supports optional timezone like CST)
        match = re.search(r"# Snapshot:\s*(\d{4}-\d{2}-\d{2})\s+(?:[A-Z]{2,5}\s+)?(\d{2}:\d{2})", content)
        if not match:
            return False, "Missing or invalid timestamp in header", warnings

        timestamp_str = f"{match.group(1)} {match.group(2)}"
        snapshot_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
        age = datetime.now() - snapshot_time

        # Stale snapshot is a WARNING, not an error
        if age > timedelta(days=7):
            warnings.append(f"Snapshot is {age.days} days old (stale). Consider regenerating.")

        # Check required sections
        required = ["## Context", "## Next Session Should Know"]
        missing = [sec for sec in required if sec not in content]

        if missing:
            return False, f"Missing sections: {', '.join(missing)}", warnings

        # WARNING: multiple ## Context sections (improper appending)
        context_count = len(re.findall(r"^## Context\b", content, re.MULTILINE))
        if context_count > 1:
            warnings.append(
                f"Snapshot contains {context_count} '## Context' sections. "
                "It appears to have been appended rather than overwritten. "
                "Regenerate with generate_snapshot.py."
            )

        allowed = {"Context", "Recent Progress", "Current Focus", "Blockers", "Files Modified", "Stable Decisions", "Key Findings", "Utilities", "Next Session Should Know"}
        unknown = [match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", content, re.MULTILINE) if match.group(1).strip() not in allowed]
        if unknown:
            warnings.append("Snapshot has unexpected top-level sections: " + ", ".join(unknown[:5]))

        return True, "Valid", warnings

    except Exception as e:
        return False, f"Error reading file: {e}", warnings


def check_forbidden_paths(directory: Path) -> list[str]:
    """Check for artifacts in forbidden paths."""
    violations = []

    for item in directory.rglob("*.md"):
        path_str = str(item)
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden in path_str:
                violations.append(f"{item}: contains forbidden substring '{forbidden}'")

    return violations


def check_utils_sensitivity(directory: Path) -> list[str]:
    """Reject likely credential values in the portable utilities profile."""
    utils = directory / "utils.md"
    if not utils.exists():
        return []
    try:
        content = utils.read_text(encoding="utf-8")
    except OSError:
        return []
    secret_patterns = (
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        r"\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+",
        r"\b(?:AKIA|ghp_|github_pat_)[A-Za-z0-9_-]{8,}",
    )
    return ["utils.md contains a likely secret value; record credential names/access requirements, never values"] \
        if any(re.search(pattern, content, re.I) for pattern in secret_patterns) else []


def check_snapshot_drift(directory: Path) -> list[str]:
    snapshot = directory / "snapshot.md"
    if not snapshot.exists():
        return []
    try:
        snapshot_time = snapshot.stat().st_mtime
        newer = [name for name in ("findings.md", "progress.md", "decisions.md", "utils.md")
                 if (directory / name).exists() and (directory / name).stat().st_mtime > snapshot_time]
    except OSError:
        return []
    return ["snapshot.md is older than: " + ", ".join(newer) + "; regenerate the snapshot"] if newer else []


def verify_mrs(directory: Path) -> dict:
    """Verify MRS completeness and validity."""
    results = {
        "tier0": {"present": [], "missing": [], "invalid": []},
        "tier1": {"present": [], "missing": []},
        "tier2": {"present": [], "missing": []},
        "warnings": [],
        "forbidden_paths": [],
        "exit_code": 0,
    }

    # Check Tier 0 (required)
    validators = {
        "task_state.md": validate_task_state,
        "plan.md": validate_plan,
        "snapshot.md": validate_snapshot,
    }

    for filename in TIER_0:
        filepath = directory / filename
        if not filepath.exists():
            results["tier0"]["missing"].append(filename)
            results["exit_code"] = 1
        else:
            validator = validators.get(filename)
            if validator:
                valid, msg, file_warnings = validator(filepath)
                results["warnings"].extend(file_warnings)
            else:
                valid, msg = True, "Valid"

            if valid:
                results["tier0"]["present"].append(filename)
            else:
                results["tier0"]["invalid"].append(f"{filename}: {msg}")
                results["exit_code"] = 3

    # Check Tier 1 core (missing = degraded)
    for filename in TIER_1_CORE:
        if check_file_exists(directory, filename):
            results["tier1"]["present"].append(filename)
        else:
            results["tier1"]["missing"].append(filename)
            if results["exit_code"] == 0:
                results["exit_code"] = 2

    # Check Tier 1 conditional (missing = warning only, not degraded)
    for filename in TIER_1_CONDITIONAL:
        if check_file_exists(directory, filename):
            results["tier1"]["present"].append(filename)
        else:
            results["tier1"]["missing"].append(filename)
            results["warnings"].append(
                f"{filename} not found (optional for small tasks; "
                "required for multi-session/multi-agent/>10 phase tasks)."
            )

    # Utilities are a portable context profile. Old MRS trees may not have it.
    for filename in TIER_1_OPTIONAL:
        if check_file_exists(directory, filename):
            results["tier1"]["present"].append(filename)
        else:
            results["tier1"]["missing"].append(filename)
            results["warnings"].append(
                "utils.md not found (optional for legacy MRS; create it to preserve tooling, environment, and resource pointers)."
            )

    # Check Tier 2 (informational)
    for filename in TIER_2:
        if check_file_exists(directory, filename):
            results["tier2"]["present"].append(filename)
        else:
            results["tier2"]["missing"].append(filename)

    # Check forbidden paths
    results["forbidden_paths"] = check_forbidden_paths(directory)
    if results["forbidden_paths"] and results["exit_code"] == 0:
        results["exit_code"] = 3

    sensitivity_violations = check_utils_sensitivity(directory)
    results["warnings"].extend(sensitivity_violations)
    if sensitivity_violations:
        results["exit_code"] = 3

    results["warnings"].extend(check_snapshot_drift(directory))

    return results


def print_results(results: dict):
    """Print verification results."""
    print("=" * 60)
    print("MRS VERIFICATION REPORT")
    print("=" * 60)

    # Tier 0
    print("\nTIER 0 (REQUIRED):")
    if results["tier0"]["present"]:
        print("  Present:", ", ".join(results["tier0"]["present"]))
    if results["tier0"]["missing"]:
        print("  MISSING:", ", ".join(results["tier0"]["missing"]))
    if results["tier0"]["invalid"]:
        print("  INVALID:")
        for msg in results["tier0"]["invalid"]:
            print(f"     - {msg}")

    # Tier 1
    print("\nTIER 1 (IMPORTANT):")
    if results["tier1"]["present"]:
        print("  Present:", ", ".join(results["tier1"]["present"]))
    if results["tier1"]["missing"]:
        print("  Missing:", ", ".join(results["tier1"]["missing"]))

    # Tier 2
    print("\nTIER 2 (OPTIONAL):")
    if results["tier2"]["present"]:
        print("  Present:", ", ".join(results["tier2"]["present"]))
    if results["tier2"]["missing"]:
        print("  Not present:", ", ".join(results["tier2"]["missing"]))

    # Warnings
    if results["warnings"]:
        print("\nWARNINGS:")
        for warning in results["warnings"]:
            print(f"  - {warning}")

    # Forbidden paths
    if results["forbidden_paths"]:
        print("\nFORBIDDEN PATH VIOLATIONS:")
        for violation in results["forbidden_paths"]:
            print(f"  - {violation}")

    # Summary
    print("\n" + "=" * 60)
    exit_code = results["exit_code"]

    if exit_code == 0:
        suffix = f" ({len(results['warnings'])} warnings)" if results["warnings"] else ""
        print(f"MRS VALID - Recovery possible{suffix}")
    elif exit_code == 1:
        print("MRS INCOMPLETE - Recovery impossible (missing Tier 0)")
    elif exit_code == 2:
        print("MRS DEGRADED - Recovery possible with warnings (missing Tier 1)")
    elif exit_code == 3:
        print("MRS INVALID - Validation errors detected")

    print("=" * 60)


def print_json(results: dict):
    """Print results as JSON for agent consumption."""
    output = {
        "exit_code": results["exit_code"],
        "status": {
            0: "valid",
            1: "incomplete",
            2: "degraded",
            3: "invalid",
        }.get(results["exit_code"], "unknown"),
        "tier0": results["tier0"],
        "tier1": results["tier1"],
        "tier2": results["tier2"],
        "warnings": results["warnings"],
        "forbidden_paths": results["forbidden_paths"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify MRS completeness and consistency")
    parser.add_argument("directory", nargs="?", default=".", help="MRS directory (default: current)")
    parser.add_argument("--json", action="store_true", help="Output as JSON for agent consumption")

    args = parser.parse_args()
    directory = Path(args.directory)

    if not directory.is_dir():
        if args.json:
            print(json.dumps({"error": f"{directory} is not a directory", "exit_code": 1}))
        else:
            print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    if not args.json:
        print(f"Verifying MRS in: {directory}\n")

    results = verify_mrs(directory)

    if args.json:
        print_json(results)
    else:
        print_results(results)

    sys.exit(results["exit_code"])


if __name__ == "__main__":
    main()
