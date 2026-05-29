"""Tests for kernel/phase_router.py - PhaseRouter and SkillSelection."""

import pytest

from kernel.intent_analyzer import IntentResult
from kernel.phase_router import PhaseRouter, SkillSelection


@pytest.fixture
def skills_index() -> dict:
    """Return a minimal skills index for testing."""
    return {
        "core_items": [
            {
                "name": "grill-me",
                "composable_with": ["grill-with-docs", "to-prd"],
            },
            {
                "name": "prd",
                "composable_with": ["ralph", "to-issues", "grill-me"],
            },
            {
                "name": "ralph",
                "composable_with": ["prd", "tdd", "diagnose"],
            },
            {
                "name": "tdd",
                "composable_with": ["ralph", "diagnose", "prototype"],
            },
            {
                "name": "prototype",
                "composable_with": ["tdd", "ui-ux-pro-max"],
            },
            {
                "name": "relentless-iteration",
                "composable_with": [
                    "tdd",
                    "diagnose",
                    "improve-codebase-architecture",
                    "ux-audit",
                    "ui-ux-pro-max",
                ],
            },
            {
                "name": "zoom-out",
                "composable_with": ["improve-codebase-architecture", "handoff"],
            },
            {
                "name": "handoff",
                "composable_with": ["zoom-out"],
            },
            {
                "name": "write-a-skill",
                "composable_with": [],
            },
            {
                "name": "diagnose",
                "composable_with": ["ralph", "tdd"],
            },
        ],
        "community_items": [
            {
                "name": "to-prd",
                "composable_with": ["prd", "grill-me", "to-issues"],
            },
            {
                "name": "improve-codebase-architecture",
                "composable_with": ["diagnose", "zoom-out"],
            },
            {
                "name": "ux-audit",
                "composable_with": ["relentless-iteration", "ui-ux-pro-max", "diagnose"],
            },
        ],
    }


@pytest.fixture
def workflow() -> dict:
    """Return a minimal workflow mapping phases to skill lists."""
    return {
        "idea_phase": ["grill-me", "grill-with-docs"],
        "requirements_phase": ["prd", "to-issues", "to-prd"],
        "execution_phase": ["ralph", "tdd", "prototype"],
        "quality_phase": [
            "diagnose",
            "relentless-iteration",
            "improve-codebase-architecture",
            "ux-audit",
        ],
        "lifecycle_phase": ["handoff", "zoom-out"],
        "meta_phase": ["write-a-skill"],
    }


@pytest.fixture
def router(skills_index: dict, workflow: dict) -> PhaseRouter:
    """Return a PhaseRouter instance with test data."""
    return PhaseRouter(skills_index=skills_index, workflow=workflow)


def _make_intent(
    goal_type: str = "build",
    output_form: str = "unknown",
    is_vague: bool = False,
) -> IntentResult:
    """Helper to create IntentResult for testing."""
    return IntentResult(
        goal_type=goal_type,
        output_form=output_form,
        tech_hints=[],
        language="en",
        is_vague=is_vague,
    )


# --- Node routing tests ---


class TestNodeRouting:
    """Test routing for each node returns correct primary skills."""

    def test_init_node_empty(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("init", intent, "medium")
        assert result.primary == []

    def test_plan_node_default(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("plan", intent, "medium")
        assert result.primary == ["prd"]

    def test_code_node_default(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("code", intent, "medium")
        assert result.primary == ["ralph"]

    def test_test_node(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("test", intent, "medium")
        assert result.primary == ["tdd"]

    def test_review_node(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("review", intent, "medium")
        assert result.primary == ["relentless-iteration"]

    def test_reflect_node(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("reflect", intent, "medium")
        assert result.primary == ["zoom-out"]

    def test_evolve_node(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("evolve", intent, "medium")
        assert result.primary == ["write-a-skill"]


# --- Conditional routing tests ---


class TestConditionalRouting:
    """Test conditional routing based on intent and complexity."""

    def test_vague_goal_adds_grill_me_in_plan(self, router: PhaseRouter) -> None:
        intent = _make_intent(is_vague=True)
        result = router.route("plan", intent, "medium")
        assert result.primary == ["grill-me", "prd"]

    def test_high_complexity_adds_tdd_in_code(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("code", intent, "high")
        assert result.primary == ["tdd", "ralph"]

    def test_explore_goal_uses_prototype_in_code(self, router: PhaseRouter) -> None:
        intent = _make_intent(goal_type="explore")
        result = router.route("code", intent, "medium")
        assert result.primary == ["prototype"]

    def test_explore_overrides_high_complexity(self, router: PhaseRouter) -> None:
        """Explore goal type takes precedence over high complexity."""
        intent = _make_intent(goal_type="explore")
        result = router.route("code", intent, "high")
        assert result.primary == ["prototype"]


# --- Auxiliary skills tests ---


class TestAuxiliarySkills:
    """Test composable_with auxiliary skill selection."""

    def test_auxiliary_from_composable_with(self, router: PhaseRouter) -> None:
        """prd's composable_with includes to-issues which is in requirements_phase."""
        intent = _make_intent()
        result = router.route("plan", intent, "medium")
        # prd composable_with: [ralph, to-issues, grill-me]
        # requirements_phase candidates: [prd, to-issues, to-prd]
        # to-issues is in both composable_with and phase candidates
        assert "to-issues" in result.auxiliary

    def test_auxiliary_max_two(self, router: PhaseRouter) -> None:
        """Auxiliary skills should be limited to 2."""
        intent = _make_intent()
        result = router.route("review", intent, "medium")
        assert len(result.auxiliary) <= 2

    def test_auxiliary_not_in_primary(self, router: PhaseRouter) -> None:
        """Auxiliary skills should not duplicate primary skills."""
        intent = _make_intent()
        result = router.route("code", intent, "high")
        # primary is [tdd, ralph]
        for aux in result.auxiliary:
            assert aux not in result.primary

    def test_auxiliary_empty_for_init(self, router: PhaseRouter) -> None:
        """Init node has no primary skills, so no auxiliary either."""
        intent = _make_intent()
        result = router.route("init", intent, "medium")
        assert result.auxiliary == []

    def test_auxiliary_in_phase_candidates(self, router: PhaseRouter) -> None:
        """All auxiliary skills must be in the phase candidate list."""
        intent = _make_intent()
        result = router.route("code", intent, "medium")
        execution_phase_skills = {"ralph", "tdd", "prototype"}
        for aux in result.auxiliary:
            assert aux in execution_phase_skills


# --- Fallback and edge cases ---


class TestFallbackAndEdges:
    """Test fallback behavior for unknown nodes and edge cases."""

    def test_unknown_node_returns_empty(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("nonexistent_node", intent, "medium")
        assert result.primary == []
        assert result.auxiliary == []

    def test_reason_is_populated(self, router: PhaseRouter) -> None:
        intent = _make_intent()
        result = router.route("code", intent, "medium")
        assert result.reason != ""

    def test_skill_selection_defaults(self) -> None:
        selection = SkillSelection()
        assert selection.primary == []
        assert selection.auxiliary == []
        assert selection.reason == ""
