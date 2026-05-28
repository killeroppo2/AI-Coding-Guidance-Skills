"""Tests for robust markdown parsing in OutputContractValidator.

Covers handling of various markdown-formatted AI outputs including:
bold, inline code, blockquotes, lowercase, no-space-after-colon,
code blocks, list items, and semantic inference fallback.
"""

import warnings

import pytest

from kernel.contracts import OutputContractValidator


@pytest.fixture
def validator() -> OutputContractValidator:
    """Create a validator without graph validation."""
    return OutputContractValidator()


class TestTransitionMarkdownBold:
    """Tests for TRANSITION parsing with markdown bold formatting."""

    def test_bold_transition(self, validator: OutputContractValidator) -> None:
        """Test parsing **TRANSITION:** plan_ready."""
        output = "**TRANSITION:** plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_bold_keyword_and_value(self, validator: OutputContractValidator) -> None:
        """Test parsing **TRANSITION: plan_ready**."""
        output = "**TRANSITION: plan_ready**\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestTransitionInlineCode:
    """Tests for TRANSITION parsing with inline code formatting."""

    def test_inline_code_transition(self, validator: OutputContractValidator) -> None:
        """Test parsing `TRANSITION: plan_ready`."""
        output = "`TRANSITION: plan_ready`\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_inline_code_keyword_only(self, validator: OutputContractValidator) -> None:
        """Test parsing `TRANSITION`: plan_ready."""
        output = "`TRANSITION`: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestTransitionBlockquote:
    """Tests for TRANSITION parsing with blockquote formatting."""

    def test_blockquote_transition(self, validator: OutputContractValidator) -> None:
        """Test parsing > TRANSITION: plan_ready."""
        output = "> TRANSITION: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_blockquote_no_space(self, validator: OutputContractValidator) -> None:
        """Test parsing >TRANSITION: plan_ready."""
        output = ">TRANSITION: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestTransitionLowercase:
    """Tests for TRANSITION parsing with lowercase keyword."""

    def test_lowercase_transition(self, validator: OutputContractValidator) -> None:
        """Test parsing transition: plan_ready."""
        output = "transition: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_mixed_case_transition(self, validator: OutputContractValidator) -> None:
        """Test parsing Transition: plan_ready."""
        output = "Transition: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestTransitionNoSpaceAfterColon:
    """Tests for TRANSITION parsing with no space after colon."""

    def test_no_space_after_colon(self, validator: OutputContractValidator) -> None:
        """Test parsing TRANSITION:plan_ready."""
        output = "TRANSITION:plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestTransitionCodeBlock:
    """Tests for TRANSITION parsing inside code blocks."""

    def test_transition_in_code_block(self, validator: OutputContractValidator) -> None:
        """Test parsing TRANSITION inside a ``` code block."""
        output = "Some text\n```\nTRANSITION: plan_ready\nSTATUS: success\n```"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_transition_in_code_block_with_language(self, validator: OutputContractValidator) -> None:
        """Test parsing TRANSITION inside a ```text code block."""
        output = "Output:\n```text\nTRANSITION: plan_ready\nSTATUS: success\n```"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestTransitionListItem:
    """Tests for TRANSITION parsing with list item formatting."""

    def test_dash_list_item(self, validator: OutputContractValidator) -> None:
        """Test parsing - TRANSITION: plan_ready."""
        output = "- TRANSITION: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_asterisk_list_item(self, validator: OutputContractValidator) -> None:
        """Test parsing * TRANSITION: plan_ready."""
        output = "* TRANSITION: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"


class TestSemanticInference:
    """Tests for semantic inference fallback for TRANSITION."""

    def test_infer_tests_pass(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: all tests pass -> tests_pass."""
        output = "All tests pass successfully.\nSTATUS: success"
        result = validator.validate_output(output, "test")
        assert result.transition == "tests_pass"

    def test_infer_tests_passing(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: tests passing -> tests_pass."""
        output = "The tests passing without errors.\nSTATUS: success"
        result = validator.validate_output(output, "test")
        assert result.transition == "tests_pass"

    def test_infer_plan_ready(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: plan is ready -> plan_ready."""
        output = "The plan is ready for implementation.\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_infer_plan_complete(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: plan complete -> plan_ready."""
        output = "The plan complete and approved.\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"

    def test_infer_goal_loaded(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: goal loaded -> goal_loaded."""
        output = "The goal loaded into context.\nSTATUS: success"
        result = validator.validate_output(output, "init")
        assert result.transition == "goal_loaded"

    def test_infer_context_initialized(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: context initialized -> goal_loaded."""
        output = "The context initialized successfully.\nSTATUS: success"
        result = validator.validate_output(output, "init")
        assert result.transition == "goal_loaded"

    def test_infer_code_written(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: code written -> code_written."""
        output = "The code written to disk.\nSTATUS: success"
        result = validator.validate_output(output, "code")
        assert result.transition == "code_written"

    def test_infer_implementation_complete(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: implementation complete -> code_written."""
        output = "The implementation complete.\nSTATUS: success"
        result = validator.validate_output(output, "code")
        assert result.transition == "code_written"

    def test_infer_review_pass(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: review pass -> review_pass."""
        output = "Code review pass with no issues.\nSTATUS: success"
        result = validator.validate_output(output, "review")
        assert result.transition == "review_pass"

    def test_infer_code_quality_acceptable(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: code quality acceptable -> review_pass."""
        output = "The code quality acceptable for merge.\nSTATUS: success"
        result = validator.validate_output(output, "review")
        assert result.transition == "review_pass"

    def test_infer_no_evolution(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: no evolution -> no_evolution_needed."""
        output = "There is no evolution required.\nSTATUS: success"
        result = validator.validate_output(output, "reflect")
        assert result.transition == "no_evolution_needed"

    def test_infer_no_changes_needed(self, validator: OutputContractValidator) -> None:
        """Test semantic inference: no changes needed -> no_evolution_needed."""
        output = "No changes needed at this time.\nSTATUS: success"
        result = validator.validate_output(output, "reflect")
        assert result.transition == "no_evolution_needed"

    def test_semantic_inference_emits_warning(self, validator: OutputContractValidator) -> None:
        """Test that semantic inference emits a WARNING."""
        output = "All tests pass successfully.\nSTATUS: success"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = validator.validate_output(output, "test")
            assert len(w) >= 1
            warning_messages = [str(warning.message) for warning in w]
            assert any("TRANSITION inferred" in msg for msg in warning_messages)
            assert any("tests_pass" in msg for msg in warning_messages)


class TestStatusMarkdownVariants:
    """Tests for STATUS parsing with various markdown formats."""

    def test_bold_status(self, validator: OutputContractValidator) -> None:
        """Test parsing **STATUS:** success."""
        output = "TRANSITION: plan_ready\n**STATUS:** success"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_inline_code_status(self, validator: OutputContractValidator) -> None:
        """Test parsing `STATUS: success`."""
        output = "TRANSITION: plan_ready\n`STATUS: success`"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_blockquote_status(self, validator: OutputContractValidator) -> None:
        """Test parsing > STATUS: success."""
        output = "TRANSITION: plan_ready\n> STATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_lowercase_status(self, validator: OutputContractValidator) -> None:
        """Test parsing status: success."""
        output = "TRANSITION: plan_ready\nstatus: success"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_no_space_after_colon_status(self, validator: OutputContractValidator) -> None:
        """Test parsing STATUS:success."""
        output = "TRANSITION: plan_ready\nSTATUS:success"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_list_item_status(self, validator: OutputContractValidator) -> None:
        """Test parsing - STATUS: success."""
        output = "TRANSITION: plan_ready\n- STATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_status_in_code_block(self, validator: OutputContractValidator) -> None:
        """Test parsing STATUS inside a ``` code block."""
        output = "Some text\n```\nTRANSITION: plan_ready\nSTATUS: success\n```"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"


class TestFilesWrittenMarkdownVariants:
    """Tests for FILES_WRITTEN parsing with various markdown formats."""

    def test_bold_files_written(self, validator: OutputContractValidator) -> None:
        """Test parsing **FILES_WRITTEN:** src/main.py."""
        output = "TRANSITION: code_written\nSTATUS: success\n**FILES_WRITTEN:** src/main.py"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_inline_code_files_written(self, validator: OutputContractValidator) -> None:
        """Test parsing `FILES_WRITTEN: src/main.py`."""
        output = "TRANSITION: code_written\nSTATUS: success\n`FILES_WRITTEN: src/main.py`"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_blockquote_files_written(self, validator: OutputContractValidator) -> None:
        """Test parsing > FILES_WRITTEN: src/main.py."""
        output = "TRANSITION: code_written\nSTATUS: success\n> FILES_WRITTEN: src/main.py"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_lowercase_files_written(self, validator: OutputContractValidator) -> None:
        """Test parsing files_written: src/main.py."""
        output = "TRANSITION: code_written\nSTATUS: success\nfiles_written: src/main.py"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_no_space_after_colon_files_written(self, validator: OutputContractValidator) -> None:
        """Test parsing FILES_WRITTEN:src/main.py."""
        output = "TRANSITION: code_written\nSTATUS: success\nFILES_WRITTEN:src/main.py"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_list_item_files_written(self, validator: OutputContractValidator) -> None:
        """Test parsing - FILES_WRITTEN: src/main.py."""
        output = "TRANSITION: code_written\nSTATUS: success\n- FILES_WRITTEN: src/main.py"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_files_written_in_code_block(self, validator: OutputContractValidator) -> None:
        """Test parsing FILES_WRITTEN inside a ``` code block."""
        output = "Some text\n```\nTRANSITION: code_written\nSTATUS: success\nFILES_WRITTEN: src/main.py\n```"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/main.py"]

    def test_files_written_multiple_bold(self, validator: OutputContractValidator) -> None:
        """Test parsing **FILES_WRITTEN:** with multiple files."""
        output = "TRANSITION: code_written\nSTATUS: success\n**FILES_WRITTEN:** src/a.py, src/b.py"
        result = validator.validate_output(output, "code")
        assert result.files_written == ["src/a.py", "src/b.py"]


class TestErrorMarkdownVariants:
    """Tests for ERROR parsing with various markdown formats."""

    def test_bold_error(self, validator: OutputContractValidator) -> None:
        """Test parsing **ERROR:** Something failed."""
        output = "TRANSITION: code_needs_retry\nSTATUS: failure\n**ERROR:** Something failed"
        result = validator.validate_output(output, "code")
        assert result.errors == ["Something failed"]

    def test_inline_code_error(self, validator: OutputContractValidator) -> None:
        """Test parsing `ERROR: Something failed`."""
        output = "TRANSITION: code_needs_retry\nSTATUS: failure\n`ERROR: Something failed`"
        result = validator.validate_output(output, "code")
        assert result.errors == ["Something failed"]

    def test_blockquote_error(self, validator: OutputContractValidator) -> None:
        """Test parsing > ERROR: Something failed."""
        output = "TRANSITION: code_needs_retry\nSTATUS: failure\n> ERROR: Something failed"
        result = validator.validate_output(output, "code")
        assert result.errors == ["Something failed"]

    def test_lowercase_error(self, validator: OutputContractValidator) -> None:
        """Test parsing error: Something failed."""
        output = "TRANSITION: code_needs_retry\nSTATUS: failure\nerror: Something failed"
        result = validator.validate_output(output, "code")
        assert result.errors == ["Something failed"]


class TestCombinedMarkdownFormats:
    """Tests for output with mixed markdown formatting."""

    def test_all_fields_bold(self, validator: OutputContractValidator) -> None:
        """Test all fields with bold formatting."""
        output = "**TRANSITION:** goal_loaded\n**STATUS:** success\n**FILES_WRITTEN:** src/main.py"
        result = validator.validate_output(output, "init")
        assert result.valid is True
        assert result.transition == "goal_loaded"
        assert result.status == "success"
        assert result.files_written == ["src/main.py"]

    def test_all_fields_in_blockquote(self, validator: OutputContractValidator) -> None:
        """Test all fields with blockquote formatting."""
        output = "> TRANSITION: goal_loaded\n> STATUS: success\n> FILES_WRITTEN: src/main.py"
        result = validator.validate_output(output, "init")
        assert result.valid is True
        assert result.transition == "goal_loaded"
        assert result.status == "success"
        assert result.files_written == ["src/main.py"]

    def test_all_fields_lowercase(self, validator: OutputContractValidator) -> None:
        """Test all fields with lowercase keywords."""
        output = "transition: goal_loaded\nstatus: success\nfiles_written: src/main.py"
        result = validator.validate_output(output, "init")
        assert result.valid is True
        assert result.transition == "goal_loaded"
        assert result.status == "success"
        assert result.files_written == ["src/main.py"]


class TestFalsePositiveRejection:
    """Tests that prose containing keywords does NOT produce false matches."""

    def test_error_in_prose_not_matched(self, validator: OutputContractValidator) -> None:
        """A line like 'An error: the file was not found' should NOT produce an ERROR entry."""
        output = "TRANSITION: code_needs_retry\nSTATUS: failure\nAn error: the file was not found"
        result = validator.validate_output(output, "code")
        assert result.errors == []

    def test_syntax_error_in_prose_not_matched(self, validator: OutputContractValidator) -> None:
        """A line like 'Syntax error: unexpected token' should NOT produce an ERROR entry."""
        output = "TRANSITION: code_needs_retry\nSTATUS: failure\nSyntax error: unexpected token"
        result = validator.validate_output(output, "code")
        assert result.errors == []

    def test_current_status_in_prose_not_matched(self, validator: OutputContractValidator) -> None:
        """A line like 'Current status: processing' should NOT match as STATUS."""
        output = "TRANSITION: plan_ready\nSTATUS: success\nCurrent status: processing"
        result = validator.validate_output(output, "plan")
        assert result.status == "success"

    def test_transition_in_prose_not_matched(self, validator: OutputContractValidator) -> None:
        """A line like 'Check the transition: it should work' should NOT match as TRANSITION."""
        output = "Check the transition: it should work\nTRANSITION: plan_ready\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.transition == "plan_ready"
