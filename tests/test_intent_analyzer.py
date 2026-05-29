"""Tests for kernel/intent_analyzer.py - IntentAnalyzer and IntentResult."""

import pytest

from kernel.intent_analyzer import IntentAnalyzer, IntentResult


@pytest.fixture
def analyzer() -> IntentAnalyzer:
    """Return an IntentAnalyzer instance."""
    return IntentAnalyzer()


# --- goal_type detection ---


class TestGoalTypeDetection:
    """Test goal_type detection for all verb categories."""

    def test_build_verb_create(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a REST API for user management")
        assert result.goal_type == "build"

    def test_build_verb_make(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("make a CLI tool for deployment")
        assert result.goal_type == "build"

    def test_build_verb_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u642d\u5efa\u4e00\u4e2a\u7f51\u7ad9")
        assert result.goal_type == "build"

    def test_fix_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("fix the login bug in authentication module")
        assert result.goal_type == "fix"

    def test_fix_verb_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u4fee\u590d\u767b\u5f55\u62a5\u9519\u95ee\u9898")
        assert result.goal_type == "fix"

    def test_optimize_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("optimize database query performance")
        assert result.goal_type == "optimize"

    def test_optimize_verb_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u4f18\u5316\u7cfb\u7edf\u6027\u80fd")
        assert result.goal_type == "optimize"

    def test_audit_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("review the security of the auth module")
        assert result.goal_type == "audit"

    def test_audit_verb_check(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("check code quality and standards compliance")
        assert result.goal_type == "audit"

    def test_audit_verb_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u68c0\u67e5\u4ee3\u7801\u8d28\u91cf")
        assert result.goal_type == "audit"

    def test_explore_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("explore using GraphQL for the data layer")
        assert result.goal_type == "explore"

    def test_explore_verb_prototype(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("prototype a new dashboard layout")
        assert result.goal_type == "explore"

    def test_explore_verb_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u8bd5\u8bd5\u7528React\u505a\u524d\u7aef")
        assert result.goal_type == "explore"

    def test_document_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("document the API endpoints and usage")
        assert result.goal_type == "document"

    def test_document_verb_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u5199\u6587\u6863\u8bb0\u5f55\u9879\u76ee\u67b6\u6784")
        assert result.goal_type == "document"

    def test_default_goal_type(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("a shopping cart with payments and inventory")
        assert result.goal_type == "build"


# --- output_form detection ---


class TestOutputFormDetection:
    """Test output_form detection for all noun categories."""

    def test_api_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a REST API for user authentication")
        assert result.output_form == "api"

    def test_graphql_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a graphql endpoint for products")
        assert result.output_form == "api"

    def test_cli_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a CLI tool for file management")
        assert result.output_form == "cli"

    def test_app_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a web app for project tracking")
        assert result.output_form == "app"

    def test_app_form_chinese(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u642d\u5efa\u4e00\u4e2a\u7f51\u7ad9\u8fdb\u884c\u5c55\u793a")
        assert result.output_form == "app"

    def test_library_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a package for date utilities")
        assert result.output_form == "library"

    def test_script_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("write a script to clean up old logs")
        assert result.output_form == "script"

    def test_unknown_form(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("improve the system overall")
        assert result.output_form == "unknown"


# --- tech_hints detection ---


class TestTechHintsDetection:
    """Test technology hint extraction."""

    def test_python_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a python flask API")
        assert "python" in result.tech_hints

    def test_react_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a react dashboard app")
        assert "react" in result.tech_hints

    def test_go_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a golang microservice")
        assert "go" in result.tech_hints

    def test_rust_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a rust CLI tool")
        assert "rust" in result.tech_hints

    def test_node_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build an express API with node")
        assert "node" in result.tech_hints

    def test_java_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create a spring boot application")
        assert "java" in result.tech_hints

    def test_typescript_detected(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a typescript library for validation")
        assert "typescript" in result.tech_hints

    def test_multiple_techs(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a python API with react frontend")
        assert "python" in result.tech_hints
        assert "react" in result.tech_hints

    def test_no_tech_hints(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build something cool")
        assert result.tech_hints == []


# --- language detection ---


class TestLanguageDetection:
    """Test language detection (en, zh, mixed)."""

    def test_english_only(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("build a REST API")
        assert result.language == "en"

    def test_chinese_only(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u642d\u5efa\u4e00\u4e2a\u7f51\u7ad9")
        assert result.language == "zh"

    def test_mixed_language(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("\u7528React\u642d\u5efa\u4e00\u4e2a\u524d\u7aef")
        assert result.language == "mixed"


# --- is_vague detection ---


class TestIsVagueDetection:
    """Test vagueness detection."""

    def test_vague_short_no_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("something nice")
        assert result.is_vague is True

    def test_not_vague_short_with_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("fix login")
        assert result.is_vague is False

    def test_not_vague_long_sentence(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze(
            "I need a system that can handle multiple users and process payments"
        )
        assert result.is_vague is False

    def test_vague_single_word(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("help")
        assert result.is_vague is True

    def test_not_vague_with_build_verb(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("create app")
        assert result.is_vague is False


# --- edge cases ---


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("")
        assert result.goal_type == "build"
        assert result.is_vague is True
        assert result.tech_hints == []

    def test_very_long_goal(self, analyzer: IntentAnalyzer) -> None:
        long_goal = "build " + "a very detailed system " * 100 + "with python and react"
        result = analyzer.analyze(long_goal)
        assert result.goal_type == "build"
        assert "python" in result.tech_hints
        assert "react" in result.tech_hints

    def test_only_stop_words(self, analyzer: IntentAnalyzer) -> None:
        result = analyzer.analyze("the and or but")
        assert result.is_vague is True
        assert result.goal_type == "build"

    def test_intent_result_defaults(self) -> None:
        result = IntentResult()
        assert result.goal_type == "build"
        assert result.output_form == "unknown"
        assert result.tech_hints == []
        assert result.language == "en"
        assert result.is_vague is False
