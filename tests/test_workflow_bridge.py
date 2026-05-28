"""Tests for kernel/workflow_bridge.py and select_skills_for_phase."""

from pathlib import Path

import pytest
import yaml

from kernel.skill_selector import select_skills_for_phase
from kernel.workflow_bridge import WorkflowBridge


@pytest.fixture
def skill_index_path(tmp_path: Path) -> str:
    """Create a temporary _index.yaml with workflow section."""
    index_file = tmp_path / "_index.yaml"
    data = {
        "version": "1.0",
        "workflow": {
            "idea_phase": ["grill-me", "grill-with-docs"],
            "requirements_phase": ["prd", "to-prd", "to-issues"],
            "execution_phase": ["ralph", "tdd", "prototype"],
            "quality_phase": ["diagnose", "improve-codebase-architecture"],
            "design_phase": [
                "ui-ux-pro-max",
                "ui-styling",
                "design-system",
                "design",
                "brand",
                "banner-design",
                "slides",
            ],
            "lifecycle_phase": ["handoff", "triage", "zoom-out"],
        },
        "items": [],
    }
    with open(index_file, "w") as f:
        yaml.safe_dump(data, f)
    return str(index_file)


@pytest.fixture
def bridge(skill_index_path: str) -> WorkflowBridge:
    """Create a WorkflowBridge instance with the test index."""
    return WorkflowBridge(skill_index_path)


class TestPhaseToNodesMapping:
    """Tests for PHASE_TO_NODES correctness."""

    def test_all_graph_nodes_mapped(self):
        """Every graph node should appear in at least one phase."""
        all_nodes = {"init", "plan", "code", "test", "review", "reflect", "evolve"}
        mapped_nodes = set()
        for nodes in WorkflowBridge.PHASE_TO_NODES.values():
            mapped_nodes.update(nodes)
        assert all_nodes == mapped_nodes

    def test_idea_phase_nodes(self):
        assert WorkflowBridge.PHASE_TO_NODES["idea_phase"] == ["init", "plan"]

    def test_requirements_phase_nodes(self):
        assert WorkflowBridge.PHASE_TO_NODES["requirements_phase"] == ["plan"]

    def test_execution_phase_nodes(self):
        assert WorkflowBridge.PHASE_TO_NODES["execution_phase"] == ["code", "test"]

    def test_quality_phase_nodes(self):
        assert WorkflowBridge.PHASE_TO_NODES["quality_phase"] == ["review", "reflect"]

    def test_design_phase_nodes(self):
        assert WorkflowBridge.PHASE_TO_NODES["design_phase"] == ["plan", "code"]

    def test_lifecycle_phase_nodes(self):
        assert WorkflowBridge.PHASE_TO_NODES["lifecycle_phase"] == ["reflect", "evolve"]


class TestNodeToPhases:
    """Tests for NODE_TO_PHASES reverse mapping."""

    def test_init_maps_to_idea_phase(self):
        assert "idea_phase" in WorkflowBridge.NODE_TO_PHASES["init"]

    def test_plan_maps_to_multiple_phases(self):
        phases = WorkflowBridge.NODE_TO_PHASES["plan"]
        assert "idea_phase" in phases
        assert "requirements_phase" in phases
        assert "design_phase" in phases

    def test_code_maps_to_execution_and_design(self):
        phases = WorkflowBridge.NODE_TO_PHASES["code"]
        assert "execution_phase" in phases
        assert "design_phase" in phases

    def test_reflect_maps_to_quality_and_lifecycle(self):
        phases = WorkflowBridge.NODE_TO_PHASES["reflect"]
        assert "quality_phase" in phases
        assert "lifecycle_phase" in phases

    def test_evolve_maps_to_lifecycle(self):
        assert "lifecycle_phase" in WorkflowBridge.NODE_TO_PHASES["evolve"]


class TestGetCurrentPhase:
    """Tests for get_current_phase method."""

    def test_init_returns_idea_phase(self, bridge):
        assert bridge.get_current_phase("init") == "idea_phase"

    def test_plan_returns_idea_phase(self, bridge):
        # First phase in the list for 'plan' node
        assert bridge.get_current_phase("plan") == "idea_phase"

    def test_code_returns_execution_phase(self, bridge):
        assert bridge.get_current_phase("code") == "execution_phase"

    def test_test_returns_execution_phase(self, bridge):
        assert bridge.get_current_phase("test") == "execution_phase"

    def test_review_returns_quality_phase(self, bridge):
        assert bridge.get_current_phase("review") == "quality_phase"

    def test_reflect_returns_quality_phase(self, bridge):
        assert bridge.get_current_phase("reflect") == "quality_phase"

    def test_evolve_returns_lifecycle_phase(self, bridge):
        assert bridge.get_current_phase("evolve") == "lifecycle_phase"

    def test_unknown_node_returns_none(self, bridge):
        assert bridge.get_current_phase("nonexistent") is None

    def test_empty_node_returns_none(self, bridge):
        assert bridge.get_current_phase("") is None


class TestGetPhasesForNode:
    """Tests for get_phases_for_node method."""

    def test_plan_has_three_phases(self, bridge):
        phases = bridge.get_phases_for_node("plan")
        assert len(phases) == 3
        assert "idea_phase" in phases
        assert "requirements_phase" in phases
        assert "design_phase" in phases

    def test_unknown_node_returns_empty(self, bridge):
        assert bridge.get_phases_for_node("unknown") == []


class TestGetSkillsForPhase:
    """Tests for get_skills_for_phase method."""

    def test_idea_phase_skills(self, bridge):
        skills = bridge.get_skills_for_phase("idea_phase")
        assert skills == ["grill-me", "grill-with-docs"]

    def test_requirements_phase_skills(self, bridge):
        skills = bridge.get_skills_for_phase("requirements_phase")
        assert skills == ["prd", "to-prd", "to-issues"]

    def test_execution_phase_skills(self, bridge):
        skills = bridge.get_skills_for_phase("execution_phase")
        assert skills == ["ralph", "tdd", "prototype"]

    def test_quality_phase_skills(self, bridge):
        skills = bridge.get_skills_for_phase("quality_phase")
        assert skills == ["diagnose", "improve-codebase-architecture"]

    def test_design_phase_skills(self, bridge):
        skills = bridge.get_skills_for_phase("design_phase")
        assert len(skills) == 7
        assert "ui-ux-pro-max" in skills

    def test_lifecycle_phase_skills(self, bridge):
        skills = bridge.get_skills_for_phase("lifecycle_phase")
        assert skills == ["handoff", "triage", "zoom-out"]

    def test_unknown_phase_returns_empty(self, bridge):
        assert bridge.get_skills_for_phase("nonexistent_phase") == []


class TestGetRecommendedPhase:
    """Tests for get_recommended_phase method."""

    def test_vague_goal_with_question(self, bridge):
        assert bridge.get_recommended_phase("what should I build?", {}) == "idea_phase"

    def test_how_question(self, bridge):
        assert bridge.get_recommended_phase("how to structure this", {}) == "idea_phase"

    def test_maybe_vague(self, bridge):
        assert bridge.get_recommended_phase("maybe a dashboard", {}) == "idea_phase"

    def test_ui_goal(self, bridge):
        assert bridge.get_recommended_phase("design a new UI", {}) == "design_phase"

    def test_brand_goal(self, bridge):
        assert bridge.get_recommended_phase("brand guidelines needed", {}) == "design_phase"

    def test_style_goal(self, bridge):
        assert bridge.get_recommended_phase("style the buttons", {}) == "design_phase"

    def test_actionable_implement(self, bridge):
        assert bridge.get_recommended_phase("implement user auth", {}) == "execution_phase"

    def test_actionable_build(self, bridge):
        assert bridge.get_recommended_phase("build the API endpoint", {}) == "execution_phase"

    def test_actionable_fix(self, bridge):
        assert bridge.get_recommended_phase("fix the login bug", {}) == "execution_phase"

    def test_default_requirements(self, bridge):
        assert (
            bridge.get_recommended_phase("user authentication system", {}) == "requirements_phase"
        )

    def test_empty_goal(self, bridge):
        assert bridge.get_recommended_phase("", {}) == "idea_phase"

    def test_whitespace_goal(self, bridge):
        assert bridge.get_recommended_phase("   ", {}) == "idea_phase"


class TestRecordPhaseTransition:
    """Tests for record_phase_transition method."""

    def test_records_transition(self, bridge):
        state = {}
        result = bridge.record_phase_transition(state, "idea_phase", "requirements_phase")
        assert result is state
        assert len(state["phase_transitions"]) == 1
        assert state["phase_transitions"][0] == {
            "from": "idea_phase",
            "to": "requirements_phase",
        }

    def test_appends_multiple_transitions(self, bridge):
        state = {}
        bridge.record_phase_transition(state, "idea_phase", "requirements_phase")
        bridge.record_phase_transition(state, "requirements_phase", "execution_phase")
        assert len(state["phase_transitions"]) == 2

    def test_preserves_existing_transitions(self, bridge):
        state = {"phase_transitions": [{"from": "a", "to": "b"}]}
        bridge.record_phase_transition(state, "b", "c")
        assert len(state["phase_transitions"]) == 2


class TestSelectSkillsForPhase:
    """Tests for the select_skills_for_phase function in skill_selector."""

    def test_returns_skills_for_known_phase(self):
        workflow = {
            "idea_phase": ["grill-me", "grill-with-docs"],
            "execution_phase": ["ralph", "tdd"],
        }
        assert select_skills_for_phase("idea_phase", workflow) == ["grill-me", "grill-with-docs"]

    def test_returns_empty_for_unknown_phase(self):
        workflow = {"idea_phase": ["grill-me"]}
        assert select_skills_for_phase("nonexistent", workflow) == []

    def test_empty_phase_returns_empty(self):
        workflow = {"idea_phase": ["grill-me"]}
        assert select_skills_for_phase("", workflow) == []

    def test_none_phase_returns_empty(self):
        assert select_skills_for_phase(None, {"a": ["b"]}) == []

    def test_empty_workflow_returns_empty(self):
        assert select_skills_for_phase("idea_phase", {}) == []

    def test_none_workflow_returns_empty(self):
        assert select_skills_for_phase("idea_phase", None) == []


class TestWorkflowBridgeInit:
    """Tests for WorkflowBridge initialization edge cases."""

    def test_nonexistent_path(self, tmp_path):
        """Loading from a non-existent path results in empty workflow."""
        bridge = WorkflowBridge(str(tmp_path / "does_not_exist.yaml"))
        assert bridge.get_skills_for_phase("idea_phase") == []

    def test_empty_yaml(self, tmp_path):
        """Loading from an empty YAML file results in empty workflow."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        bridge = WorkflowBridge(str(empty_file))
        assert bridge.get_skills_for_phase("idea_phase") == []

    def test_yaml_without_workflow_key(self, tmp_path):
        """Loading YAML without workflow key results in empty workflow."""
        no_workflow = tmp_path / "no_workflow.yaml"
        with open(no_workflow, "w") as f:
            yaml.safe_dump({"items": []}, f)
        bridge = WorkflowBridge(str(no_workflow))
        assert bridge.get_skills_for_phase("idea_phase") == []
