"""Bridge between skill workflow phases and graph nodes.

Maps the workflow phases defined in knowledge/skills/_index.yaml to
the graph execution nodes defined in kernel/graph.yaml, enabling
phase-aware skill selection and transition tracking.
"""

from pathlib import Path

import yaml


class WorkflowBridge:
    """Maps skill workflow phases to graph nodes and vice versa."""

    PHASE_TO_NODES: dict[str, list[str]] = {
        "idea_phase": ["init", "plan"],
        "requirements_phase": ["plan"],
        "execution_phase": ["code", "test"],
        "quality_phase": ["review", "reflect"],
        "design_phase": ["plan", "code"],
        "lifecycle_phase": ["reflect", "evolve"],
    }

    # Reverse mapping: node -> phases
    NODE_TO_PHASES: dict[str, list[str]] = {}
    for _phase, _nodes in PHASE_TO_NODES.items():
        for _node in _nodes:
            NODE_TO_PHASES.setdefault(_node, []).append(_phase)

    def __init__(self, skill_index_path: str) -> None:
        """Load the workflow section from _index.yaml.

        Args:
            skill_index_path: Path to the skills _index.yaml file.
        """
        path = Path(skill_index_path)
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            self._workflow: dict[str, list[str]] = data.get("workflow", {})
            # Support new format with core_workflow and community_workflow
            if not self._workflow:
                core_wf = data.get("core_workflow", {})
                community_wf = data.get("community_workflow", {})
                self._workflow = {**core_wf, **community_wf}
        else:
            self._workflow = {}

    def get_current_phase(self, current_node: str) -> str | None:
        """Given a graph node, return the primary workflow phase.

        The primary phase is the first phase found in NODE_TO_PHASES
        for the given node.

        Args:
            current_node: A graph node id (e.g. 'init', 'code').

        Returns:
            The primary phase name or None if the node is unknown.
        """
        phases = self.NODE_TO_PHASES.get(current_node)
        if phases:
            return phases[0]
        return None

    def get_phases_for_node(self, node_id: str) -> list[str]:
        """Return all phases that map to this node.

        Args:
            node_id: A graph node id.

        Returns:
            List of phase names, or empty list if node is unknown.
        """
        return self.NODE_TO_PHASES.get(node_id, [])

    def get_skills_for_phase(self, phase: str) -> list[str]:
        """Return skill names from the workflow section for a given phase.

        Args:
            phase: A workflow phase name (e.g. 'idea_phase').

        Returns:
            List of skill names for that phase, or empty list if phase is unknown.
        """
        return self._workflow.get(phase, [])

    def get_recommended_phase(self, goal: str, state: dict) -> str:
        """Suggest starting phase based on goal analysis.

        Heuristics:
        - If goal is vague/question-like -> idea_phase
        - If goal mentions UI/design -> design_phase
        - If goal is specific/actionable -> execution_phase
        - Default -> requirements_phase

        Args:
            goal: The development goal text.
            state: Current state dict (for future context use).

        Returns:
            A phase name string.
        """
        if not goal or not goal.strip():
            return "idea_phase"

        goal_lower = goal.lower()
        goal_words = set(goal_lower.split())

        # Question-like or vague goals
        question_markers = ["?", "how", "what", "why", "should", "could", "maybe"]
        if any(marker in goal_lower for marker in question_markers):
            return "idea_phase"

        # Specific/actionable goals (check before design to avoid false positives)
        action_markers = [
            "implement",
            "build",
            "create",
            "add",
            "fix",
            "write",
            "code",
            "develop",
            "make",
            "refactor",
        ]
        if any(marker in goal_words for marker in action_markers):
            return "execution_phase"

        # Design/UI related (use word-level matching to avoid substring false positives)
        design_markers = [
            "ui",
            "ux",
            "design",
            "style",
            "layout",
            "brand",
            "banner",
            "logo",
            "icon",
            "color",
            "font",
            "slide",
        ]
        if any(marker in goal_words for marker in design_markers):
            return "design_phase"

        return "requirements_phase"

    def record_phase_transition(self, state: dict, from_phase: str, to_phase: str) -> dict:
        """Record a phase transition in state['phase_transitions'] list.

        Args:
            state: The current state dict.
            from_phase: Phase being transitioned from.
            to_phase: Phase being transitioned to.

        Returns:
            Updated state dict with the transition recorded.
        """
        if "phase_transitions" not in state:
            state["phase_transitions"] = []
        state["phase_transitions"].append(
            {
                "from": from_phase,
                "to": to_phase,
            }
        )
        return state
