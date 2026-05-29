"""Phase-aware skill router for dynamic per-node skill selection."""

from __future__ import annotations

from dataclasses import dataclass, field

from kernel.intent_analyzer import IntentResult


@dataclass
class SkillSelection:
    """Result of a routing decision for a given node."""

    primary: list[str] = field(default_factory=list)
    auxiliary: list[str] = field(default_factory=list)
    reason: str = ""


# Mapping from graph node_id to workflow phase key
_NODE_TO_PHASE: dict[str, str] = {
    "init": "none",
    "plan": "requirements_phase",
    "code": "execution_phase",
    "test": "execution_phase",
    "review": "quality_phase",
    "reflect": "lifecycle_phase",
    "evolve": "meta_phase",
}


class PhaseRouter:
    """Select skills dynamically per node based on intent, complexity, and composable_with."""

    def __init__(self, skills_index: dict, workflow: dict) -> None:
        """Initialize the router with skills index and workflow data.

        Args:
            skills_index: Dict containing core_items and community_items lists.
            workflow: Dict mapping phase names to lists of skill names.
        """
        self._skills_index = skills_index
        self._workflow = workflow
        self._composable_map = self._build_composable_map()

    def _build_composable_map(self) -> dict[str, list[str]]:
        """Build a mapping from skill name to its composable_with list."""
        result: dict[str, list[str]] = {}
        for item in self._skills_index.get("core_items", []):
            result[item["name"]] = item.get("composable_with", [])
        for item in self._skills_index.get("community_items", []):
            result[item["name"]] = item.get("composable_with", [])
        return result

    def route(
        self,
        node_id: str,
        intent: IntentResult,
        complexity: str,
        history: list[str] | None = None,
        recommendations: list[str] | None = None,
    ) -> SkillSelection:
        """Route to appropriate skills for the given node.

        Args:
            node_id: Current graph node identifier.
            intent: Analyzed intent from IntentAnalyzer.
            complexity: Complexity level ('low', 'medium', 'high').
            history: Optional list of previously visited node IDs.
            recommendations: Optional list of recommended skills from feedback store.

        Returns:
            SkillSelection with primary skills, auxiliary skills, and reasoning.
        """
        primary = self._select_primary(node_id, intent, complexity)

        # Boost recommended skills to primary (from feedback store)
        if recommendations:
            for rec_skill in recommendations:
                if rec_skill in self._composable_map and rec_skill not in primary:
                    primary.append(rec_skill)

        phase = _NODE_TO_PHASE.get(node_id, "none")
        auxiliary = self._select_auxiliary(primary, phase)
        reason = self._build_reason(node_id, intent, complexity, primary)

        return SkillSelection(primary=primary, auxiliary=auxiliary, reason=reason)

    def _select_primary(
        self, node_id: str, intent: IntentResult, complexity: str
    ) -> list[str]:
        """Select primary skills using data-driven scoring with fallback.

        Scores candidates from the workflow against intent and complexity.
        Falls back to hardcoded logic when no candidates score > 0.

        Args:
            node_id: Current graph node identifier.
            intent: Analyzed intent from IntentAnalyzer.
            complexity: Complexity level ('low', 'medium', 'high').

        Returns:
            List of selected skill names (up to 3).
        """
        phase_key = _NODE_TO_PHASE.get(node_id, "none")
        if phase_key == "none":
            return self._fallback_primary(node_id, intent, complexity)

        candidates = self._workflow.get(phase_key, [])
        if not candidates:
            return self._fallback_primary(node_id, intent, complexity)

        scored: list[tuple[str, int]] = []
        for skill_name in candidates:
            meta = self._get_skill_metadata(skill_name)
            if meta is None:
                continue
            tags = meta.get("tags", [])
            if not tags:
                continue
            score = 0
            # +1 for each tag matching a tech_hint
            for tag in tags:
                if tag in intent.tech_hints:
                    score += 1
            # +1 if goal_type appears in tags
            if intent.goal_type in tags:
                score += 1
            # +1 if output_form appears in tags
            if intent.output_form in tags:
                score += 1
            # +1 for complexity match
            if complexity == "high" and any(
                t in tags for t in ("testing", "architecture", "tdd", "quality")
            ):
                score += 1
            elif complexity == "low" and any(
                t in tags for t in ("rapid", "prototype", "simple")
            ):
                score += 1
            if score > 0:
                scored.append((skill_name, score))

        if not scored:
            return self._fallback_primary(node_id, intent, complexity)

        scored.sort(key=lambda x: x[1], reverse=True)
        return [name for name, _ in scored[:3]]

    def _get_skill_metadata(self, skill_name: str) -> dict | None:
        """Look up skill metadata by name from core_items or community_items.

        Args:
            skill_name: The skill name to search for.

        Returns:
            The skill metadata dict if found, otherwise None.
        """
        for item in self._skills_index.get("core_items", []):
            if item.get("name") == skill_name:
                return item
        for item in self._skills_index.get("community_items", []):
            if item.get("name") == skill_name:
                return item
        return None

    def _fallback_primary(
        self, node_id: str, intent: IntentResult, complexity: str
    ) -> list[str]:
        """Fallback primary skill selection using hardcoded logic.

        Args:
            node_id: Current graph node identifier.
            intent: Analyzed intent from IntentAnalyzer.
            complexity: Complexity level ('low', 'medium', 'high').

        Returns:
            List of selected skill names.
        """
        if node_id == "init":
            return []

        if node_id == "plan":
            if intent.is_vague:
                return ["grill-me", "prd"]
            return ["prd"]

        if node_id == "code":
            if intent.goal_type == "explore":
                return ["prototype"]
            if complexity == "high":
                return ["tdd", "ralph"]
            return ["ralph"]

        if node_id == "test":
            return ["tdd"]

        if node_id == "review":
            return ["relentless-iteration"]

        if node_id == "reflect":
            return ["zoom-out"]

        if node_id == "evolve":
            return ["write-a-skill"]

        # Unknown node - return empty selection
        return []

    def _select_auxiliary(self, primary: list[str], phase: str) -> list[str]:
        """Select auxiliary skills from composable_with that are in the current phase.

        Adds up to 2 auxiliary skills that:
        1. Appear in composable_with of any primary skill
        2. Also appear in the current phase's candidate list from the workflow
        3. Are not already in primary
        """
        if phase == "none" or not primary:
            return []

        # Get candidate skills for this phase from the workflow
        phase_candidates = set(self._workflow.get(phase, []))
        if not phase_candidates:
            return []

        # Collect composable skills from all primary skills
        composable: set[str] = set()
        for skill in primary:
            composable.update(self._composable_map.get(skill, []))

        # Filter: must be in phase candidates AND not already primary
        primary_set = set(primary)
        eligible = [
            s for s in composable if s in phase_candidates and s not in primary_set
        ]

        # Deduplicate while preserving order, limit to 2
        seen: set[str] = set()
        result: list[str] = []
        for s in eligible:
            if s not in seen:
                seen.add(s)
                result.append(s)
                if len(result) >= 2:
                    break

        return result

    def _build_reason(
        self,
        node_id: str,
        intent: IntentResult,
        complexity: str,
        primary: list[str],
    ) -> str:
        """Build a human-readable reason for the routing decision."""
        if node_id == "init":
            return "init node requires no skills"

        if not primary:
            return f"no routing rules for node '{node_id}'"

        parts = [f"node={node_id}"]
        if node_id == "plan" and intent.is_vague:
            parts.append("goal is vague, adding grill-me for clarification")
        elif node_id == "code":
            if intent.goal_type == "explore":
                parts.append("explore intent, using prototype")
            elif complexity == "high":
                parts.append("high complexity, adding tdd")

        parts.append(f"primary={primary}")
        return "; ".join(parts)
