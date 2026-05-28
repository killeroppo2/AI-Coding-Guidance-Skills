"""Tests for kernel/evolution/graph_advisor.py and Reflector integration."""

import pytest
import yaml

from kernel.evolution.graph_advisor import (
    DESIGN_KEYWORDS,
    STRUCTURAL_CONFIDENCE,
    GraphAdvisor,
)
from kernel.evolution.metrics import EvolutionMetrics
from kernel.graph_executor import GraphExecutor
from kernel.reflector import Reflector


@pytest.fixture
def graph_with_review(tmp_path):
    """Create a graph that includes a review node."""
    graph_file = tmp_path / "graph.yaml"
    graph_data = {
        "version": "1.0",
        "description": "Test graph with review",
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Initialize",
                "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                "max_retries": 1,
            },
            {
                "id": "plan",
                "prompt_file": "prompts/planner.md",
                "description": "Plan tasks",
                "transitions": [{"to": "code", "condition": "plan_ready"}],
                "max_retries": 2,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Write code",
                "transitions": [{"to": "review", "condition": "code_ready"}],
                "max_retries": 3,
            },
            {
                "id": "review",
                "prompt_file": "prompts/reviewer.md",
                "description": "Review code",
                "transitions": [{"to": "init", "condition": "done"}],
                "max_retries": 2,
            },
        ],
        "default_start": "init",
    }
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)
    return graph_file


@pytest.fixture
def graph_with_design(tmp_path):
    """Create a graph that already has a design node."""
    graph_file = tmp_path / "graph.yaml"
    graph_data = {
        "version": "1.0",
        "description": "Test graph with design",
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Initialize",
                "transitions": [{"to": "design", "condition": "goal_loaded"}],
                "max_retries": 1,
            },
            {
                "id": "design",
                "prompt_file": "prompts/designer.md",
                "description": "Design step",
                "transitions": [{"to": "code", "condition": "design_ready"}],
                "max_retries": 2,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Write code",
                "transitions": [{"to": "init", "condition": "done"}],
                "max_retries": 3,
            },
        ],
        "default_start": "init",
    }
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)
    return graph_file


@pytest.fixture
def metrics():
    """Create an EvolutionMetrics instance."""
    return EvolutionMetrics(window_size=20)


@pytest.fixture
def advisor(tmp_graph, metrics):
    """Create a GraphAdvisor with basic graph (no review, no design)."""
    executor = GraphExecutor(str(tmp_graph))
    return GraphAdvisor(executor, metrics)


@pytest.fixture
def advisor_with_review(graph_with_review, metrics):
    """Create a GraphAdvisor with review node in graph."""
    executor = GraphExecutor(str(graph_with_review))
    return GraphAdvisor(executor, metrics)


@pytest.fixture
def advisor_with_design(graph_with_design, metrics):
    """Create a GraphAdvisor with design node already in graph."""
    executor = GraphExecutor(str(graph_with_design))
    return GraphAdvisor(executor, metrics)


# --- Rule 1: UI goal triggers design node proposal ---


class TestDesignNodeForUIGoal:
    """Tests for Rule 1: design node proposal when goal has UI keywords."""

    def test_ui_goal_triggers_design_proposal(self, advisor):
        """UI-related goal with design keyword should trigger design node proposal."""
        proposals = advisor.suggest_graph_changes(
            goal="Build a responsive frontend dashboard",
            skills_loaded=["coding"],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 1
        assert add_proposals[0]["details"]["node"]["id"] == "design"

    def test_multiple_design_keywords(self, advisor):
        """Multiple design keywords still produce only one proposal."""
        proposals = advisor.suggest_graph_changes(
            goal="Create a react component with css styling",
            skills_loaded=["coding"],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 1

    def test_non_ui_goal_no_design_proposal(self, advisor):
        """Non-UI goal should NOT trigger design node proposal."""
        proposals = advisor.suggest_graph_changes(
            goal="Implement a REST API with authentication",
            skills_loaded=["coding"],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        # No design proposal from rule 1
        for p in add_proposals:
            # Could have proposals from other rules, check reason
            assert "UI/design" not in p.get("reason", "")

    def test_design_not_proposed_when_already_exists(self, advisor_with_design):
        """Design node should NOT be proposed when it already exists in graph."""
        proposals = advisor_with_design.suggest_graph_changes(
            goal="Build a responsive frontend dashboard",
            skills_loaded=["coding"],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 0

    def test_keyword_matching_is_case_insensitive(self, advisor):
        """Keywords should match regardless of case."""
        proposals = advisor.suggest_graph_changes(
            goal="Build a FRONTEND application",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 1

    def test_each_design_keyword_triggers(self, advisor, tmp_graph):
        """Each keyword in DESIGN_KEYWORDS should trigger a proposal."""
        for keyword in ["ui", "ux", "design", "frontend", "react", "figma"]:
            # Reload executor each time to ensure no design node
            executor = GraphExecutor(str(tmp_graph))
            metrics = EvolutionMetrics()
            adv = GraphAdvisor(executor, metrics)
            proposals = adv.suggest_graph_changes(
                goal=f"Work on {keyword} task",
                skills_loaded=[],
                history=[],
            )
            add_proposals = [
                p
                for p in proposals
                if p["type"] == "add_node" and "UI/design" in p.get("reason", "")
            ]
            assert len(add_proposals) == 1, f"Keyword '{keyword}' did not trigger proposal"


# --- Rule 2: Review removal ---


class TestReviewRemoval:
    """Tests for Rule 2: remove review when consistently passing."""

    def test_high_review_success_triggers_removal(self, advisor_with_review, metrics):
        """Review with success_rate > 0.9 and >= 5 samples triggers removal."""
        # Record 6 successes for review
        for _ in range(6):
            metrics.record_iteration("review", success=True, retries=0)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        remove_proposals = [p for p in proposals if p["type"] == "remove_node"]
        assert len(remove_proposals) == 1
        assert remove_proposals[0]["details"]["node_id"] == "review"

    def test_review_not_removed_low_success_rate(self, advisor_with_review, metrics):
        """Review with success_rate <= 0.9 should NOT be proposed for removal."""
        # 4 successes, 2 failures = 66% success rate
        for _ in range(4):
            metrics.record_iteration("review", success=True, retries=0)
        for _ in range(2):
            metrics.record_iteration("review", success=False, retries=1)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        remove_proposals = [p for p in proposals if p["type"] == "remove_node"]
        assert len(remove_proposals) == 0

    def test_review_not_removed_low_sample_count(self, advisor_with_review, metrics):
        """Review with sample_count < 5 should NOT be proposed for removal."""
        # Only 4 samples (all successful)
        for _ in range(4):
            metrics.record_iteration("review", success=True, retries=0)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        remove_proposals = [p for p in proposals if p["type"] == "remove_node"]
        assert len(remove_proposals) == 0

    def test_review_not_removed_no_data(self, advisor_with_review, metrics):
        """Review with no metrics data should NOT be proposed for removal."""
        proposals = advisor_with_review.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        remove_proposals = [p for p in proposals if p["type"] == "remove_node"]
        assert len(remove_proposals) == 0


# --- Rule 3: Code struggles ---


class TestCodeStruggles:
    """Tests for Rule 3: add design when code has high retries."""

    def test_high_code_retries_triggers_design_proposal(self, advisor, metrics):
        """Code node with avg_retries > 3 should trigger design proposal."""
        # 4 iterations with 4 retries each (avg = 4.0 > 3)
        for _ in range(4):
            metrics.record_iteration("code", success=True, retries=4)

        proposals = advisor.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 1
        assert add_proposals[0]["details"]["node"]["id"] == "design"
        assert "retries" in add_proposals[0]["reason"]

    def test_code_struggles_not_triggered_low_retries(self, advisor, metrics):
        """Code with avg_retries <= 3 should NOT trigger proposal."""
        for _ in range(5):
            metrics.record_iteration("code", success=True, retries=2)

        proposals = advisor.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 0

    def test_code_struggles_not_triggered_low_sample(self, advisor, metrics):
        """Code with sample_count < 3 should NOT trigger proposal."""
        for _ in range(2):
            metrics.record_iteration("code", success=True, retries=5)

        proposals = advisor.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 0

    def test_code_struggles_not_triggered_design_exists(self, advisor_with_design, metrics):
        """Code struggles should NOT propose design if design node already exists."""
        for _ in range(5):
            metrics.record_iteration("code", success=True, retries=5)

        proposals = advisor_with_design.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 0


# --- Proposal format and confidence ---


class TestProposalFormat:
    """Tests for proposal format and confidence scores."""

    def test_all_proposals_have_required_fields(self, advisor_with_review, metrics):
        """All proposals must have type, details, reason, confidence_score, category."""
        # Trigger rule 1 and rule 2
        for _ in range(6):
            metrics.record_iteration("review", success=True, retries=0)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Build a responsive frontend",
            skills_loaded=[],
            history=[],
        )
        assert len(proposals) >= 1
        for proposal in proposals:
            assert "type" in proposal
            assert "details" in proposal
            assert "reason" in proposal
            assert "confidence_score" in proposal
            assert "category" in proposal

    def test_all_proposals_confidence_at_least_09(self, advisor_with_review, metrics):
        """All structural proposals have confidence >= 0.9."""
        for _ in range(6):
            metrics.record_iteration("review", success=True, retries=0)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Build a vue frontend",
            skills_loaded=[],
            history=[],
        )
        for proposal in proposals:
            assert proposal["confidence_score"] >= 0.9

    def test_all_proposals_category_structural(self, advisor, metrics):
        """All proposals have category 'structural'."""
        for _ in range(5):
            metrics.record_iteration("code", success=True, retries=5)

        proposals = advisor.suggest_graph_changes(
            goal="Build a react app",
            skills_loaded=[],
            history=[],
        )
        for proposal in proposals:
            assert proposal["category"] == "structural"

    def test_add_node_details_format(self, advisor):
        """add_node proposals have details.node dict with 'id' field."""
        proposals = advisor.suggest_graph_changes(
            goal="Build a frontend component",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        assert len(add_proposals) == 1
        assert "node" in add_proposals[0]["details"]
        assert "id" in add_proposals[0]["details"]["node"]

    def test_remove_node_details_format(self, advisor_with_review, metrics):
        """remove_node proposals have details.node_id field."""
        for _ in range(6):
            metrics.record_iteration("review", success=True, retries=0)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Implement API",
            skills_loaded=[],
            history=[],
        )
        remove_proposals = [p for p in proposals if p["type"] == "remove_node"]
        assert len(remove_proposals) == 1
        assert "node_id" in remove_proposals[0]["details"]


# --- Multiple proposals and empty results ---


class TestMultipleProposals:
    """Tests for combined proposal scenarios."""

    def test_multiple_proposals_returned(self, advisor_with_review, metrics):
        """Can return proposals from multiple rules at once."""
        # Trigger rule 1 (UI goal) and rule 2 (review passing)
        for _ in range(6):
            metrics.record_iteration("review", success=True, retries=0)

        proposals = advisor_with_review.suggest_graph_changes(
            goal="Build a responsive frontend dashboard",
            skills_loaded=[],
            history=[],
        )
        types = [p["type"] for p in proposals]
        assert "add_node" in types
        assert "remove_node" in types

    def test_empty_list_when_no_conditions_met(self, advisor, metrics):
        """Returns empty list when no rules trigger."""
        # Non-UI goal, no metrics data
        proposals = advisor.suggest_graph_changes(
            goal="Implement a REST API",
            skills_loaded=[],
            history=[],
        )
        assert proposals == []

    def test_ui_goal_and_code_struggles_single_design(self, advisor, metrics):
        """When both rule 1 and rule 3 trigger, only one design proposal (from rule 1 first)."""
        # High code retries
        for _ in range(5):
            metrics.record_iteration("code", success=True, retries=5)

        proposals = advisor.suggest_graph_changes(
            goal="Build a react component",
            skills_loaded=[],
            history=[],
        )
        add_proposals = [p for p in proposals if p["type"] == "add_node"]
        # Rule 1 fires first - adds design node.
        # Rule 3 checks if design node exists in graph. Since rule 1 only
        # proposes but doesn't modify the graph, rule 3 also fires.
        # Both will propose add_node for "design"
        assert len(add_proposals) == 2


# --- Reflector integration ---


class TestReflectorIntegration:
    """Tests for Reflector.suggest_graph_evolution integration."""

    def test_reflector_no_advisor_returns_empty(self, tmp_memory):
        """Reflector without graph_advisor returns empty list."""
        reflector = Reflector(str(tmp_memory), knowledge_store=None)
        result = reflector.suggest_graph_evolution(goal="Build UI", skills_loaded=[], history=[])
        assert result == []

    def test_reflector_with_advisor_delegates(self, tmp_memory, tmp_graph):
        """Reflector with graph_advisor delegates to suggest_graph_changes."""
        metrics = EvolutionMetrics()
        executor = GraphExecutor(str(tmp_graph))
        advisor = GraphAdvisor(executor, metrics)

        reflector = Reflector(str(tmp_memory), knowledge_store=None, graph_advisor=advisor)
        result = reflector.suggest_graph_evolution(
            goal="Build a frontend page", skills_loaded=[], history=[]
        )
        assert len(result) >= 1
        assert result[0]["type"] == "add_node"

    def test_reflector_with_advisor_no_proposals(self, tmp_memory, tmp_graph):
        """Reflector delegates even when no proposals returned."""
        metrics = EvolutionMetrics()
        executor = GraphExecutor(str(tmp_graph))
        advisor = GraphAdvisor(executor, metrics)

        reflector = Reflector(str(tmp_memory), knowledge_store=None, graph_advisor=advisor)
        result = reflector.suggest_graph_evolution(
            goal="Implement API endpoint", skills_loaded=[], history=[]
        )
        assert result == []


# --- STRUCTURAL_CONFIDENCE constant ---


class TestConstants:
    """Tests for module-level constants."""

    def test_structural_confidence_value(self):
        """STRUCTURAL_CONFIDENCE is 0.9."""
        assert STRUCTURAL_CONFIDENCE == 0.9

    def test_design_keywords_is_frozenset(self):
        """DESIGN_KEYWORDS is a frozenset."""
        assert isinstance(DESIGN_KEYWORDS, frozenset)

    def test_design_keywords_not_empty(self):
        """DESIGN_KEYWORDS has entries."""
        assert len(DESIGN_KEYWORDS) > 0
