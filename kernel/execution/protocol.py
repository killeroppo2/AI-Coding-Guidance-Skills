"""Shared protocol utilities for execution strategies.

Contains node transition logic, stuck detection helpers, and progress tracking.
"""

import json
from pathlib import Path

from kernel.philosophy.principles import should_stop_iterating

# Maximum number of progress history entries to retain
MAX_PROGRESS_HISTORY_ENTRIES = 20

# Number of recent reflections to check for stop-iterating philosophy
RECENT_REFLECTIONS_WINDOW = 10


def resolve_transition(
    transitions: list[dict],
    transition_condition: str | None,
    complexity: str,
    logger,
) -> tuple[str, bool]:
    """Resolve the next node from available transitions and AI-provided condition.

    Args:
        transitions: List of transition dicts from graph.
        transition_condition: The condition parsed from AI output, or None.
        complexity: Current complexity level.
        logger: Logger instance for warnings.

    Returns:
        Tuple of (next_node_id, had_warning).
    """
    had_warning = False
    if transition_condition:
        matched = False
        next_node_id = ""
        for t in transitions:
            if t.get("condition") == transition_condition:
                next_node_id = t["to"]
                matched = True
                break
        if not matched:
            next_node_id = transitions[0]["to"]
            logger.warning(
                f"[警告] TRANSITION 条件 '{transition_condition}' "
                f"不匹配任何可用转换，"
                f"回退到第一个转换: {next_node_id}"
            )
            had_warning = True
    else:
        next_node_id = transitions[0]["to"]
        had_warning = True

    # Medium complexity: skip reflect/evolve
    if complexity == "medium" and next_node_id in ("reflect", "evolve"):
        next_node_id = "plan"

    return next_node_id, had_warning


def check_should_stop(memory_dir: str, state: dict) -> bool:
    """Check if iteration should stop based on philosophy heuristics.

    Args:
        memory_dir: Path to memory directory.
        state: Current state dict.

    Returns:
        True if iteration should stop.
    """
    reflections_path = Path(memory_dir) / "reflections.jsonl"
    recent_reflections: list[dict] = []
    if reflections_path.exists():
        lines = reflections_path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-RECENT_REFLECTIONS_WINDOW:]:
            try:
                recent_reflections.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                pass
    return should_stop_iterating(state, recent_reflections)


def update_progress_history(state: dict, memory_dir: str) -> None:
    """Update progress_history in state from tasks.yaml.

    Args:
        state: Current state dict to update.
        memory_dir: Path to memory directory.
    """
    from kernel.task_manager import TaskManager

    tasks_path_progress = Path(memory_dir) / "tasks.yaml"
    if tasks_path_progress.exists():
        tm_progress = TaskManager(memory_dir)
        _total, tasks_done_count = tm_progress.get_progress()
        if _total > 0:
            progress_history = state.setdefault("progress_history", [])
            progress_history.append(tasks_done_count)
            if len(progress_history) > MAX_PROGRESS_HISTORY_ENTRIES:
                state["progress_history"] = progress_history[-MAX_PROGRESS_HISTORY_ENTRIES:]
