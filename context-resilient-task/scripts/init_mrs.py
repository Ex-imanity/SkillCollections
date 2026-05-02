#!/usr/bin/env python3
"""
Initialize a Minimum Recovery Set (MRS) for a new task.

Usage:
    # CLI mode (all required args present, non-interactive):
    python init_mrs.py --goal "Build auth module" --complexity large \
        --requirements "JWT;refresh tokens;rate limiting"

    # Interactive mode (missing --goal or --complexity triggers prompts):
    python init_mrs.py

Options:
    --dir PATH          Target MRS directory (default: ./.task-state)
    --goal TEXT         One-sentence task goal
    --complexity LEVEL  small | medium | large
    --requirements TEXT Semicolon-separated list, e.g. "a;b;c"
    --multi-agent       Mark task as multi-agent (forces decisions.md creation)
    --force             Allow writing into a non-empty target directory
    --agent NAME        Identifier for "Updated By" (default: "user (init)")

Decisions.md auto-creation rule:
    Created when --multi-agent OR --complexity large OR len(requirements) > 10.
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path
from datetime import datetime

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"
REFERENCES_DIR = SKILL_ROOT / "references"
TEMPLATE_DOCS_MARKER = "<!--END_TEMPLATE_DOCS-->\n"

VALID_COMPLEXITY = ("small", "medium", "large")


def load_template(name: str) -> str:
    """Load a template from assets/, stripping internal docs preamble."""
    path = ASSETS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    raw = path.read_text(encoding="utf-8")
    if TEMPLATE_DOCS_MARKER in raw:
        _, _, body = raw.partition(TEMPLATE_DOCS_MARKER)
        return body
    return raw


def prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer or default


def collect_inputs(args: argparse.Namespace) -> argparse.Namespace:
    """Fill missing required args via interactive prompts."""
    if not args.goal:
        args.goal = prompt("Task goal (one sentence)")
        if not args.goal:
            sys.exit("Error: goal is required")
    if not args.complexity:
        comp = prompt("Complexity (small/medium/large)", "medium")
        if comp not in VALID_COMPLEXITY:
            sys.exit(f"Error: invalid complexity '{comp}'")
        args.complexity = comp
    if args.requirements is None:
        args.requirements = prompt(
            "Key requirements (semicolon-separated, optional)", ""
        )
    return args


def parse_requirements(text: str) -> list[str]:
    if not text:
        return []
    return [r.strip() for r in text.split(";") if r.strip()]


def render_phases(requirements: list[str]) -> str:
    if not requirements:
        return (
            "## Phase 1: Planning\n"
            "**Status:** pending\n"
            "**Description:** Refine task into concrete phases.\n"
            "**Deliverables:**\n"
            "- Concrete plan.md phases\n"
        )
    blocks = []
    for i, req in enumerate(requirements, 1):
        blocks.append(
            f"## Phase {i}: {req}\n"
            f"**Status:** pending\n"
            f"**Description:** TODO — describe how this phase delivers \"{req}\".\n"
            f"**Deliverables:**\n"
            f"- TODO\n"
        )
    return "\n".join(blocks)


def render_task_state(goal: str, requirements: list[str], agent: str) -> str:
    template = load_template("task_state.template.md")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")

    if requirements:
        active_todos = "\n".join(
            f"- [ ] {req} (added: {today}, source: plan Phase {i})"
            for i, req in enumerate(requirements, 1)
        )
        current_phase = f"Phase 1: {requirements[0]}"
        next_action = f"Begin Phase 1: {requirements[0]}"
    else:
        active_todos = "_(no active todos yet — define via plan.md phases)_"
        current_phase = "Phase 1: Planning"
        next_action = "Refine plan.md phases and add concrete todos"

    artifacts = (
        "- plan.md (created at init)\n"
        "- snapshot.md (created at init)"
    )

    return template.format(
        timestamp=timestamp,
        agent=agent,
        goal=goal,
        status="active",
        active_todos=active_todos,
        current_phase=current_phase,
        next_action=next_action,
        completed_items="_(none)_",
        open_questions="_(none)_",
        artifacts=artifacts,
    )


def render_plan(goal: str, requirements: list[str]) -> str:
    template = load_template("plan.template.md")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.format(
        timestamp=timestamp,
        goal=goal,
        phases=render_phases(requirements).rstrip(),
    )


def render_initial_snapshot(goal: str, requirements: list[str]) -> str:
    template = load_template("snapshot.template.md")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    current_focus = (
        f"Begin Phase 1: {requirements[0]}" if requirements else "Refine plan.md phases"
    )
    return template.format(
        timestamp=timestamp,
        context=f"Initialized MRS for goal: {goal}",
        recent_progress="- (Initial snapshot — no progress yet)",
        current_focus=current_focus,
        blockers="- (None)",
        files_modified="- (No source changes yet)",
        next_session_notes=f"- Goal: {goal}\n- Next action: {current_focus}",
    )


def needs_decisions(complexity: str, multi_agent: bool, requirements: list[str]) -> bool:
    return multi_agent or complexity == "large" or len(requirements) > 10


def write_files(
    target_dir: Path,
    goal: str,
    requirements: list[str],
    complexity: str,
    multi_agent: bool,
    agent: str,
    force: bool,
) -> dict[str, Path]:
    """Render and write MRS files. Returns mapping of filename → written path."""
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        suggestion = target_dir.parent / f"{target_dir.name}-<slug>"
        raise FileExistsError(
            f"{target_dir} is non-empty.\n"
            "\nTo start a parallel task without destroying existing MRS, use a sibling directory:\n"
            f"  --dir {suggestion}\n"
            "(replace <slug> with a short task identifier, e.g. 'auth' or 'bugfix-x42')\n"
            "\nOr use --force to overwrite (DESTRUCTIVE - loses current MRS state)."
        )
    target_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {
        "task_state.md": render_task_state(goal, requirements, agent),
        "plan.md": render_plan(goal, requirements),
        "snapshot.md": render_initial_snapshot(goal, requirements),
        "findings.md": (
            "# Findings\n\n"
            "<!-- Append research notes and discoveries below this line. -->\n"
        ),
        "progress.md": (
            "# Progress\n\n"
            "<!-- Append chronological execution log entries below this line. -->\n"
        ),
    }

    if needs_decisions(complexity, multi_agent, requirements):
        decisions_path = ASSETS_DIR / "decisions.template.md"
        files["decisions.md"] = decisions_path.read_text(encoding="utf-8")

    written: dict[str, Path] = {}
    for name, content in files.items():
        path = target_dir / name
        path.write_text(content, encoding="utf-8")
        written[name] = path

    return written


def print_post_init_guidance(target_dir: Path, created: dict[str, Path]) -> None:
    print()
    print("=" * 60)
    print("MRS initialized")
    print("=" * 60)
    for name, path in created.items():
        print(f"  Created: {path}")
    print()
    print("Next steps:")
    print(f"  1. Review and refine: {target_dir / 'plan.md'}")
    print(f"  2. Add concrete todos to: {target_dir / 'task_state.md'} (Active Todos)")
    print(f"  3. Append execution notes to: {target_dir / 'progress.md'}")
    print("  4. If multi-agent, copy MRS rules into your project's AGENTS.md:")
    print(f"     source: {REFERENCES_DIR / 'agents-md-snippet.md'}")
    print()
    print(f"  Validate: python {SKILL_ROOT / 'scripts' / 'verify_mrs.py'} {target_dir}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a Minimum Recovery Set (MRS) for a new task.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dir", default=".task-state", help="Target MRS directory (default: ./.task-state)")
    parser.add_argument("--goal", default=None, help="One-sentence task goal")
    parser.add_argument("--complexity", choices=VALID_COMPLEXITY, default=None)
    parser.add_argument(
        "--requirements", default=None,
        help='Semicolon-separated list, e.g. "JWT;refresh tokens;rate limiting"',
    )
    parser.add_argument("--multi-agent", action="store_true",
                        help="Mark task as multi-agent (forces decisions.md creation)")
    parser.add_argument("--force", action="store_true",
                        help="Allow writing into a non-empty target directory")
    parser.add_argument("--agent", default="user (init)",
                        help='Identifier for the "Updated By" field')

    args = parser.parse_args()

    needs_interactive = args.goal is None or args.complexity is None
    if needs_interactive:
        if sys.stdin.isatty():
            args = collect_inputs(args)
        else:
            parser.error(
                "--goal and --complexity are required in non-interactive mode"
            )

    requirements = parse_requirements(args.requirements or "")
    target_dir = Path(args.dir).resolve()

    try:
        created = write_files(
            target_dir=target_dir,
            goal=args.goal,
            requirements=requirements,
            complexity=args.complexity,
            multi_agent=args.multi_agent,
            agent=args.agent,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print_post_init_guidance(target_dir, created)
    return 0


if __name__ == "__main__":
    sys.exit(main())
