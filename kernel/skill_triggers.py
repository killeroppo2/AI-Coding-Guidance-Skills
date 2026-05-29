"""Auto-trigger conditions engine - 道常无为而无不为 (act without forcing)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SkillTrigger:
    """A triggered skill recommendation based on runtime conditions."""

    trigger_name: str
    skill: str
    target_node: str
    reason: str


class SkillTriggerEngine:
    """Evaluate runtime conditions and recommend skill adjustments."""

    def evaluate(
        self, state: dict, node_id: str, iteration_result: str
    ) -> list[SkillTrigger]:
        """Evaluate all trigger conditions and return matching triggers.

        Args:
            state: Runtime state dict with node_visits, context, progress_history.
            node_id: Current graph node identifier.
            iteration_result: Result of the current iteration ('success' or 'failed').

        Returns:
            List of SkillTrigger recommendations that fired.
        """
        triggers: list[SkillTrigger] = []

        triggers.extend(self._check_auto_diagnose(state, node_id, iteration_result))
        triggers.extend(self._check_auto_grill(state, node_id))
        triggers.extend(self._check_auto_simplify(state, node_id, iteration_result))
        triggers.extend(self._check_auto_write_skill(node_id, iteration_result))
        triggers.extend(self._check_auto_zoom_out(state, node_id, iteration_result))

        return triggers

    def _check_auto_diagnose(
        self, state: dict, node_id: str, iteration_result: str
    ) -> list[SkillTrigger]:
        """Trigger diagnose skill after 2+ consecutive test failures."""
        if node_id != "test" or iteration_result != "failed":
            return []

        node_visits = state.get("node_visits", {})
        if node_visits.get("test", 0) >= 2:
            return [
                SkillTrigger(
                    trigger_name="auto_diagnose",
                    skill="diagnose",
                    target_node="code",
                    reason="2+ consecutive test failures, switching to diagnose",
                )
            ]
        return []

    def _check_auto_grill(self, state: dict, node_id: str) -> list[SkillTrigger]:
        """Trigger grill-me on vague intent at plan node."""
        if node_id != "plan":
            return []

        context = state.get("context", {})
        intent_result = context.get("intent_result", {})
        skills_loaded = context.get("skills_loaded", [])

        if intent_result.get("is_vague") and "grill-me" not in skills_loaded:
            return [
                SkillTrigger(
                    trigger_name="auto_grill",
                    skill="grill-me",
                    target_node="plan",
                    reason="vague intent detected, adding grill-me for clarification",
                )
            ]
        return []

    def _check_auto_simplify(
        self, state: dict, node_id: str, iteration_result: str
    ) -> list[SkillTrigger]:
        """Trigger prototype skill after 3+ consecutive code failures."""
        if node_id != "code" or iteration_result != "failed":
            return []

        node_visits = state.get("node_visits", {})
        if node_visits.get("code", 0) >= 3:
            return [
                SkillTrigger(
                    trigger_name="auto_simplify",
                    skill="prototype",
                    target_node="code",
                    reason="3+ consecutive code failures, simplifying with prototype",
                )
            ]
        return []

    def _check_auto_write_skill(
        self, node_id: str, iteration_result: str
    ) -> list[SkillTrigger]:
        """Trigger write-a-skill on successful evolve."""
        if node_id == "evolve" and iteration_result == "success":
            return [
                SkillTrigger(
                    trigger_name="auto_write_skill",
                    skill="write-a-skill",
                    target_node="evolve",
                    reason="successful evolution, capturing as reusable skill",
                )
            ]
        return []

    def _check_auto_zoom_out(
        self, state: dict, node_id: str, iteration_result: str
    ) -> list[SkillTrigger]:
        """Trigger zoom-out when stall detected at reflect node."""
        if node_id != "reflect" or iteration_result != "success":
            return []

        progress_history = state.get("progress_history", [])
        if len(progress_history) >= 5:
            last_five = progress_history[-5:]
            if all(v == last_five[0] for v in last_five):
                return [
                    SkillTrigger(
                        trigger_name="auto_zoom_out",
                        skill="zoom-out",
                        target_node="reflect",
                        reason="stall detected (same progress 5+ times), zooming out",
                    )
                ]
        return []
