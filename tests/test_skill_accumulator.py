"""Tests for the SkillAccumulator class."""

import json
from pathlib import Path

import pytest
import yaml

from kernel.skill_accumulator import SkillAccumulator


@pytest.fixture
def accumulator_setup(tmp_path: Path):
    """Set up a skill accumulator test environment."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    accumulator = SkillAccumulator(str(skills_dir), str(memory_dir))
    return accumulator, skills_dir, memory_dir


class TestDetectPatterns:
    """Tests for SkillAccumulator.detect_patterns."""

    def test_detects_workflow_pattern_with_3_successes(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        reflections = [
            {"node": "code", "success": True},
            {"node": "code", "success": True},
            {"node": "code", "success": True},
        ]
        patterns = accumulator.detect_patterns(reflections)
        assert len(patterns) >= 1
        workflow_patterns = [p for p in patterns if p["pattern_type"] == "workflow"]
        assert len(workflow_patterns) == 1
        assert workflow_patterns[0]["frequency"] == 3
        assert "code" in workflow_patterns[0]["name"]

    def test_no_pattern_below_threshold(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        reflections = [
            {"node": "code", "success": True},
            {"node": "code", "success": True},
        ]
        patterns = accumulator.detect_patterns(reflections)
        workflow_patterns = [p for p in patterns if p["pattern_type"] == "workflow"]
        assert len(workflow_patterns) == 0

    def test_detects_resolution_pattern(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        reflections = [
            {"node": "code", "errors": ["timeout"], "success": False},
            {"node": "code", "errors": ["timeout"], "success": False},
            {"node": "code", "errors": ["timeout"], "success": False},
        ]
        patterns = accumulator.detect_patterns(reflections)
        resolution_patterns = [p for p in patterns if p["pattern_type"] == "resolution"]
        assert len(resolution_patterns) >= 1
        assert resolution_patterns[0]["frequency"] >= 3

    def test_empty_reflections_returns_empty(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        patterns = accumulator.detect_patterns([])
        assert patterns == []

    def test_mixed_nodes_detected_separately(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        reflections = [
            {"node": "code", "success": True},
            {"node": "code", "success": True},
            {"node": "code", "success": True},
            {"node": "plan", "success": True},
            {"node": "plan", "success": True},
            {"node": "plan", "success": True},
            {"node": "plan", "success": True},
        ]
        patterns = accumulator.detect_patterns(reflections)
        workflow_patterns = [p for p in patterns if p["pattern_type"] == "workflow"]
        assert len(workflow_patterns) == 2


class TestAnalyzeCompletion:
    """Tests for SkillAccumulator.analyze_completion."""

    def test_proposes_skill_when_pattern_found(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        project_data = {
            "goal": "build a web app",
            "skills_used": ["tdd"],
            "outcome": "success",
            "reflections": [
                {"node": "code", "success": True},
                {"node": "code", "success": True},
                {"node": "code", "success": True},
            ],
        }
        proposals = accumulator.analyze_completion(project_data)
        assert len(proposals) >= 1
        assert proposals[0]["name"]
        assert proposals[0]["description"]
        assert proposals[0]["content"]
        assert "auto-generated" in proposals[0]["tags"]

    def test_no_proposals_below_threshold(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        project_data = {
            "goal": "build something",
            "skills_used": [],
            "outcome": "success",
            "reflections": [
                {"node": "code", "success": True},
                {"node": "code", "success": True},
            ],
        }
        proposals = accumulator.analyze_completion(project_data)
        assert proposals == []

    def test_empty_reflections_no_proposals(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        project_data = {
            "goal": "test",
            "skills_used": [],
            "outcome": "success",
            "reflections": [],
        }
        proposals = accumulator.analyze_completion(project_data)
        assert proposals == []


class TestMetrics:
    """Tests for SkillAccumulator metrics tracking."""

    def test_update_metrics_creates_file(self, accumulator_setup) -> None:
        accumulator, skills_dir, _ = accumulator_setup
        accumulator.update_metrics("tdd", True, 5)
        assert (skills_dir / "_metrics.yaml").exists()

    def test_update_metrics_records_correctly(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        accumulator.update_metrics("tdd", True, 5)
        metrics = accumulator.get_skill_metrics("tdd")
        assert metrics["times_used"] == 1
        assert metrics["success_rate"] == 1.0
        assert metrics["avg_iterations"] == 5.0

    def test_get_skill_metrics_unknown_returns_zeros(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        metrics = accumulator.get_skill_metrics("nonexistent")
        assert metrics["times_used"] == 0
        assert metrics["success_rate"] == 0.0
        assert metrics["avg_iterations"] == 0.0

    def test_multiple_updates_accumulate(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        accumulator.update_metrics("tdd", True, 4)
        accumulator.update_metrics("tdd", True, 6)
        accumulator.update_metrics("tdd", False, 10)
        metrics = accumulator.get_skill_metrics("tdd")
        assert metrics["times_used"] == 3
        assert metrics["success_rate"] == pytest.approx(2.0 / 3.0)
        assert metrics["avg_iterations"] == pytest.approx(20.0 / 3.0)

    def test_get_all_metrics(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        accumulator.update_metrics("tdd", True, 4)
        accumulator.update_metrics("ralph", False, 8)
        all_metrics = accumulator.get_all_metrics()
        assert "tdd" in all_metrics
        assert "ralph" in all_metrics
        assert all_metrics["tdd"]["times_used"] == 1
        assert all_metrics["ralph"]["success_rate"] == 0.0

    def test_get_all_metrics_empty(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        all_metrics = accumulator.get_all_metrics()
        assert all_metrics == {}

    def test_metrics_persistence(self, accumulator_setup) -> None:
        accumulator, skills_dir, memory_dir = accumulator_setup
        accumulator.update_metrics("tdd", True, 5)
        # Create a new instance to verify persistence
        accumulator2 = SkillAccumulator(str(skills_dir), str(memory_dir))
        metrics = accumulator2.get_skill_metrics("tdd")
        assert metrics["times_used"] == 1


class TestPatternToSkillName:
    """Tests for pattern name to skill name conversion."""

    def test_simple_name(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        assert accumulator._pattern_to_skill_name("code-workflow") == "code-workflow"

    def test_special_chars_removed(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        result = accumulator._pattern_to_skill_name("code:error_fix")
        assert ":" not in result
        assert "_" not in result

    def test_uppercase_lowered(self, accumulator_setup) -> None:
        accumulator, _, _ = accumulator_setup
        result = accumulator._pattern_to_skill_name("CODE-Workflow")
        assert result == "code-workflow"
