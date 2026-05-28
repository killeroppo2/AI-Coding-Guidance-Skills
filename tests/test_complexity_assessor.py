"""Tests for kernel.complexity_assessor module."""


from kernel.complexity_assessor import assess_complexity


class TestAssessComplexityLow:
    """Tests for low complexity detection."""

    def test_hello_world(self) -> None:
        """Test that 'hello world' goal is assessed as low."""
        assert assess_complexity("hello world") == "low"

    def test_fix_bug(self) -> None:
        """Test that 'fix bug' goal is assessed as low."""
        assert assess_complexity("fix bug") == "low"

    def test_simple_keyword(self) -> None:
        """Test that 'simple' keyword triggers low."""
        assert assess_complexity("a simple task to do") == "low"

    def test_config_keyword(self) -> None:
        """Test that 'config' keyword triggers low."""
        assert assess_complexity("update config values") == "low"

    def test_repair_keyword(self) -> None:
        """Test that 'repair' keyword triggers low."""
        assert assess_complexity("repair the broken link") == "low"

    def test_single_file_keyword(self) -> None:
        """Test that 'single file' keyword triggers low."""
        assert assess_complexity("create a single file utility") == "low"

    def test_chinese_simple(self) -> None:
        """Test Chinese keyword for simple."""
        assert assess_complexity("\u7b80\u5355\u914d\u7f6e") == "low"

    def test_chinese_fix(self) -> None:
        """Test Chinese keyword for fix."""
        assert assess_complexity("\u4fee\u590d\u4e00\u4e2a\u95ee\u9898") == "low"

    def test_chinese_config(self) -> None:
        """Test Chinese keyword for config."""
        assert assess_complexity("\u914d\u7f6e\u6587\u4ef6\u66f4\u65b0") == "low"

    def test_chinese_single_file(self) -> None:
        """Test Chinese keyword for single file."""
        assert assess_complexity("\u5355\u6587\u4ef6\u811a\u672c") == "low"

    def test_short_goal_len_under_20(self) -> None:
        """Test that very short goals (< 20 chars) are low."""
        assert assess_complexity("x") == "low"

    def test_exactly_19_chars_no_keywords(self) -> None:
        """Test that a 19-char goal with no keywords is low."""
        goal = "a" * 19
        assert assess_complexity(goal) == "low"

    def test_case_insensitive(self) -> None:
        """Test that keyword matching is case-insensitive."""
        assert assess_complexity("HELLO WORLD app") == "low"
        assert assess_complexity("Fix Something") == "low"


class TestAssessComplexityHigh:
    """Tests for high complexity detection."""

    def test_distributed_microservice(self) -> None:
        """Test that distributed microservice goal is high."""
        assert assess_complexity(
            "Build a distributed microservice architecture"
        ) == "high"

    def test_architecture_keyword(self) -> None:
        """Test that 'architecture' keyword triggers high."""
        assert assess_complexity("Design the system architecture") == "high"

    def test_system_keyword(self) -> None:
        """Test that 'system' keyword triggers high."""
        assert assess_complexity("Build a monitoring system for prod") == "high"

    def test_multi_module_keyword(self) -> None:
        """Test that 'multi-module' keyword triggers high."""
        assert assess_complexity("Create a multi-module project setup") == "high"

    def test_microservice_keyword(self) -> None:
        """Test that 'microservice' keyword triggers high."""
        assert assess_complexity("Deploy a microservice backend") == "high"

    def test_refactor_entire_keyword(self) -> None:
        """Test that 'refactor entire' keyword triggers high."""
        assert assess_complexity("refactor entire codebase to new pattern") == "high"

    def test_chinese_architecture(self) -> None:
        """Test Chinese keyword for architecture."""
        assert assess_complexity("\u91cd\u6784\u6574\u4e2a\u7cfb\u7edf\u67b6\u6784") == "high"

    def test_chinese_system(self) -> None:
        """Test Chinese keyword for system."""
        assert assess_complexity("\u7cfb\u7edf\u8bbe\u8ba1\u65b9\u6848") == "high"

    def test_chinese_multi_module(self) -> None:
        """Test Chinese keyword for multi-module."""
        assert assess_complexity("\u591a\u6a21\u5757\u5f00\u53d1") == "high"

    def test_chinese_refactor_entire(self) -> None:
        """Test Chinese keyword for refactor entire."""
        assert assess_complexity("\u91cd\u6784\u6574\u4e2a\u4ee3\u7801\u5e93") == "high"

    def test_long_goal_over_100_no_keywords(self) -> None:
        """Test that goals over 100 chars with no keywords are high."""
        goal = "A" * 101
        assert assess_complexity(goal) == "high"

    def test_case_insensitive_high(self) -> None:
        """Test that high keyword matching is case-insensitive."""
        assert assess_complexity("DISTRIBUTED service") == "high"
        assert assess_complexity("ARCHITECTURE plan") == "high"


class TestAssessComplexityMedium:
    """Tests for medium complexity detection."""

    def test_add_login_page(self) -> None:
        """Test that a normal task is medium."""
        assert assess_complexity("Add a user login page now") == "medium"

    def test_implement_search(self) -> None:
        """Test that normal feature work is medium."""
        assert assess_complexity("Implement search feature for products") == "medium"

    def test_between_20_and_100_chars_no_keywords(self) -> None:
        """Test that goals between 20-100 chars with no keywords are medium."""
        goal = "B" * 50
        assert assess_complexity(goal) == "medium"

    def test_exactly_20_chars_no_keywords(self) -> None:
        """Test that a 20-char goal with no keywords is medium."""
        goal = "a" * 20
        assert assess_complexity(goal) == "medium"

    def test_exactly_100_chars_no_keywords(self) -> None:
        """Test that a 100-char goal with no keywords is medium."""
        goal = "C" * 100
        assert assess_complexity(goal) == "medium"


class TestAssessComplexityPriority:
    """Tests for priority when both low and high keywords match."""

    def test_high_priority_over_low(self) -> None:
        """Test that high keywords take priority when both match."""
        assert assess_complexity("hello world distributed system") == "high"

    def test_fix_the_architecture(self) -> None:
        """Test that 'fix' (low) + 'architecture' (high) resolves to high."""
        assert assess_complexity("fix the architecture design") == "high"

    def test_simple_distributed_system(self) -> None:
        """Test that 'simple' (low) + 'distributed' (high) resolves to high."""
        assert assess_complexity("simple distributed system setup") == "high"


class TestAssessComplexityEdgeCases:
    """Edge case tests."""

    def test_empty_string(self) -> None:
        """Test empty string goal (len < 20)."""
        assert assess_complexity("") == "low"

    def test_whitespace_only(self) -> None:
        """Test whitespace-only goal (strip makes it < 20)."""
        assert assess_complexity("   ") == "low"

    def test_keyword_as_substring(self) -> None:
        """Test that keywords match as substrings."""
        # 'fix' appears in 'prefix' - this is expected behavior per spec
        assert assess_complexity("prefix some text with data") == "low"

    def test_system_in_longer_word(self) -> None:
        """Test that 'system' matches in 'filesystem'."""
        assert assess_complexity("implement a filesystem watcher") == "high"
