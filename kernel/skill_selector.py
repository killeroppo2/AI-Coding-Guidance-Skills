"""Skill auto-selection based on goal keyword matching.

This module provides functions for automatically selecting relevant skills
from the knowledge store based on the development goal text, and for
selecting skills by workflow phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.intent_analyzer import IntentResult


def select_skills_for_goal(
    goal: str, available_skills: list[dict], max_skills: int = 5
) -> list[str]:
    """Select relevant skills for a goal by matching keywords against skill metadata.

    .. deprecated::
        Kept as fallback for dry-run mode and initial skill selection.
        For per-node dynamic routing, use :func:`select_skills_dynamic` instead.

    Tokenizes the goal into lowercase words and computes a relevance score for
    each skill by matching goal words against skill tags and description words.
    Tags are weighted higher (3x) than description matches (1x).

    Args:
        goal: The development goal text.
        available_skills: List of skill dicts with keys: name, tags, description.
        max_skills: Maximum number of skills to return (default: 5).

    Returns:
        List of skill names sorted by relevance score (descending),
        excluding skills with score 0. Returns at most max_skills items.
    """
    if not goal or not goal.strip():
        return []
    if not available_skills:
        return []

    goal_words = set(goal.lower().split())

    scored: list[tuple[str, int]] = []
    for skill in available_skills:
        name = skill.get("name", "")
        tags = skill.get("tags", [])
        description = skill.get("description", "")

        # Count matches in tags (weight 3x)
        tag_matches = sum(1 for tag in tags if tag.lower() in goal_words)

        # Count matches in description words (weight 1x)
        desc_words = set(description.lower().split())
        desc_matches = sum(1 for word in goal_words if word in desc_words)

        score = (tag_matches * 3) + (desc_matches * 1)

        # Boost core skills (those not in community/ subdirectory)
        path = skill.get("path", "")
        is_core = not path.startswith("community/")
        if is_core and score > 0:
            score = int(score * 1.5)

        if score > 0:
            scored.append((name, score))

    # Sort by score descending, then by name for stable ordering
    scored.sort(key=lambda x: (-x[1], x[0]))

    return [name for name, _ in scored[:max_skills]]


def select_skills_for_phase(phase: str, workflow: dict) -> list[str]:
    """Return skills for a given workflow phase from the workflow dict.

    Args:
        phase: The workflow phase name (e.g. 'idea_phase', 'execution_phase').
        workflow: The workflow dict mapping phase names to skill name lists.

    Returns:
        List of skill names for the given phase, or empty list if phase
        is not found in the workflow dict.
    """
    if not phase or not workflow:
        return []
    skills: list[str] = workflow.get(phase, [])
    return skills


def select_skills_dynamic(
    node_id: str,
    intent: "IntentResult",
    complexity: str,
    available_skills: list[dict],
    workflow: dict,
) -> list[str]:
    """Dynamically select skills for a specific node using PhaseRouter.

    Creates a PhaseRouter instance and delegates routing to it, returning
    the combined primary + auxiliary skill names.

    Args:
        node_id: Current graph node identifier.
        intent: Analyzed IntentResult from IntentAnalyzer.
        complexity: Complexity level ('low', 'medium', 'high').
        available_skills: List of skill dicts with core_items/community_items structure.
        workflow: Dict mapping phase names to lists of skill names (core_workflow).

    Returns:
        Combined list of primary and auxiliary skill names for this node.
    """
    from kernel.phase_router import PhaseRouter

    # Build skills_index dict from available_skills
    # available_skills is the combined items list; reconstruct the index structure
    skills_index: dict = {
        "core_items": [
            s for s in available_skills
            if not s.get("path", "").startswith("community/")
        ],
        "community_items": [
            s for s in available_skills
            if s.get("path", "").startswith("community/")
        ],
    }

    router = PhaseRouter(skills_index, workflow)
    selection = router.route(node_id, intent, complexity)
    return selection.primary + selection.auxiliary
