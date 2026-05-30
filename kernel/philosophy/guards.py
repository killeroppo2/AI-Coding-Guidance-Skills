"""Executable philosophy guards - translate principles into runtime constraints.

Wu Wei (non-action): Stop iterating when making no progress.
Shui (water): Flow around obstacles by avoiding failing skills.
Bing Gui Shen Su (military values speed): Detect stalling early, force simplification.
"""

from __future__ import annotations


def wu_wei_guard(state: dict, proposed_action: str = "iterate") -> bool:
    """Wu Wei - non-action when stuck.

    Returns False if the system is iterating without progress, signaling
    that the proposed action should NOT be taken.

    Checks state['progress_history']: if the last 3+ entries have the
    same value, progress has stalled. However, if recent errors contain
    workspace/security/boundary/contract keywords, these are retryable
    issues and the guard allows continuation.

    Args:
        state: The current state dict (may contain progress_history, errors).
        proposed_action: Description of proposed action (for logging context).

    Returns:
        True if action should proceed, False if system should stop.
    """
    progress_history = state.get("progress_history", [])
    if len(progress_history) >= 3:
        last_three = progress_history[-3:]
        if len(set(last_three)) == 1:
            # Check if recent errors are retryable path/security issues
            errors = state.get("errors", [])
            recent_errors = errors[-3:] if errors else []
            retryable_keywords = ("workspace", "security", "boundary", "contract")
            for err in recent_errors:
                err_lower = err.lower() if isinstance(err, str) else ""
                if any(kw in err_lower for kw in retryable_keywords):
                    return True
            return False
    return True


def shui_guard(
    proposed_skills: list[str],
    feedback_store,
    node_id: str,
    goal_type: str,
) -> list[str]:
    """Shui (water) - flow around obstacles.

    Filters out skills with >70% recent failure rate for the given
    node and goal type. If ALL skills would be filtered, returns
    the original list unchanged (preserve at least some options).

    Args:
        proposed_skills: List of skill names to evaluate.
        feedback_store: SkillFeedbackStore instance for querying history.
        node_id: The current graph node.
        goal_type: The current goal type.

    Returns:
        Filtered list of skills (or original list if all would be removed).
    """
    if not proposed_skills:
        return proposed_skills

    entries = feedback_store._read_entries()
    # Filter entries to current node and goal_type
    relevant = [
        e for e in entries
        if e.get("node_id") == node_id and e.get("goal_type") == goal_type
    ]

    # Compute per-skill failure rate
    skill_stats: dict[str, dict[str, int]] = {}
    for entry in relevant:
        for skill in entry.get("skills_used", []):
            if skill not in skill_stats:
                skill_stats[skill] = {"successes": 0, "failures": 0}
            if entry.get("outcome") == "success":
                skill_stats[skill]["successes"] += 1
            else:
                skill_stats[skill]["failures"] += 1

    # Filter out skills with >70% failure rate (need at least 3 data points)
    filtered = []
    for skill in proposed_skills:
        stats = skill_stats.get(skill)
        if stats is None:
            filtered.append(skill)  # No data, keep it
            continue
        total = stats["successes"] + stats["failures"]
        if total < 3:
            filtered.append(skill)  # Not enough data, keep it
            continue
        failure_rate = stats["failures"] / total
        if failure_rate <= 0.7:
            filtered.append(skill)

    # If all would be filtered, return original list
    if not filtered:
        return proposed_skills

    return filtered


def bing_gui_shen_su(iteration_count: int, tasks_done: int) -> str:
    """Bing Gui Shen Su - military values speed.

    If 10+ iterations have passed with 0 tasks completed, returns "low"
    to signal that complexity should be downgraded. Otherwise returns "keep".

    Args:
        iteration_count: Number of iterations completed so far.
        tasks_done: Number of tasks marked as done.

    Returns:
        "low" if complexity should be downgraded, "keep" otherwise.
    """
    if iteration_count >= 10 and tasks_done == 0:
        return "low"
    return "keep"
