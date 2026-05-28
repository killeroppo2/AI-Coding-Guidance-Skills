"""Tests for kernel/error_messages.py."""

from kernel.error_messages import ERROR_MESSAGES, classify_error, format_error


class TestErrorMessages:
    """Tests for the ERROR_MESSAGES dictionary structure."""

    def test_error_messages_has_at_least_5_entries(self):
        assert len(ERROR_MESSAGES) >= 5

    def test_all_entries_have_what_why_fix(self):
        for key, template in ERROR_MESSAGES.items():
            assert "what" in template, f"{key} missing 'what'"
            assert "why" in template, f"{key} missing 'why'"
            assert "fix" in template, f"{key} missing 'fix'"


class TestFormatError:
    """Tests for format_error function."""

    def test_format_stuck_node(self):
        result = format_error("stuck_node", node="code", visits=6, max_retries=5)
        assert "What happened:" in result
        assert "code" in result
        assert "6" in result
        assert "5" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_command_not_found(self):
        result = format_error("command_not_found", cmd="claude")
        assert "claude" in result
        assert "What happened:" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_timeout(self):
        result = format_error("timeout", seconds="300", node="code")
        assert "300" in result
        assert "code" in result
        assert "What happened:" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_skill_not_found(self):
        result = format_error("skill_not_found", name="my-skill")
        assert "my-skill" in result
        assert "What happened:" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_contract_violation(self):
        result = format_error("contract_violation", node="plan")
        assert "plan" in result
        assert "What happened:" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_state_corrupted(self):
        result = format_error("state_corrupted")
        assert "What happened:" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_unknown_error_type_returns_generic_fallback(self):
        result = format_error("totally_unknown_error")
        assert "What happened:" in result
        assert "totally_unknown_error" in result
        assert "Why it matters:" in result
        assert "What to do:" in result

    def test_format_unknown_with_detail_kwarg(self):
        result = format_error("nonexistent", detail="something broke")
        assert "something broke" in result

    def test_format_error_with_missing_kwargs_uses_raw_template(self):
        # stuck_node expects node, visits, max_retries - provide none
        result = format_error("stuck_node")
        assert "What happened:" in result
        assert "Why it matters:" in result
        assert "What to do:" in result
        # Should use the raw template strings
        assert "{node}" in result or "node" in result

    def test_format_error_multiline_structure(self):
        result = format_error("command_not_found", cmd="test-cmd")
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert lines[0].strip().startswith("What happened:")
        assert lines[1].strip().startswith("Why it matters:")
        assert lines[2].strip().startswith("What to do:")


class TestClassifyError:
    """Tests for classify_error function."""

    def test_classify_command_not_found(self):
        error_type, kwargs = classify_error("Command not found: claude")
        assert error_type == "command_not_found"
        assert kwargs["cmd"] == "claude"

    def test_classify_timeout(self):
        error_type, kwargs = classify_error("Timeout after 300s on node code")
        assert error_type == "timeout"
        assert kwargs["seconds"] == "300"
        assert kwargs["node"] == "code"

    def test_classify_stuck_node(self):
        error_type, kwargs = classify_error(
            "Node 'code' exceeded max_retries (visited 6 times, max 5)"
        )
        assert error_type == "stuck_node"
        assert kwargs["node"] == "code"
        assert kwargs["visits"] == "6"
        assert kwargs["max_retries"] == "5"

    def test_classify_contract_violation(self):
        error_type, kwargs = classify_error(
            "Contract violation on node plan: missing TRANSITION"
        )
        assert error_type == "contract_violation"
        assert kwargs["node"] == "unknown"

    def test_classify_skill_not_found(self):
        error_type, kwargs = classify_error("Skill not found: my-skill")
        assert error_type == "skill_not_found"
        assert kwargs["name"] == "my-skill"

    def test_classify_unknown_error(self):
        error_type, kwargs = classify_error("Something completely unexpected happened")
        assert error_type == "unknown"
        assert kwargs["detail"] == "Something completely unexpected happened"
