"""Tests for kernel/skill_feedback.py - SkillFeedbackStore."""

import json

import pytest

from kernel.skill_feedback import SkillFeedbackStore


@pytest.fixture
def store(tmp_path) -> SkillFeedbackStore:
    """Return a SkillFeedbackStore using a temp directory."""
    return SkillFeedbackStore(str(tmp_path / "memory"))


class TestRecord:
    """Tests for SkillFeedbackStore.record."""

    def test_record_appends_to_file(self, store: SkillFeedbackStore) -> None:
        """Recording entries appends lines to the JSONL file."""
        store.record("code", ["ralph", "tdd"], "success", "build")
        store.record("code", ["ralph"], "failed", "build")

        lines = store._path.read_text().strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["node_id"] == "code"
        assert first["skills_used"] == ["ralph", "tdd"]
        assert first["outcome"] == "success"
        assert first["goal_type"] == "build"

    def test_record_includes_timestamp(self, store: SkillFeedbackStore) -> None:
        """Each recorded entry includes a timestamp."""
        store.record("test", ["tdd"], "success", "fix")

        lines = store._path.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert "timestamp" in entry
        # Verify ISO format with Z suffix
        assert entry["timestamp"].endswith("Z")
        assert "T" in entry["timestamp"]


class TestGetRecommendations:
    """Tests for SkillFeedbackStore.get_recommendations."""

    def test_get_recommendations_basic(self, store: SkillFeedbackStore) -> None:
        """Skills with enough data points and high success rate are recommended."""
        # ralph: 4 successes, 1 failure = 80%
        for _ in range(4):
            store.record("code", ["ralph"], "success", "build")
        store.record("code", ["ralph"], "failed", "build")

        # tdd: 3 successes, 0 failures = 100%
        for _ in range(3):
            store.record("code", ["tdd"], "success", "build")

        recs = store.get_recommendations("code", "build")
        assert "tdd" in recs
        assert "ralph" in recs
        # tdd should be first (higher rate)
        assert recs.index("tdd") < recs.index("ralph")

    def test_get_recommendations_minimum_data_points(
        self, store: SkillFeedbackStore
    ) -> None:
        """Skills with fewer than 3 data points are not recommended."""
        # Only 2 entries for this skill (even if 100% success)
        store.record("code", ["new-skill"], "success", "build")
        store.record("code", ["new-skill"], "success", "build")

        recs = store.get_recommendations("code", "build")
        assert "new-skill" not in recs

    def test_get_recommendations_success_rate_threshold(
        self, store: SkillFeedbackStore
    ) -> None:
        """Skills with less than 60% success rate are not recommended."""
        # 2 successes, 3 failures = 40%
        store.record("code", ["weak-skill"], "success", "build")
        store.record("code", ["weak-skill"], "success", "build")
        store.record("code", ["weak-skill"], "failed", "build")
        store.record("code", ["weak-skill"], "failed", "build")
        store.record("code", ["weak-skill"], "failed", "build")

        recs = store.get_recommendations("code", "build")
        assert "weak-skill" not in recs

    def test_get_recommendations_empty_store(
        self, store: SkillFeedbackStore
    ) -> None:
        """Empty store returns empty recommendations."""
        recs = store.get_recommendations("code", "build")
        assert recs == []

    def test_get_recommendations_filters_by_node_and_goal_type(
        self, store: SkillFeedbackStore
    ) -> None:
        """Recommendations are filtered by node_id and goal_type."""
        # Good skill for code+build
        for _ in range(4):
            store.record("code", ["ralph"], "success", "build")

        # Same skill but for test+fix (different context)
        for _ in range(4):
            store.record("test", ["ralph"], "failed", "fix")

        # Querying code+build should recommend ralph
        recs_code = store.get_recommendations("code", "build")
        assert "ralph" in recs_code

        # Querying test+fix should NOT recommend ralph (0% success)
        recs_test = store.get_recommendations("test", "fix")
        assert "ralph" not in recs_test


class TestPrune:
    """Tests for SkillFeedbackStore._prune."""

    def test_prune_at_500_entries(self, store: SkillFeedbackStore) -> None:
        """Writing 600 entries results in only 500 remaining after prune."""
        # Write 600 entries directly to avoid calling _prune 600 times
        store._path.parent.mkdir(parents=True, exist_ok=True)
        with open(store._path, "w") as f:
            for i in range(600):
                entry = {
                    "node_id": "code",
                    "skills_used": ["ralph"],
                    "outcome": "success",
                    "goal_type": "build",
                    "timestamp": f"2025-01-01T00:00:{i:02d}Z",
                }
                f.write(json.dumps(entry) + "\n")

        store._prune()

        lines = [l for l in store._path.read_text().strip().split("\n") if l]
        assert len(lines) == 500


class TestGetStats:
    """Tests for SkillFeedbackStore.get_stats."""

    def test_get_stats_correct_counts(self, store: SkillFeedbackStore) -> None:
        """get_stats returns correct summary information."""
        store.record("code", ["ralph", "tdd"], "success", "build")
        store.record("test", ["tdd"], "failed", "fix")
        store.record("code", ["prototype"], "success", "explore")

        stats = store.get_stats()
        assert stats["total_entries"] == 3
        assert stats["unique_skills"] == 3  # ralph, tdd, prototype
        assert stats["unique_nodes"] == 2  # code, test
        assert isinstance(stats["top_skills"], list)
        assert len(stats["top_skills"]) <= 5

    def test_multiple_goal_types_tracked_independently(
        self, store: SkillFeedbackStore
    ) -> None:
        """Different goal types maintain independent tracking."""
        # ralph is great for build
        for _ in range(4):
            store.record("code", ["ralph"], "success", "build")

        # ralph is terrible for fix
        for _ in range(4):
            store.record("code", ["ralph"], "failed", "fix")

        # Should be recommended for build but not fix
        build_recs = store.get_recommendations("code", "build")
        fix_recs = store.get_recommendations("code", "fix")

        assert "ralph" in build_recs
        assert "ralph" not in fix_recs
