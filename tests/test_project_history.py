"""Tests for the ProjectHistory class."""

from pathlib import Path

import pytest

from kernel.project_history import ProjectHistory


@pytest.fixture
def history_setup(tmp_path: Path):
    """Set up a project history test environment."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    history = ProjectHistory(str(memory_dir))
    return history, memory_dir


class TestRecordProject:
    """Tests for ProjectHistory.record_project."""

    def test_record_creates_file(self, history_setup) -> None:
        history, memory_dir = history_setup
        project = {
            "goal": "build a web app",
            "skills_used": ["tdd", "prototype"],
            "iterations_needed": 5,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": ["init", "plan", "code"],
        }
        history.record_project(project)
        assert (memory_dir / "projects_completed.jsonl").exists()

    def test_record_and_load_back(self, history_setup) -> None:
        history, _ = history_setup
        project = {
            "goal": "build a web app",
            "skills_used": ["tdd"],
            "iterations_needed": 5,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": ["init", "plan", "code"],
        }
        history.record_project(project)
        loaded = history._load_history()
        assert len(loaded) == 1
        assert loaded[0]["goal"] == "build a web app"

    def test_multiple_records_append(self, history_setup) -> None:
        history, _ = history_setup
        for i in range(3):
            history.record_project({
                "goal": f"project {i}",
                "skills_used": [],
                "iterations_needed": i,
                "outcome": "success",
                "timestamp": f"2025-01-0{i+1}T00:00:00Z",
                "nodes_visited": [],
            })
        loaded = history._load_history()
        assert len(loaded) == 3


class TestSimilaritySearch:
    """Tests for ProjectHistory.get_similar_past_projects."""

    def test_finds_matching_project(self, history_setup) -> None:
        history, _ = history_setup
        history.record_project({
            "goal": "build react web application",
            "skills_used": ["prototype"],
            "iterations_needed": 3,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": ["init", "code"],
        })
        history.record_project({
            "goal": "write python script",
            "skills_used": ["tdd"],
            "iterations_needed": 2,
            "outcome": "success",
            "timestamp": "2025-01-02T00:00:00Z",
            "nodes_visited": ["init", "code"],
        })
        results = history.get_similar_past_projects("build react app")
        assert len(results) >= 1
        assert results[0]["goal"] == "build react web application"

    def test_returns_empty_when_no_history(self, history_setup) -> None:
        history, _ = history_setup
        results = history.get_similar_past_projects("build something")
        assert results == []

    def test_top_k_limits_results(self, history_setup) -> None:
        history, _ = history_setup
        for i in range(10):
            history.record_project({
                "goal": f"build web project number {i}",
                "skills_used": [],
                "iterations_needed": 1,
                "outcome": "success",
                "timestamp": "2025-01-01T00:00:00Z",
                "nodes_visited": [],
            })
        results = history.get_similar_past_projects("build web project", top_k=2)
        assert len(results) == 2

    def test_returns_empty_for_no_overlap(self, history_setup) -> None:
        history, _ = history_setup
        history.record_project({
            "goal": "build react web application",
            "skills_used": [],
            "iterations_needed": 3,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": [],
        })
        results = history.get_similar_past_projects("deploy kubernetes cluster")
        assert results == []


class TestRecommendedSkills:
    """Tests for ProjectHistory.get_recommended_skills."""

    def test_recommends_from_successful_projects(self, history_setup) -> None:
        history, _ = history_setup
        history.record_project({
            "goal": "build web dashboard",
            "skills_used": ["prototype", "ui-styling"],
            "iterations_needed": 4,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": [],
        })
        recommended = history.get_recommended_skills("build web app dashboard")
        assert "prototype" in recommended
        assert "ui-styling" in recommended

    def test_excludes_failed_projects(self, history_setup) -> None:
        history, _ = history_setup
        history.record_project({
            "goal": "build web dashboard",
            "skills_used": ["bad-skill"],
            "iterations_needed": 10,
            "outcome": "failed",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": [],
        })
        history.record_project({
            "goal": "build web dashboard v2",
            "skills_used": ["good-skill"],
            "iterations_needed": 3,
            "outcome": "success",
            "timestamp": "2025-01-02T00:00:00Z",
            "nodes_visited": [],
        })
        recommended = history.get_recommended_skills("build web dashboard")
        assert "bad-skill" not in recommended
        assert "good-skill" in recommended

    def test_deduplicates_skills(self, history_setup) -> None:
        history, _ = history_setup
        history.record_project({
            "goal": "build web app",
            "skills_used": ["tdd", "prototype"],
            "iterations_needed": 3,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": [],
        })
        history.record_project({
            "goal": "create web application",
            "skills_used": ["tdd", "ui-styling"],
            "iterations_needed": 4,
            "outcome": "success",
            "timestamp": "2025-01-02T00:00:00Z",
            "nodes_visited": [],
        })
        recommended = history.get_recommended_skills("build web app")
        # tdd should only appear once
        assert recommended.count("tdd") == 1


class TestStats:
    """Tests for ProjectHistory.get_stats."""

    def test_stats_with_multiple_projects(self, history_setup) -> None:
        history, _ = history_setup
        history.record_project({
            "goal": "project 1",
            "skills_used": ["tdd"],
            "iterations_needed": 5,
            "outcome": "success",
            "timestamp": "2025-01-01T00:00:00Z",
            "nodes_visited": [],
        })
        history.record_project({
            "goal": "project 2",
            "skills_used": ["tdd", "prototype"],
            "iterations_needed": 10,
            "outcome": "failed",
            "timestamp": "2025-01-02T00:00:00Z",
            "nodes_visited": [],
        })
        stats = history.get_stats()
        assert stats["total_projects"] == 2
        assert stats["success_rate"] == pytest.approx(0.5)
        assert stats["avg_iterations"] == pytest.approx(7.5)
        assert "tdd" in stats["most_used_skills"]

    def test_stats_empty_history(self, history_setup) -> None:
        history, _ = history_setup
        stats = history.get_stats()
        assert stats["total_projects"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["most_used_skills"] == []
        assert stats["avg_iterations"] == 0.0


class TestTokenize:
    """Tests for ProjectHistory._tokenize."""

    def test_removes_stop_words(self, history_setup) -> None:
        history, _ = history_setup
        tokens = history._tokenize("build a web app for the user")
        assert "a" not in tokens
        assert "for" not in tokens
        assert "the" not in tokens
        assert "build" in tokens
        assert "web" in tokens
        assert "app" in tokens
        assert "user" in tokens

    def test_lowercases_tokens(self, history_setup) -> None:
        history, _ = history_setup
        tokens = history._tokenize("Build Web App")
        assert "build" in tokens
        assert "Build" not in tokens

    def test_splits_on_non_alphanumeric(self, history_setup) -> None:
        history, _ = history_setup
        tokens = history._tokenize("build-web_app/fast")
        assert "build" in tokens
        assert "web" in tokens
        assert "app" in tokens
        assert "fast" in tokens

    def test_empty_string(self, history_setup) -> None:
        history, _ = history_setup
        tokens = history._tokenize("")
        assert tokens == set()
