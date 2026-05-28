"""Graph structure advisor for intelligent workflow restructuring.

Proposes structural changes to the graph (add/remove/reorder nodes)
based on analysis of goal, loaded skills, history, and metrics.
"""

from typing import Any

# Keywords that suggest UI/design work
DESIGN_KEYWORDS = frozenset({
    "ui", "ux", "design", "frontend", "interface", "layout",
    "css", "styling", "component", "visual", "responsive", "tailwind",
    "react", "vue", "angular", "svelte", "page", "screen", "mockup",
    "wireframe", "figma", "prototype"
})

# Structural change confidence threshold (higher than prompt changes)
STRUCTURAL_CONFIDENCE = 0.9


class GraphAdvisor:
    """Proposes structural graph changes based on runtime analysis.

    Uses goal analysis, skill coverage, evolution history, and node metrics
    to suggest when the workflow graph should be restructured.
    """

    def __init__(self, graph_executor: Any, evolution_metrics: Any):
        """
        Args:
            graph_executor: GraphExecutor instance for reading graph state.
            evolution_metrics: EvolutionMetrics instance for node performance data.
        """
        self.graph_executor = graph_executor
        self.metrics = evolution_metrics

    def suggest_graph_changes(
        self,
        goal: str,
        skills_loaded: list[str],
        history: list[dict],
        metrics_summary: dict | None = None,
    ) -> list[dict]:
        """Analyze and propose structural graph changes.

        Rules:
        1. If goal contains design/UI keywords AND no 'design' node exists -> propose add_node
        2. If review node consistently passes first time
           (success_rate > 0.9, sample_count >= 5) -> propose remove_node
        3. If code node has high avg_retries (> 3) -> propose adding 'design' node before code

        Each proposal is a dict with:
        - type: "add_node" | "remove_node" | "reorder"
        - details: matching what EvolutionEngine.apply_change expects
        - reason: human-readable explanation
        - confidence_score: always >= 0.9 for structural changes
        - category: "structural"

        Args:
            goal: The development goal string.
            skills_loaded: Currently loaded skill names.
            history: Evolution history entries.
            metrics_summary: Optional pre-computed metrics dict.

        Returns:
            List of proposal dicts. May be empty if no changes needed.
        """
        proposals = []

        # Rule 1: Design node for UI goals
        proposal = self._check_design_node_needed(goal, skills_loaded)
        if proposal:
            proposals.append(proposal)

        # Rule 2: Remove review if consistently passing
        proposal = self._check_review_removal()
        if proposal:
            proposals.append(proposal)

        # Rule 3: Add design step if code keeps retrying
        proposal = self._check_code_struggles()
        if proposal:
            proposals.append(proposal)

        return proposals

    def _check_design_node_needed(self, goal: str, skills_loaded: list[str]) -> dict | None:
        """Check if a design node should be added based on goal keywords.

        Only proposes if 'design' node does NOT already exist in the graph.
        """
        goal_words = set(goal.lower().split())
        has_design_keyword = bool(goal_words & DESIGN_KEYWORDS)

        if not has_design_keyword:
            return None

        # Check if design node already exists
        node_ids = {n["id"] for n in self.graph_executor.graph.get("nodes", [])}
        if "design" in node_ids:
            return None

        return {
            "type": "add_node",
            "details": {
                "node": {
                    "id": "design",
                    "prompt_file": "prompts/designer.md",
                    "description": "Design UI/UX components before coding",
                    "transitions": [{"to": "code", "condition": "design_ready"}],
                    "max_retries": 3,
                }
            },
            "reason": "Goal involves UI/design work but graph has no design node",
            "confidence_score": STRUCTURAL_CONFIDENCE,
            "category": "structural",
        }

    def _check_review_removal(self) -> dict | None:
        """Check if review node can be removed due to consistent success.

        If review has success_rate > 0.9 and sample_count >= 5, it's
        not providing value - propose removal to speed up iteration.
        """
        review_metrics = self.metrics.get_node_metrics("review")

        if review_metrics["sample_count"] < 5:
            return None

        if review_metrics["success_rate"] <= 0.9:
            return None

        return {
            "type": "remove_node",
            "details": {
                "node_id": "review",
            },
            "reason": (
                f"Review node passes {review_metrics['success_rate']:.0%} of the time "
                f"(over {review_metrics['sample_count']} samples) - removing to speed up iteration"
            ),
            "confidence_score": STRUCTURAL_CONFIDENCE,
            "category": "structural",
        }

    def _check_code_struggles(self) -> dict | None:
        """Check if code node struggles suggest a missing design step.

        If code node's avg_retries > 3, a design step between plan and code
        might help by clarifying implementation before coding starts.
        Only proposes if 'design' node doesn't exist yet.
        """
        code_metrics = self.metrics.get_node_metrics("code")

        if code_metrics["sample_count"] < 3:
            return None

        if code_metrics["avg_retries"] <= 3.0:
            return None

        # Don't propose if design already exists
        node_ids = {n["id"] for n in self.graph_executor.graph.get("nodes", [])}
        if "design" in node_ids:
            return None

        return {
            "type": "add_node",
            "details": {
                "node": {
                    "id": "design",
                    "prompt_file": "prompts/designer.md",
                    "description": "Design step to reduce code iteration loops",
                    "transitions": [{"to": "code", "condition": "design_ready"}],
                    "max_retries": 3,
                }
            },
            "reason": (
                f"Code node averages {code_metrics['avg_retries']:.1f} retries - "
                f"adding design step to clarify implementation before coding"
            ),
            "confidence_score": STRUCTURAL_CONFIDENCE,
            "category": "structural",
        }
