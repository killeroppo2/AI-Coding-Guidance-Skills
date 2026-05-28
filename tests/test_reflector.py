"""Tests for the Reflector class."""

from pathlib import Path

import pytest

from kernel.reflector import Reflector
from knowledge.store import KnowledgeStore


@pytest.fixture
def reflector_setup(tmp_knowledge: Path, tmp_memory: Path):
    """Set up a Reflector instance for testing."""
    ks = KnowledgeStore(str(tmp_knowledge))
    r = Reflector(str(tmp_memory), ks)
    return r


class TestAnalyzeIteration:
    """Tests for analyze_iteration."""

    def test_successful_iteration(self, reflector_setup) -> None:
        """Test analyzing a successful iteration."""
        r = reflector_setup
        data = {
            "iteration": 1,
            "node": "code",
            "result": "success",
            "duration": 5.2,
            "errors": [],
        }
        reflection = r.analyze_iteration(data)
        assert reflection["iteration"] == 1
        assert reflection["node"] == "code"
        assert reflection["success"] is True
        assert len(reflection["learnings"]) > 0
        assert len(reflection["issues"]) == 0
        assert "timestamp" in reflection

    def test_failed_iteration(self, reflector_setup) -> None:
        """Test analyzing a failed iteration."""
        r = reflector_setup
        data = {
            "iteration": 2,
            "node": "test",
            "result": "failed",
            "duration": 3.0,
            "errors": ["Test suite failed", "Coverage below 90%"],
        }
        reflection = r.analyze_iteration(data)
        assert reflection["success"] is False
        assert len(reflection["issues"]) >= 2

    def test_iteration_with_errors(self, reflector_setup) -> None:
        """Test analyzing an iteration with errors."""
        r = reflector_setup
        data = {
            "iteration": 3,
            "node": "review",
            "result": "partial",
            "duration": 1.0,
            "errors": ["Syntax error found"],
        }
        reflection = r.analyze_iteration(data)
        assert reflection["success"] is False
        assert any("Syntax error" in issue for issue in reflection["issues"])


class TestProposeEvolution:
    """Tests for propose_evolution."""

    def test_no_proposals_for_few_failures(self, reflector_setup) -> None:
        """Test that few failures do not generate proposals."""
        r = reflector_setup
        reflections = [
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
        ]
        proposals = r.propose_evolution(reflections)
        # 2 failures is below the threshold of 3
        code_proposals = [p for p in proposals if p["details"].get("node_id") == "code"]
        assert len(code_proposals) == 0

    def test_propose_for_repeated_failures(self, reflector_setup) -> None:
        """Test that 3+ failures on same node generates a proposal."""
        r = reflector_setup
        reflections = [
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
        ]
        proposals = r.propose_evolution(reflections)
        assert len(proposals) >= 1
        assert proposals[0]["type"] == "modify_prompt"
        assert "code" in proposals[0]["reason"]

    def test_propose_rule_for_consistent_success(self, reflector_setup) -> None:
        """Test that consistent success generates a rule proposal."""
        r = reflector_setup
        reflections = [
            {"node": "plan", "success": True, "learnings": ["ok"], "issues": []},
        ] * 5
        proposals = r.propose_evolution(reflections)
        rule_proposals = [p for p in proposals if p["type"] == "add_rule"]
        assert len(rule_proposals) >= 1


class TestExtractRules:
    """Tests for extract_rules."""

    def test_extract_rules_from_reflections(self, reflector_setup) -> None:
        """Test extracting rules from reflection patterns."""
        r = reflector_setup
        reflections = [
            {"node": "code", "success": True, "learnings": ["Keep functions small"], "issues": []},
            {"node": "code", "success": True, "learnings": ["Test first"], "issues": []},
            {"node": "code", "success": True, "learnings": ["Use type hints"], "issues": []},
        ]
        rules = r.extract_rules(reflections)
        assert len(rules) >= 1
        assert rules[0]["source"] == "reflector"
        assert "code" in rules[0]["tags"]

    def test_no_rules_for_few_learnings(self, reflector_setup) -> None:
        """Test that few learnings do not generate rules."""
        r = reflector_setup
        reflections = [
            {"node": "init", "success": True, "learnings": ["one"], "issues": []},
        ]
        rules = r.extract_rules(reflections)
        assert len(rules) == 0


class TestSummarizeProgress:
    """Tests for summarize_progress."""

    def test_summarize_basic(self, reflector_setup) -> None:
        """Test basic progress summary."""
        r = reflector_setup
        state = {
            "goal": "Build API",
            "iteration_count": 5,
            "max_iterations": 30,
            "status": "running",
            "current_node": "code",
            "errors": [],
        }
        summary = r.summarize_progress(state)
        assert "Build API" in summary
        assert "running" in summary
        assert "5" in summary
        assert "code" in summary

    def test_summarize_with_errors(self, reflector_setup) -> None:
        """Test progress summary with errors."""
        r = reflector_setup
        state = {
            "goal": "Fix bugs",
            "iteration_count": 3,
            "max_iterations": 10,
            "status": "running",
            "current_node": "test",
            "errors": ["First error", "Second error"],
        }
        summary = r.summarize_progress(state)
        assert "Second error" in summary


class TestFailureCategorization:
    """Tests for failure categorization."""

    def test_categorize_timeout(self, reflector_setup) -> None:
        """Test that timeout errors are categorized correctly."""
        r = reflector_setup
        assert r.categorize_failure(["Request timed out"], "") == "timeout"
        assert r.categorize_failure(["timeout exceeded"], "") == "timeout"

    def test_categorize_test_failure(self, reflector_setup) -> None:
        """Test that test failures are categorized correctly."""
        r = reflector_setup
        assert r.categorize_failure(["test suite failed with error"], "") == "test_failure"
        assert r.categorize_failure(["Test execution error"], "") == "test_failure"

    def test_categorize_code_error(self, reflector_setup) -> None:
        """Test that code errors are categorized correctly."""
        r = reflector_setup
        assert r.categorize_failure(["SyntaxError: invalid syntax"], "") == "code_error"
        assert r.categorize_failure(["TypeError: expected int"], "") == "code_error"
        assert r.categorize_failure(["NameError: undefined"], "") == "code_error"

    def test_categorize_dependency(self, reflector_setup) -> None:
        """Test that dependency issues are categorized correctly."""
        r = reflector_setup
        assert r.categorize_failure(["ImportError: no module"], "") == "dependency_issue"
        assert r.categorize_failure(["dependency not installed"], "") == "dependency_issue"
        assert r.categorize_failure(["module not found"], "") == "dependency_issue"

    def test_categorize_unknown(self, reflector_setup) -> None:
        """Test that unrecognizable errors return unknown."""
        r = reflector_setup
        assert r.categorize_failure(["something happened"], "") == "unknown"
        assert r.categorize_failure([], "") == "unknown"

    def test_propose_evolution_has_confidence(self, reflector_setup) -> None:
        """Test that proposals include confidence_score."""
        r = reflector_setup
        reflections = [
            {"node": "code", "success": False, "learnings": [], "issues": ["error occurred"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["error occurred"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["error occurred"]},
        ]
        proposals = r.propose_evolution(reflections)
        assert len(proposals) >= 1
        assert "confidence_score" in proposals[0]
        assert 0.0 <= proposals[0]["confidence_score"] <= 1.0

    def test_propose_evolution_has_failure_category(self, reflector_setup) -> None:
        """Test that proposals include failure_category."""
        r = reflector_setup
        reflections = [
            {"node": "code", "success": False, "learnings": [], "issues": ["timeout error"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["timeout exceeded"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["timed out"]},
        ]
        proposals = r.propose_evolution(reflections)
        assert len(proposals) >= 1
        assert "failure_category" in proposals[0]
        assert proposals[0]["failure_category"] == "timeout"
