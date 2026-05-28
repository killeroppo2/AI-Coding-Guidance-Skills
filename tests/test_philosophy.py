"""Tests for kernel/philosophy/principles.py - operational decision functions."""



from kernel.philosophy.principles import (
    assess_terrain,
    should_retreat,
    should_simplify,
    should_stop_iterating,
)


class TestShouldStopIterating:
    """Tests for should_stop_iterating."""

    def test_returns_false_with_fresh_state(self) -> None:
        """Fresh state with no history or reflections returns False."""
        assert should_stop_iterating({}, []) is False

    def test_returns_false_with_no_repeating_errors(self) -> None:
        """Diverse errors should not trigger stop."""
        reflections = [
            {"issues": ["error A"]},
            {"issues": ["error B"]},
            {"issues": ["error C"]},
        ]
        assert should_stop_iterating({}, reflections) is False

    def test_returns_true_with_3_same_errors(self) -> None:
        """Same error repeating 3+ times triggers stop."""
        reflections = [
            {"issues": ["timeout on node X"]},
            {"issues": ["timeout on node X"]},
            {"issues": ["timeout on node X"]},
        ]
        assert should_stop_iterating({}, reflections) is True

    def test_returns_true_with_more_than_3_same_errors(self) -> None:
        """Same error repeating 5 times triggers stop."""
        reflections = [
            {"issues": ["same error"]},
            {"issues": ["same error"]},
            {"issues": ["same error"]},
            {"issues": ["same error"]},
            {"issues": ["same error"]},
        ]
        assert should_stop_iterating({}, reflections) is True

    def test_returns_true_with_stalled_progress_history(self) -> None:
        """tasks_done unchanged over 5 entries triggers stop."""
        state = {"progress_history": [3, 3, 3, 3, 3]}
        assert should_stop_iterating(state, []) is True

    def test_returns_false_with_short_stalled_history(self) -> None:
        """Less than 5 entries even if stalled does not trigger."""
        state = {"progress_history": [3, 3, 3]}
        assert should_stop_iterating(state, []) is False

    def test_returns_false_with_advancing_progress(self) -> None:
        """Advancing progress_history does not trigger stop."""
        state = {"progress_history": [1, 2, 3, 4, 5]}
        assert should_stop_iterating(state, []) is False

    def test_returns_true_stalled_with_longer_history(self) -> None:
        """Last 5 entries stalled even with earlier progress."""
        state = {"progress_history": [1, 2, 3, 3, 3, 3, 3, 3]}
        assert should_stop_iterating(state, []) is True

    def test_multiple_issues_per_reflection(self) -> None:
        """Multiple issues in a single reflection are counted separately."""
        reflections = [
            {"issues": ["err A", "err B"]},
            {"issues": ["err A"]},
            {"issues": ["err A"]},
        ]
        assert should_stop_iterating({}, reflections) is True

    def test_empty_issues_list(self) -> None:
        """Reflections with empty issues lists do not trigger."""
        assert should_stop_iterating({}, []) is False

    def test_mixed_errors_below_threshold(self) -> None:
        """Two of same error and one different does not trigger."""
        reflections = [
            {"issues": ["err A"]},
            {"issues": ["err A"]},
            {"issues": ["err B"]},
        ]
        assert should_stop_iterating({}, reflections) is False


class TestShouldSimplify:
    """Tests for should_simplify."""

    def test_returns_false_with_zero_failures(self) -> None:
        """No failures means no simplification needed."""
        assert should_simplify(0) is False

    def test_returns_false_with_one_failure(self) -> None:
        """Single failure does not warrant simplification."""
        assert should_simplify(1) is False

    def test_returns_false_with_two_failures(self) -> None:
        """Two failures still below threshold."""
        assert should_simplify(2) is False

    def test_returns_true_with_three_failures(self) -> None:
        """Exactly 3 failures triggers simplification."""
        assert should_simplify(3) is True

    def test_returns_true_with_many_failures(self) -> None:
        """High failure count always triggers."""
        assert should_simplify(10) is True


class TestShouldRetreat:
    """Tests for should_retreat."""

    def test_returns_false_with_zero_failures(self) -> None:
        """No failures means no retreat."""
        assert should_retreat("node_a", 0) is False

    def test_returns_false_below_threshold(self) -> None:
        """Failures below max_retries do not trigger retreat."""
        assert should_retreat("node_a", 3, max_retries=5) is False

    def test_returns_true_at_threshold(self) -> None:
        """Failures equal to max_retries triggers retreat."""
        assert should_retreat("node_a", 5, max_retries=5) is True

    def test_returns_true_above_threshold(self) -> None:
        """Failures above max_retries triggers retreat."""
        assert should_retreat("node_a", 7, max_retries=5) is True

    def test_default_max_retries_is_5(self) -> None:
        """Default max_retries value is 5."""
        assert should_retreat("node_x", 4) is False
        assert should_retreat("node_x", 5) is True

    def test_custom_max_retries(self) -> None:
        """Custom max_retries is respected."""
        assert should_retreat("n", 2, max_retries=2) is True
        assert should_retreat("n", 1, max_retries=2) is False

    def test_node_id_is_informational(self) -> None:
        """node_id does not affect the logic."""
        assert should_retreat("any_node", 5, max_retries=5) is True
        assert should_retreat("", 5, max_retries=5) is True


class TestAssessTerrain:
    """Tests for assess_terrain."""

    def test_full_coverage(self) -> None:
        """All goal keywords matched by skills."""
        skills = [
            {"name": "web-skill", "tags": ["rest", "api", "server"], "description": "REST APIs server"},
        ]
        result = assess_terrain("rest api server", skills)
        assert result["coverage_score"] == 1.0
        assert "web-skill" in result["covered"]
        assert result["gaps"] == []
        assert result["recommendation"] == "proceed"

    def test_partial_coverage(self) -> None:
        """Some keywords matched, some not."""
        skills = [
            {"name": "db-skill", "tags": ["database", "sql"], "description": "Database operations"},
        ]
        result = assess_terrain("database authentication layer", skills)
        assert 0.0 < result["coverage_score"] < 1.0
        assert "db-skill" in result["covered"]
        assert len(result["gaps"]) > 0

    def test_no_coverage(self) -> None:
        """No keywords matched."""
        skills = [
            {"name": "math-skill", "tags": ["math", "algebra"], "description": "Math computations"},
        ]
        result = assess_terrain("deploy web server", skills)
        assert result["coverage_score"] == 0.0
        assert result["covered"] == []
        assert result["recommendation"] == "reconsider"

    def test_empty_goal(self) -> None:
        """Empty goal returns zero coverage and reconsider."""
        skills = [
            {"name": "any-skill", "tags": ["test"], "description": "Anything"},
        ]
        result = assess_terrain("", skills)
        assert result["coverage_score"] == 0.0
        assert result["recommendation"] == "reconsider"

    def test_empty_skills(self) -> None:
        """No skills means no coverage."""
        result = assess_terrain("deploy web api", [])
        assert result["coverage_score"] == 0.0
        assert result["covered"] == []
        assert len(result["gaps"]) > 0
        assert result["recommendation"] == "reconsider"

    def test_short_words_filtered_from_goal(self) -> None:
        """Words with fewer than 3 characters are filtered out."""
        skills = [
            {"name": "api-skill", "tags": ["api"], "description": "API tools"},
        ]
        # "a" and "an" should be filtered, only "api" counted
        result = assess_terrain("a an api", skills)
        assert result["coverage_score"] == 1.0

    def test_proceed_with_caution_range(self) -> None:
        """Coverage between 0.4 and 0.7 gives proceed_with_caution."""
        skills = [
            {"name": "code-skill", "tags": ["code", "python"], "description": "Code python"},
        ]
        # "python code testing deploy release" - 5 keywords, likely 2 match
        result = assess_terrain("python code testing deploy release", skills)
        assert result["recommendation"] in ("proceed_with_caution", "reconsider", "proceed")

    def test_matching_via_description_words(self) -> None:
        """Keywords can match via skill description words."""
        skills = [
            {"name": "deploy-skill", "tags": [], "description": "Deploy applications to cloud"},
        ]
        result = assess_terrain("deploy applications", skills)
        assert result["coverage_score"] > 0.0
        assert "deploy-skill" in result["covered"]

    def test_matching_via_tags(self) -> None:
        """Keywords can match via skill tags."""
        skills = [
            {"name": "test-skill", "tags": ["testing", "pytest"], "description": ""},
        ]
        result = assess_terrain("testing pytest", skills)
        assert result["coverage_score"] > 0.0
        assert "test-skill" in result["covered"]

    def test_multiple_skills_contribute(self) -> None:
        """Multiple skills can cover different keywords."""
        skills = [
            {"name": "api-skill", "tags": ["api", "rest"], "description": "REST API"},
            {"name": "db-skill", "tags": ["database"], "description": "Database layer"},
        ]
        result = assess_terrain("rest api database", skills)
        assert result["coverage_score"] > 0.5
        assert len(result["covered"]) >= 1


class TestReflectorPhilosophySignals:
    """Integration tests: reflector output includes philosophy_signals."""

    def test_analyze_iteration_has_philosophy_signals(self, tmp_knowledge, tmp_memory) -> None:
        """Verify that analyze_iteration output includes philosophy_signals."""
        from kernel.reflector import Reflector
        from knowledge.store import KnowledgeStore

        ks = KnowledgeStore(str(tmp_knowledge))
        r = Reflector(str(tmp_memory), ks)
        data = {
            "iteration": 1,
            "node": "code",
            "result": "success",
            "duration": 2.0,
            "errors": [],
        }
        reflection = r.analyze_iteration(data)
        assert "philosophy_signals" in reflection
        assert "stop_suggested" in reflection["philosophy_signals"]
        assert reflection["philosophy_signals"]["stop_suggested"] is False

    def test_propose_evolution_includes_simplify_proposal(self, tmp_knowledge, tmp_memory) -> None:
        """Verify that propose_evolution adds simplify proposals for high failure counts."""
        from kernel.reflector import Reflector
        from knowledge.store import KnowledgeStore

        ks = KnowledgeStore(str(tmp_knowledge))
        r = Reflector(str(tmp_memory), ks)
        reflections = [
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
            {"node": "code", "success": False, "learnings": [], "issues": ["err"]},
        ]
        proposals = r.propose_evolution(reflections)
        simplify_proposals = [
            p for p in proposals if "\u5927\u9053\u81f3\u7b80" in p.get("reason", "")
        ]
        assert len(simplify_proposals) >= 1
