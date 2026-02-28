#!/usr/bin/env python3
"""
Verify Minimum Recovery Set (MRS) completeness and consistency.

Usage:
    python verify_mrs.py [directory]

Exit codes:
    0: All Tier 0 files present and valid
    1: Missing Tier 0 files (recovery impossible)
    2: Tier 1 files missing (recovery degraded)
    3: Validation errors (files malformed)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import re

# MRS Tiers
TIER_0 = ["task_state.md", "plan.md", "snapshot.md"]
TIER_1 = ["findings.md", "progress.md", "architecture.md"]
TIER_2 = ["decisions.md", "blockers.md"]

FORBIDDEN_SUBSTRINGS = ["/.cursor/", "/agent-tools/", "/temp/", "/tmp/", "/.cache/"]


def check_file_exists(directory: Path, filename: str) -> bool:
    """Check if file exists in directory."""
    return (directory / filename).exists()


def validate_task_state(filepath: Path) -> tuple[bool, str]:
    """Validate task_state.md structure."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Required sections
        required = ["# Task State", "## Goal", "## Current Phase", "## Next Action"]
        missing = [sec for sec in required if sec not in content]

        if missing:
            return False, f"Missing sections: {', '.join(missing)}"

        # Check for timestamp
        if "**Last Updated:**" not in content:
            return False, "Missing Last Updated timestamp"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_plan(filepath: Path) -> tuple[bool, str]:
    """Validate plan.md structure."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Should have at least one phase
        if not re.search(r"##?\s+Phase\s+\d+", content):
            return False, "No phases found"

        # Check for phase statuses
        valid_statuses = ["pending", "in_progress", "complete", "blocked"]
        has_status = any(status in content.lower() for status in valid_statuses)

        if not has_status:
            return False, "No phase statuses found"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading file: {e}"


def validate_snapshot(filepath: Path) -> tuple[bool, str]:
    """Validate snapshot.md structure and recency."""
    try:
        content = filepath.read_text(encoding="utf-8")

        # Extract timestamp from header
        match = re.search(r"# Snapshot:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", content)
        if not match:
            return False, "Missing or invalid timestamp in header"

        timestamp_str = match.group(1)
        snapshot_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
        age = datetime.now() - snapshot_time

        # Warn if >7 days old
        if age > timedelta(days=7):
            return False, f"Snapshot is {age.days} days old (stale)"

        # Check required sections
        required = ["## Context", "## Next Session Should Know"]
        missing = [sec for sec in required if sec not in content]

        if missing:
            return False, f"Missing sections: {', '.join(missing)}"

        return True, "Valid"

    except Exception as e:
        return False, f"Error reading file: {e}"


def check_forbidden_paths(directory: Path) -> list[str]:
    """Check for artifacts in forbidden paths."""
    violations = []

    for item in directory.rglob("*.md"):
        path_str = str(item)
        for forbidden in FORBIDDEN_SUBSTRINGS:
            if forbidden in path_str:
                violations.append(f"{item}: contains forbidden substring '{forbidden}'")

    return violations


def verify_mrs(directory: Path) -> dict:
    """Verify MRS completeness and validity."""
    results = {
        "tier0": {"present": [], "missing": [], "invalid": []},
        "tier1": {"present": [], "missing": []},
        "tier2": {"present": [], "missing": []},
        "forbidden_paths": [],
        "exit_code": 0,
    }

    # Check Tier 0 (required)
    for filename in TIER_0:
        filepath = directory / filename
        if not filepath.exists():
            results["tier0"]["missing"].append(filename)
            results["exit_code"] = 1
        else:
            # Validate structure
            if filename == "task_state.md":
                valid, msg = validate_task_state(filepath)
            elif filename == "plan.md":
                valid, msg = validate_plan(filepath)
            elif filename == "snapshot.md":
                valid, msg = validate_snapshot(filepath)
            else:
                valid, msg = True, "Valid"

            if valid:
                results["tier0"]["present"].append(filename)
            else:
                results["tier0"]["invalid"].append(f"{filename}: {msg}")
                results["exit_code"] = 3

    # Check Tier 1 (warnings)
    for filename in TIER_1:
        if check_file_exists(directory, filename):
            results["tier1"]["present"].append(filename)
        else:
            results["tier1"]["missing"].append(filename)
            if results["exit_code"] == 0:
                results["exit_code"] = 2

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

    return results


def print_results(results: dict):
    """Print verification results."""
    print("=" * 60)
    print("MRS VERIFICATION REPORT")
    print("=" * 60)

    # Tier 0
    print("\n📋 TIER 0 (REQUIRED):")
    if results["tier0"]["present"]:
        print("  ✅ Present:", ", ".join(results["tier0"]["present"]))
    if results["tier0"]["missing"]:
        print("  ❌ MISSING:", ", ".join(results["tier0"]["missing"]))
    if results["tier0"]["invalid"]:
        print("  ⚠️  INVALID:")
        for msg in results["tier0"]["invalid"]:
            print(f"     - {msg}")

    # Tier 1
    print("\n📚 TIER 1 (IMPORTANT):")
    if results["tier1"]["present"]:
        print("  ✅ Present:", ", ".join(results["tier1"]["present"]))
    if results["tier1"]["missing"]:
        print("  ⚠️  Missing:", ", ".join(results["tier1"]["missing"]))

    # Tier 2
    print("\n📝 TIER 2 (OPTIONAL):")
    if results["tier2"]["present"]:
        print("  ✅ Present:", ", ".join(results["tier2"]["present"]))
    if results["tier2"]["missing"]:
        print("  ℹ️  Not present:", ", ".join(results["tier2"]["missing"]))

    # Forbidden paths
    if results["forbidden_paths"]:
        print("\n🚫 FORBIDDEN PATH VIOLATIONS:")
        for violation in results["forbidden_paths"]:
            print(f"  - {violation}")

    # Summary
    print("\n" + "=" * 60)
    exit_code = results["exit_code"]

    if exit_code == 0:
        print("✅ MRS VALID - Recovery possible")
    elif exit_code == 1:
        print("❌ MRS INCOMPLETE - Recovery impossible (missing Tier 0)")
    elif exit_code == 2:
        print("⚠️  MRS DEGRADED - Recovery possible with warnings (missing Tier 1)")
    elif exit_code == 3:
        print("❌ MRS INVALID - Validation errors detected")

    print("=" * 60)


def main():
    """Main entry point."""
    # Get directory from args or use current
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Verifying MRS in: {directory}\n")

    results = verify_mrs(directory)
    print_results(results)

    sys.exit(results["exit_code"])


if __name__ == "__main__":
    main()
