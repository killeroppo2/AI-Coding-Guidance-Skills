"""Tests for OutputContractValidator output format enforcement.

Validates that the contract validator correctly identifies valid outputs,
missing fields, invalid transitions, and multiple violations.
"""

from pathlib import Path

import pytest
import yaml

from kernel.contracts import ContractResult, OutputContractValidator


@pytest.fixture
def contract_graph(tmp_path: Path) -> Path:
    """Create a temporary graph.yaml for contract validation tests.

    Returns:
        Path to the temporary graph.yaml file.
    """
    graph_data = {
        "version": "1.0",
        "description": "Contract validation test graph",
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Initialize",
                "transitions": [{"to": "plan", "condition": "goal_loaded"}],
            },
            {
                "id": "plan",
                "prompt_file": "prompts/planner.md",
                "description": "Plan",
                "transitions": [
                    {"to": "code", "condition": "plan_ready"},
                    {"to": "plan", "condition": "plan_needs_revision"},
                ],
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Code",
                "transitions": [
                    {"to": "test", "condition": "code_written"},
                    {"to": "code", "condition": "code_needs_retry"},
                ],
            },
            {
                "id": "test",
                "prompt_file": "prompts/tester.md",
                "description": "Test",
                "transitions": [
                    {"to": "review", "condition": "tests_pass"},
                    {"to": "code", "condition": "tests_fail"},
                ],
            },
            {
                "id": "review",
                "prompt_file": "prompts/reviewer.md",
                "description": "Review",
                "transitions": [
                    {"to": "reflect", "condition": "review_pass"},
                    {"to": "code", "condition": "review_needs_changes"},
                ],
            },
            {
                "id": "reflect",
                "prompt_file": "prompts/reflector.md",
                "description": "Reflect",
                "transitions": [
                    {"to": "evolve", "condition": "evolution_proposed"},
                    {"to": "plan", "condition": "no_evolution_needed"},
                ],
            },
        ],
        "default_start": "init",
        "max_iterations": 30,
    }
    graph_file = tmp_path / "graph.yaml"
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)
    return graph_file


class TestValidOutputForEachNode:
    """Tests that valid output for each node passes validation."""

    @pytest.mark.parametrize(
        "node_id,transition",
        [
            ("init", "goal_loaded"),
            ("plan", "plan_ready"),
            ("plan", "plan_needs_revision"),
            ("code", "code_written"),
            ("code", "code_needs_retry"),
            ("test", "tests_pass"),
            ("test", "tests_fail"),
            ("review", "review_pass"),
            ("review", "review_needs_changes"),
            ("reflect", "evolution_proposed"),
            ("reflect", "no_evolution_needed"),
        ],
    )
    def test_valid_output_passes(
        self, contract_graph: Path, node_id: str, transition: str
    ) -> None:
        """Test that a valid TRANSITION + STATUS output passes for each node."""
        validator = OutputContractValidator(contract_graph)
        output = f"TRANSITION: {transition}\nSTATUS: success"
        result = validator.validate_output(output, node_id)
        assert result.valid is True
        assert result.transition == transition
        assert result.status == "success"
        assert result.violations == []


class TestMissingTransitionIsViolation:
    """Tests that missing TRANSITION line is detected as a violation."""

    def test_missing_transition_is_violation(self, contract_graph: Path) -> None:
        """Test that output without TRANSITION line fails validation."""
        validator = OutputContractValidator(contract_graph)
        output = "STATUS: success\nSome other content here"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert result.transition is None
        assert any("Missing required TRANSITION" in v for v in result.violations)

    def test_empty_output_has_violations(self, contract_graph: Path) -> None:
        """Test that empty output fails with multiple violations."""
        validator = OutputContractValidator(contract_graph)
        result = validator.validate_output("", "init")
        assert result.valid is False
        assert any("Missing required TRANSITION" in v for v in result.violations)
        assert any("Missing required STATUS" in v for v in result.violations)


class TestInvalidTransitionForNode:
    """Tests that wrong TRANSITION value for a specific node is flagged."""

    def test_invalid_transition_for_node(self, contract_graph: Path) -> None:
        """Test that a wrong transition condition for a node is flagged."""
        validator = OutputContractValidator(contract_graph)
        # "tests_pass" is valid for test node, not for init node
        output = "TRANSITION: tests_pass\nSTATUS: success"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert any("Invalid TRANSITION" in v for v in result.violations)
        assert any("init" in v for v in result.violations)

    def test_invalid_transition_shows_valid_options(self, contract_graph: Path) -> None:
        """Test that the violation message includes the valid transitions."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: wrong_value\nSTATUS: success"
        result = validator.validate_output(output, "plan")
        assert result.valid is False
        violation_text = " ".join(result.violations)
        assert "plan_ready" in violation_text
        assert "plan_needs_revision" in violation_text


class TestFilesWrittenParsing:
    """Tests for FILES_WRITTEN line parsing."""

    def test_files_written_single_file(self, contract_graph: Path) -> None:
        """Test parsing a single FILES_WRITTEN entry."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: code_written\nSTATUS: success\nFILES_WRITTEN: src/main.py"
        result = validator.validate_output(output, "code")
        assert result.valid is True
        assert result.files_written == ["src/main.py"]

    def test_files_written_multiple_files(self, contract_graph: Path) -> None:
        """Test parsing multiple comma-separated FILES_WRITTEN entries."""
        validator = OutputContractValidator(contract_graph)
        output = (
            "TRANSITION: code_written\nSTATUS: success\n"
            "FILES_WRITTEN: src/main.py, src/utils.py, tests/test_main.py"
        )
        result = validator.validate_output(output, "code")
        assert result.valid is True
        assert result.files_written == ["src/main.py", "src/utils.py", "tests/test_main.py"]

    def test_files_written_multiple_lines(self, contract_graph: Path) -> None:
        """Test parsing multiple FILES_WRITTEN lines."""
        validator = OutputContractValidator(contract_graph)
        output = (
            "TRANSITION: code_written\nSTATUS: success\n"
            "FILES_WRITTEN: src/main.py\n"
            "FILES_WRITTEN: src/utils.py"
        )
        result = validator.validate_output(output, "code")
        assert result.valid is True
        assert "src/main.py" in result.files_written
        assert "src/utils.py" in result.files_written

    def test_no_files_written(self, contract_graph: Path) -> None:
        """Test that output without FILES_WRITTEN has empty list."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: goal_loaded\nSTATUS: success"
        result = validator.validate_output(output, "init")
        assert result.files_written == []


class TestErrorLineParsing:
    """Tests for ERROR line parsing."""

    def test_error_line_captured(self, contract_graph: Path) -> None:
        """Test that ERROR: lines are captured in the result."""
        validator = OutputContractValidator(contract_graph)
        output = (
            "TRANSITION: code_needs_retry\nSTATUS: failure\n"
            "ERROR: Compilation failed - missing module"
        )
        result = validator.validate_output(output, "code")
        assert result.valid is True
        assert len(result.errors) == 1
        assert "Compilation failed" in result.errors[0]

    def test_multiple_error_lines(self, contract_graph: Path) -> None:
        """Test that multiple ERROR: lines are all captured."""
        validator = OutputContractValidator(contract_graph)
        output = (
            "TRANSITION: code_needs_retry\nSTATUS: failure\n"
            "ERROR: First error\n"
            "ERROR: Second error\n"
            "ERROR: Third error"
        )
        result = validator.validate_output(output, "code")
        assert len(result.errors) == 3
        assert result.errors[0] == "First error"
        assert result.errors[1] == "Second error"
        assert result.errors[2] == "Third error"


class TestStatusLineParsing:
    """Tests for STATUS line parsing."""

    def test_status_success(self, contract_graph: Path) -> None:
        """Test that STATUS: success is parsed correctly."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: goal_loaded\nSTATUS: success"
        result = validator.validate_output(output, "init")
        assert result.status == "success"
        assert result.valid is True

    def test_status_failure(self, contract_graph: Path) -> None:
        """Test that STATUS: failure is parsed correctly."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: code_needs_retry\nSTATUS: failure"
        result = validator.validate_output(output, "code")
        assert result.status == "failure"
        assert result.valid is True

    def test_invalid_status_value(self, contract_graph: Path) -> None:
        """Test that an invalid STATUS value is flagged."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: goal_loaded\nSTATUS: maybe"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert any("Invalid STATUS" in v for v in result.violations)

    def test_missing_status(self, contract_graph: Path) -> None:
        """Test that missing STATUS line is flagged."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: goal_loaded"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert any("Missing required STATUS" in v for v in result.violations)


class TestMultipleViolationsReported:
    """Tests that multiple problems are all reported."""

    def test_multiple_violations_reported(self, contract_graph: Path) -> None:
        """Test that output with multiple problems reports all violations."""
        validator = OutputContractValidator(contract_graph)
        # No TRANSITION, no STATUS - two violations
        output = "Some random output with no required fields"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert len(result.violations) >= 2
        violation_text = " ".join(result.violations)
        assert "TRANSITION" in violation_text
        assert "STATUS" in violation_text

    def test_invalid_transition_and_invalid_status(self, contract_graph: Path) -> None:
        """Test that both invalid TRANSITION and invalid STATUS are reported."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: completely_wrong\nSTATUS: invalid_value"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert len(result.violations) == 2
        violation_text = " ".join(result.violations)
        assert "Invalid TRANSITION" in violation_text
        assert "Invalid STATUS" in violation_text


class TestUnknownNodeValidation:
    """Tests for validating output against an unknown node."""

    def test_unknown_node_accepts_any_transition(self, contract_graph: Path) -> None:
        """Test that validating against an unknown node just checks TRANSITION exists."""
        validator = OutputContractValidator(contract_graph)
        output = "TRANSITION: anything_goes\nSTATUS: success"
        result = validator.validate_output(output, "nonexistent_node")
        # Unknown node has no valid_transitions constraint, so any TRANSITION is ok
        assert result.valid is True
        assert result.transition == "anything_goes"

    def test_unknown_node_still_requires_transition(self, contract_graph: Path) -> None:
        """Test that unknown node still requires TRANSITION line to be present."""
        validator = OutputContractValidator(contract_graph)
        output = "STATUS: success"
        result = validator.validate_output(output, "nonexistent_node")
        assert result.valid is False
        assert any("Missing required TRANSITION" in v for v in result.violations)


class TestValidatorWithoutGraph:
    """Tests for validator initialized without a graph path."""

    def test_validator_without_graph_skips_transition_validation(self) -> None:
        """Test that validator without graph accepts any transition value."""
        validator = OutputContractValidator(None)
        output = "TRANSITION: anything\nSTATUS: success"
        result = validator.validate_output(output, "init")
        assert result.valid is True

    def test_validator_without_graph_still_checks_required_fields(self) -> None:
        """Test that validator without graph still checks for required fields."""
        validator = OutputContractValidator(None)
        result = validator.validate_output("", "init")
        assert result.valid is False
        assert len(result.violations) >= 2
