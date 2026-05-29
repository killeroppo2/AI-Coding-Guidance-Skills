"""Tests for kernel.philosophy.guards module."""

from unittest.mock import MagicMock

from kernel.philosophy.guards import bing_gui_shen_su, shui_guard, wu_wei_guard


class TestWuWeiGuard:
    """Tests for wu_wei_guard function."""

    def test_wu_wei_guard_returns_true_when_no_history(self):
        """Guard allows action when no progress_history exists."""
        state = {}
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_returns_true_with_varied_progress(self):
        """Guard allows action when progress values are changing."""
        state = {"progress_history": [1, 2, 3, 4]}
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_returns_false_when_stalled(self):
        """Guard blocks action when last 3 progress values are identical."""
        state = {"progress_history": [1, 2, 3, 3, 3]}
        assert wu_wei_guard(state, "iterate") is False

    def test_wu_wei_guard_returns_false_when_stalled_many(self):
        """Guard blocks action when last 5+ progress values are identical."""
        state = {"progress_history": [0, 1, 2, 2, 2, 2, 2]}
        assert wu_wei_guard(state, "iterate") is False

    def test_wu_wei_guard_returns_true_with_short_history(self):
        """Guard allows action when fewer than 3 entries exist."""
        state = {"progress_history": [1, 1]}
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_returns_true_with_recent_change(self):
        """Guard allows action when only last 2 are same but 3rd differs."""
        state = {"progress_history": [1, 2, 3, 3]}
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_allows_when_workspace_errors_exist(self):
        """Guard allows action when stalled but workspace path errors present."""
        state = {
            "progress_history": [6, 6, 6],
            "errors": ["Path 'src/main.py' is outside workspace './workspace/project/'"],
        }
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_allows_when_security_errors_exist(self):
        """Guard allows action when stalled but security denial errors present."""
        state = {
            "progress_history": [6, 6, 6],
            "errors": ["[SECURITY] Denied file write: src/main.py"],
        }
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_allows_when_boundary_errors_exist(self):
        """Guard allows action when stalled but boundary violation errors present."""
        state = {
            "progress_history": [6, 6, 6],
            "errors": ["Workspace boundary violation: file outside allowed area"],
        }
        assert wu_wei_guard(state, "iterate") is True

    def test_wu_wei_guard_stops_when_stalled_without_path_errors(self):
        """Guard still stops when stalled and errors are unrelated to paths."""
        state = {
            "progress_history": [6, 6, 6],
            "errors": ["AI command exited with code 1 on node code"],
        }
        assert wu_wei_guard(state, "iterate") is False

    def test_wu_wei_guard_allows_when_old_errors_but_recent_path_error(self):
        """Guard allows when recent errors (last 5) contain path errors."""
        state = {
            "progress_history": [6, 6, 6],
            "errors": [
                "some old error",
                "another old error",
                "yet another error",
                "more errors",
                "even more errors",
                "still more errors",
                "Workspace boundary: Path outside workspace",
            ],
        }
        assert wu_wei_guard(state, "iterate") is True


class TestShuiGuard:
    """Tests for shui_guard function."""

    def test_shui_guard_returns_original_when_no_data(self):
        """Skills unchanged when feedback store has no entries."""
        store = MagicMock()
        store._read_entries.return_value = []
        result = shui_guard(["skill-a", "skill-b"], store, "code", "feature")
        assert result == ["skill-a", "skill-b"]

    def test_shui_guard_returns_empty_when_empty_input(self):
        """Returns empty list when given empty proposed_skills."""
        store = MagicMock()
        result = shui_guard([], store, "code", "feature")
        assert result == []

    def test_shui_guard_filters_high_failure_skills(self):
        """Filters out skills with >70% failure rate."""
        store = MagicMock()
        # skill-a: 1 success, 4 failures = 80% failure rate
        # skill-b: 3 successes, 1 failure = 25% failure rate
        store._read_entries.return_value = [
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "success"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "success"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "success"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "success"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "failed"},
        ]
        result = shui_guard(["skill-a", "skill-b"], store, "code", "feature")
        assert "skill-a" not in result
        assert "skill-b" in result

    def test_shui_guard_returns_original_when_all_would_be_filtered(self):
        """Returns original list when filtering would leave nothing."""
        store = MagicMock()
        # Both skills have >70% failure rate
        store._read_entries.return_value = [
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-b"], "outcome": "failed"},
        ]
        result = shui_guard(["skill-a", "skill-b"], store, "code", "feature")
        assert result == ["skill-a", "skill-b"]

    def test_shui_guard_keeps_skills_with_insufficient_data(self):
        """Skills with fewer than 3 data points are kept regardless of rate."""
        store = MagicMock()
        # skill-a: 2 failures only (not enough data to judge)
        store._read_entries.return_value = [
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "code", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
        ]
        result = shui_guard(["skill-a"], store, "code", "feature")
        assert result == ["skill-a"]

    def test_shui_guard_ignores_entries_from_other_nodes(self):
        """Only considers entries matching node_id and goal_type."""
        store = MagicMock()
        # Entries for different node - should be ignored
        store._read_entries.return_value = [
            {"node_id": "plan", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "plan", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "plan", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
            {"node_id": "plan", "goal_type": "feature", "skills_used": ["skill-a"], "outcome": "failed"},
        ]
        result = shui_guard(["skill-a"], store, "code", "feature")
        assert result == ["skill-a"]


class TestBingGuiShenSu:
    """Tests for bing_gui_shen_su function."""

    def test_bing_gui_shen_su_returns_keep_normal(self):
        """Returns 'keep' for normal iteration counts."""
        assert bing_gui_shen_su(5, 0) == "keep"

    def test_bing_gui_shen_su_returns_low_when_stalling(self):
        """Returns 'low' when 10+ iterations with 0 tasks done."""
        assert bing_gui_shen_su(10, 0) == "low"

    def test_bing_gui_shen_su_returns_low_with_many_iterations(self):
        """Returns 'low' when far beyond 10 iterations with no progress."""
        assert bing_gui_shen_su(25, 0) == "low"

    def test_bing_gui_shen_su_returns_keep_with_progress(self):
        """Returns 'keep' when iterations are high but tasks are done."""
        assert bing_gui_shen_su(10, 1) == "keep"
        assert bing_gui_shen_su(15, 3) == "keep"

    def test_bing_gui_shen_su_returns_keep_at_boundary(self):
        """Returns 'keep' when just below 10 iterations."""
        assert bing_gui_shen_su(9, 0) == "keep"
