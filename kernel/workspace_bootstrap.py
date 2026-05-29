"""Workspace bootstrap utilities for generating project-specific CLAUDE.md files.

When using Claude Code (claude --print), a CLAUDE.md file in the workspace
directory will be automatically read and followed by the AI agent.
"""

from __future__ import annotations

from pathlib import Path


def generate_claude_md(
    workspace_path: str,
    goal: str,
    tasks: list[dict] | None = None,
) -> Path:
    """Generate a CLAUDE.md file in the workspace directory.

    Creates a project-specific CLAUDE.md containing workspace rules,
    output format requirements, and the project goal. This file is
    read by Claude Code to enforce workspace boundaries and output format.

    Args:
        workspace_path: Path to the workspace directory (e.g., './workspace/my-project/').
        goal: The project goal description.
        tasks: Optional list of task dicts from the plan.

    Returns:
        Path to the generated CLAUDE.md file.
    """
    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)
    claude_md_path = workspace / "CLAUDE.md"

    # Do not overwrite existing CLAUDE.md (idempotent)
    if claude_md_path.exists():
        return claude_md_path

    content = _build_claude_md_content(workspace_path, goal, tasks)
    claude_md_path.write_text(content, encoding="utf-8")
    return claude_md_path


def _build_claude_md_content(
    workspace_path: str,
    goal: str,
    tasks: list[dict] | None = None,
) -> str:
    """Build the CLAUDE.md content string.

    Args:
        workspace_path: Path to the workspace directory.
        goal: The project goal description.
        tasks: Optional list of task dicts.

    Returns:
        The full CLAUDE.md content as a string.
    """
    sections = []

    sections.append("# CLAUDE.md - Project Rules\n")

    # Workspace section
    sections.append("## Workspace\n")
    sections.append(f"All code for this project lives in: `{workspace_path}`\n")
    sections.append(
        "**ALL file paths in FILES_WRITTEN MUST use this workspace path as prefix.**\n"
    )
    sections.append(
        f"Example: `FILES_WRITTEN: {workspace_path}src/main.py, "
        f"{workspace_path}tests/test_main.py`\n"
    )

    # Goal section
    sections.append("## Goal\n")
    sections.append(f"{goal}\n")

    # Tasks section (if provided)
    if tasks:
        sections.append("## Current Tasks\n")
        for task in tasks:
            task_id = task.get("id", "?")
            title = task.get("title", task.get("description", ""))
            status = task.get("status", "pending")
            sections.append(f"- [{status}] {task_id}: {title}")
        sections.append("")

    # Output format section
    sections.append("## Output Format (MANDATORY)\n")
    sections.append("Every response MUST end with these lines as plain text ")
    sections.append("(NOT inside a code block):\n")
    sections.append("```")
    sections.append("STATUS: success")
    sections.append("TRANSITION: <condition>")
    sections.append("```\n")
    sections.append("If you wrote files, include BEFORE the STATUS line:\n")
    sections.append("```")
    sections.append(
        f"FILES_WRITTEN: {workspace_path}src/file.py, {workspace_path}tests/test.py"
    )
    sections.append("```\n")
    sections.append("Valid STATUS values: `success`, `failure`\n")
    sections.append(
        "Valid TRANSITION values depend on current node "
        "(goal_loaded, plan_ready, code_written, tests_pass, "
        "review_pass, evolution_proposed, no_evolution_needed).\n"
    )

    # Rules section
    sections.append("## Rules\n")
    sections.append(f"1. NEVER write files outside `{workspace_path}`")
    sections.append(
        "2. ALWAYS include STATUS and TRANSITION lines at the end of your response"
    )
    sections.append(
        "3. FILES_WRITTEN paths must be absolute or start with the workspace path"
    )
    sections.append("4. Follow existing code style in this workspace")
    sections.append("5. Do not modify kernel/, memory/, or knowledge/ directories")
    sections.append("")

    return "\n".join(sections)
