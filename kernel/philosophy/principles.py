"""Operational heuristics derived from philosophy (dao.md, strategy.md).

These functions translate philosophical principles into concrete decision
signals that the kernel uses during execution.
"""

from collections import Counter


def should_stop_iterating(state: dict, reflections: list[dict]) -> bool:
    """Know when to stop to avoid danger.

    Returns True if diminishing returns detected:
    - Same errors repeating 3+ times in recent reflections
    - tasks_done has not changed across last 5 progress_history entries

    Args:
        state: The current state dict (may contain progress_history).
        reflections: List of recent reflection dicts.

    Returns:
        True if iteration should stop due to diminishing returns.
    """
    # Check for repeating errors in reflections
    if reflections:
        error_counts: Counter = Counter()
        for reflection in reflections:
            for issue in reflection.get("issues", []):
                error_counts[issue] += 1
        for _error, count in error_counts.items():
            if count >= 3:
                return True

    # Check for stalled progress_history
    progress_history = state.get("progress_history", [])
    if len(progress_history) >= 5:
        last_five = progress_history[-5:]
        if len(set(last_five)) == 1:
            return True

    return False


def should_simplify(failure_count: int) -> bool:
    """The greatest Dao is the simplest.

    Returns True if failure_count >= 3, suggesting the task should be split.

    Args:
        failure_count: Number of consecutive failures for this task.

    Returns:
        True if the task should be simplified (split).
    """
    return failure_count >= 3


def should_retreat(node_id: str, consecutive_failures: int, max_retries: int = 5) -> bool:
    """Of the 36 stratagems, retreat is best.

    Returns True if consecutive_failures >= max_retries for the node.
    Signals the runner should skip this node and move on.

    Args:
        node_id: The node identifier.
        consecutive_failures: Number of consecutive failures for this node.
        max_retries: Maximum retries allowed (default 5).

    Returns:
        True if the node should be abandoned.
    """
    return consecutive_failures >= max_retries


def assess_terrain(goal: str, available_skills: list[dict]) -> dict:
    """Know heaven and know earth.

    Delegates to CapabilityAssessor.assess_capabilities for consistent
    goal-skill matching, then maps the output to the assess_terrain format.

    Args:
        goal: The goal string to assess.
        available_skills: List of skill dicts with 'name', 'tags', 'description' fields.

    Returns:
        Dict with coverage_score (float 0.0-1.0), covered (list of skill names),
        gaps (list of goal keywords with no matching skill),
        recommendation ("proceed"|"proceed_with_caution"|"reconsider").
    """
    from kernel.capability_assessment import CapabilityAssessor

    assessor = CapabilityAssessor()
    result = assessor.assess_capabilities(goal, available_skills)

    confidence = result.get("confidence", 0.0)
    covered = result.get("covered", [])
    gaps = result.get("gaps", [])

    # Map confidence to recommendation using thresholds
    if confidence >= 0.7:
        recommendation = "proceed"
    elif confidence >= 0.4:
        recommendation = "proceed_with_caution"
    else:
        recommendation = "reconsider"

    return {
        "coverage_score": confidence,
        "covered": covered,
        "gaps": gaps,
        "recommendation": recommendation,
    }
