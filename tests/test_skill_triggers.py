"""Tests for kernel/skill_triggers.py - SkillTriggerEngine and SkillTrigger."""

import pytest

from kernel.skill_triggers import SkillTrigger, SkillTriggerEngine


@pytest.fixture
def engine() -> SkillTriggerEngine:
    """Return a SkillTriggerEngine instance."""
    return SkillTriggerEngine()


@pytest.fixture
def base_state() -> dict:
    """Return a minimal valid state dict."""
    return {
        "node_visits": {},
        "context": {
            "skills_loaded": [],
            "intent_result": {},
        },
        "progress_history": [],
    }


class TestAutoDiagnose:
    """Tests for the auto_diagnose trigger."""

    def test_auto_diagnose_fires_on_2_test_failures(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger fires when test node has 2+ visits and result is failed."""
        base_state["node_visits"]["test"] = 2
        triggers = engine.evaluate(base_state, "test", "failed")

        assert len(triggers) == 1
        assert triggers[0].trigger_name == "auto_diagnose"
        assert triggers[0].skill == "diagnose"
        assert triggers[0].target_node == "code"

    def test_auto_diagnose_does_not_fire_on_first_failure(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger does not fire on the first test failure."""
        base_state["node_visits"]["test"] = 1
        triggers = engine.evaluate(base_state, "test", "failed")

        diagnose_triggers = [t for t in triggers if t.trigger_name == "auto_diagnose"]
        assert len(diagnose_triggers) == 0


class TestAutoGrill:
    """Tests for the auto_grill trigger."""

    def test_auto_grill_fires_on_vague_intent_at_plan(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger fires when intent is vague and at plan node."""
        base_state["context"]["intent_result"] = {"is_vague": True}
        triggers = engine.evaluate(base_state, "plan", "success")

        assert len(triggers) == 1
        assert triggers[0].trigger_name == "auto_grill"
        assert triggers[0].skill == "grill-me"
        assert triggers[0].target_node == "plan"

    def test_auto_grill_does_not_fire_if_grill_already_loaded(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger does not fire if grill-me is already loaded."""
        base_state["context"]["intent_result"] = {"is_vague": True}
        base_state["context"]["skills_loaded"] = ["grill-me", "prd"]
        triggers = engine.evaluate(base_state, "plan", "success")

        grill_triggers = [t for t in triggers if t.trigger_name == "auto_grill"]
        assert len(grill_triggers) == 0


class TestAutoSimplify:
    """Tests for the auto_simplify trigger."""

    def test_auto_simplify_fires_on_3_code_failures(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger fires when code node has 3+ visits and result is failed."""
        base_state["node_visits"]["code"] = 3
        triggers = engine.evaluate(base_state, "code", "failed")

        assert len(triggers) == 1
        assert triggers[0].trigger_name == "auto_simplify"
        assert triggers[0].skill == "prototype"
        assert triggers[0].target_node == "code"

    def test_auto_simplify_does_not_fire_on_2_code_failures(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger does not fire with only 2 code visits."""
        base_state["node_visits"]["code"] = 2
        triggers = engine.evaluate(base_state, "code", "failed")

        simplify_triggers = [t for t in triggers if t.trigger_name == "auto_simplify"]
        assert len(simplify_triggers) == 0


class TestAutoWriteSkill:
    """Tests for the auto_write_skill trigger."""

    def test_auto_write_skill_fires_on_successful_evolve(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger fires when evolve node succeeds."""
        triggers = engine.evaluate(base_state, "evolve", "success")

        assert len(triggers) == 1
        assert triggers[0].trigger_name == "auto_write_skill"
        assert triggers[0].skill == "write-a-skill"
        assert triggers[0].target_node == "evolve"


class TestAutoZoomOut:
    """Tests for the auto_zoom_out trigger."""

    def test_auto_zoom_out_fires_on_stall(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger fires when last 5 progress values are the same."""
        base_state["progress_history"] = [3, 3, 3, 3, 3]
        triggers = engine.evaluate(base_state, "reflect", "success")

        assert len(triggers) == 1
        assert triggers[0].trigger_name == "auto_zoom_out"
        assert triggers[0].skill == "zoom-out"
        assert triggers[0].target_node == "reflect"

    def test_auto_zoom_out_does_not_fire_without_stall(
        self, engine: SkillTriggerEngine, base_state: dict
    ) -> None:
        """Trigger does not fire when progress values differ."""
        base_state["progress_history"] = [1, 2, 3, 4, 5]
        triggers = engine.evaluate(base_state, "reflect", "success")

        zoom_triggers = [t for t in triggers if t.trigger_name == "auto_zoom_out"]
        assert len(zoom_triggers) == 0


class TestEdgeCases:
    """Tests for edge cases and combined conditions."""

    def test_no_triggers_on_empty_state(self, engine: SkillTriggerEngine) -> None:
        """No triggers fire on completely empty state."""
        state: dict = {
            "node_visits": {},
            "context": {"skills_loaded": [], "intent_result": {}},
            "progress_history": [],
        }
        triggers = engine.evaluate(state, "init", "success")
        assert triggers == []

    def test_multiple_triggers_can_fire_simultaneously(
        self, engine: SkillTriggerEngine
    ) -> None:
        """Multiple triggers can fire if conditions overlap on reflect node."""
        state: dict = {
            "node_visits": {"reflect": 6},
            "context": {
                "skills_loaded": [],
                "intent_result": {"is_vague": True},
            },
            "progress_history": [2, 2, 2, 2, 2],
        }
        # At reflect node with success and stall - auto_zoom_out fires
        triggers = engine.evaluate(state, "reflect", "success")
        assert any(t.trigger_name == "auto_zoom_out" for t in triggers)

    def test_trigger_dataclass_fields(self) -> None:
        """SkillTrigger dataclass has correct fields."""
        trigger = SkillTrigger(
            trigger_name="test",
            skill="test-skill",
            target_node="code",
            reason="testing",
        )
        assert trigger.trigger_name == "test"
        assert trigger.skill == "test-skill"
        assert trigger.target_node == "code"
        assert trigger.reason == "testing"
