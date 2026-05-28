"""Tests for kernel/contracts - output format contract validation.

Covers ContractResult dataclass, OutputContractValidator initialization,
basic parsing, robust markdown parsing variants, and output format enforcement.
"""

import warnings
from pathlib import Path

import pytest
import yaml

from kernel.contracts import ContractResult, OutputContractValidator


class TestContractResult:
    """Tests for the ContractResult dataclass."""

    def test_contract_result_defaults(self) -> None:
        """Test ContractResult with default field values."""
        result = ContractResult(valid=True)
        assert result.valid is True
        assert result.transition is None
        assert result.files_written == []
        assert result.errors == []
        assert result.status == ""
        assert result.violations == []

    def test_contract_result_full(self) -> None:
        """Test ContractResult with all fields populated."""
        result = ContractResult(
            valid=False,
            transition="plan_ready",
            files_written=["a.py", "b.py"],
            errors=["something broke"],
            status="failure",
            violations=["Missing STATUS line"],
        )
        assert result.valid is False
        assert result.transition == "plan_ready"
        assert result.files_written == ["a.py", "b.py"]
        assert result.errors == ["something broke"]
        assert result.status == "failure"
        assert result.violations == ["Missing STATUS line"]


class TestOutputContractValidatorInit:
    """Tests for OutputContractValidator initialization."""

    def test_init_without_graph(self) -> None:
        """Test validator can be created without a graph path."""
        validator = OutputContractValidator()
        assert validator._valid_transitions == {}

    def test_init_with_graph(self, tmp_path: Path) -> None:
        """Test validator loads transitions from graph.yaml."""
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                },
                {
                    "id": "plan",
                    "transitions": [
                        {"to": "code", "condition": "plan_ready"},
                        {"to": "plan", "condition": "plan_needs_revision"},
                    ],
                },
            ]
        }
        graph_file = tmp_path / "graph.yaml"
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        validator = OutputContractValidator(str(graph_file))
        assert validator._valid_transitions["init"] == ["goal_loaded"]
        assert validator._valid_transitions["plan"] == ["plan_ready", "plan_needs_revision"]

    def test_init_with_missing_graph(self, tmp_path: Path) -> None:
        """Test validator handles missing graph file gracefully."""
        validator = OutputContractValidator(str(tmp_path / "nonexistent.yaml"))
        assert validator._valid_transitions == {}


class TestValidateOutputBasicParsing:
    """Tests for parsing TRANSITION, STATUS, FILES_WRITTEN, ERROR lines."""

    @pytest.fixture
    def validator(self) -> OutputContractValidator:
        """Create a validator without graph validation."""
        return OutputContractValidator()

    def test_valid_output_success(self, validator: OutputContractValidator) -> None:
        """Test a fully valid output parses correctly."""
        output = (
            "I completed the task.\n"
            "FILES_WRITTEN: src/main.py, tests/test_main.py\n"
            "STATUS: success\n"
            "TRANSITION: plan_ready\n"
        )
        result = validator.validate_output(output, "plan")
        assert result.valid is True
        assert result.transition == "plan_ready"
        assert result.status == "success"
        assert result.files_written == ["src/main.py", "tests/test_main.py"]
        assert result.errors == []
        assert result.violations == []

    def test_valid_output_failure(self, validator: OutputContractValidator) -> None:
        """Test a valid failure output parses correctly."""
        output = (
            "Something went wrong.\n"
            "ERROR: Could not compile module\n"
            "STATUS: failure\n"
            "TRANSITION: code_needs_retry\n"
        )
        result = validator.validate_output(output, "code")
        assert result.valid is True
        assert result.transition == "code_needs_retry"
        assert result.status == "failure"
        assert result.errors == ["Could not compile module"]

    def test_missing_transition_is_violation(self, validator: OutputContractValidator) -> None:
        """Test that missing TRANSITION line is reported as violation."""
        output = "STATUS: success\n"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert result.transition is None
        assert "Missing required TRANSITION line" in result.violations

    def test_missing_status_is_violation(self, validator: OutputContractValidator) -> None:
        """Test that missing STATUS line is reported as violation."""
        output = "TRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert "Missing required STATUS line" in result.violations

    def test_invalid_status_value(self, validator: OutputContractValidator) -> None:
        """Test that invalid STATUS value is reported as violation."""
        output = "STATUS: maybe\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert any("Invalid STATUS" in v for v in result.violations)

    def test_empty_output(self, validator: OutputContractValidator) -> None:
        """Test that empty output has both violations."""
        result = validator.validate_output("", "init")
        assert result.valid is False
        assert len(result.violations) == 2
        assert "Missing required TRANSITION line" in result.violations
        assert "Missing required STATUS line" in result.violations


class TestFilesWrittenParsing:
    """Tests for FILES_WRITTEN line parsing."""

    @pytest.fixture
    def validator(self) -> OutputContractValidator:
        """Create a validator without graph validation."""
        return OutputContractValidator()

    def test_single_file(self, validator: OutputContractValidator) -> None:
        """Test parsing a single file in FILES_WRITTEN."""
        output = "FILES_WRITTEN: src/main.py\nSTATUS: success\nTRANSITION: plan_ready\n"
        result = validator.validate_output(output, "plan")
        assert result.files_written == ["src/main.py"]

    def test_multiple_files(self, validator: OutputContractValidator) -> None:
        """Test parsing multiple files in FILES_WRITTEN."""
        output = "FILES_WRITTEN: a.py, b.py, c.py\nSTATUS: success\nTRANSITION: plan_ready\n"
        result = validator.validate_output(output, "plan")
        assert result.files_written == ["a.py", "b.py", "c.py"]

    def test_no_files_written(self, validator: OutputContractValidator) -> None:
        """Test output with no FILES_WRITTEN line."""
        output = "STATUS: success\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.files_written == []

    def test_files_written_with_spaces(self, validator: OutputContractValidator) -> None:
        """Test FILES_WRITTEN with extra spaces around paths."""
        output = "FILES_WRITTEN:  a.py ,  b.py \nSTATUS: success\nTRANSITION: plan_ready\n"
        result = validator.validate_output(output, "plan")
        assert result.files_written == ["a.py", "b.py"]

    def test_empty_files_written(self, validator: OutputContractValidator) -> None:
        """Test FILES_WRITTEN with empty value."""
        output = "FILES_WRITTEN:\nSTATUS: success\nTRANSITION: plan_ready\n"
        result = validator.validate_output(output, "plan")
        assert result.files_written == []


class TestErrorParsing:
    """Tests for ERROR line parsing."""

    @pytest.fixture
    def validator(self) -> OutputContractValidator:
        """Create a validator without graph validation."""
        return OutputContractValidator()

    def test_single_error(self, validator: OutputContractValidator) -> None:
        """Test parsing a single ERROR line."""
        output = "ERROR: Something failed\nSTATUS: failure\nTRANSITION: tests_fail\n"
        result = validator.validate_output(output, "test")
        assert result.errors == ["Something failed"]

    def test_multiple_errors(self, validator: OutputContractValidator) -> None:
        """Test parsing multiple ERROR lines."""
        output = (
            "ERROR: First error\n"
            "ERROR: Second error\n"
            "ERROR: Third error\n"
            "STATUS: failure\n"
            "TRANSITION: tests_fail\n"
        )
        result = validator.validate_output(output, "test")
        assert result.errors == ["First error", "Second error", "Third error"]

    def test_no_errors(self, validator: OutputContractValidator) -> None:
        """Test output with no ERROR lines."""
        output = "STATUS: success\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.errors == []

    def test_empty_error_line(self, validator: OutputContractValidator) -> None:
        """Test ERROR line with empty message is ignored."""
        output = "ERROR:\nSTATUS: success\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.errors == []


class TestTransitionValidation:
    """Tests for node-specific transition validation."""

    @pytest.fixture
    def validator(self, tmp_path: Path) -> OutputContractValidator:
        """Create a validator with graph transitions loaded."""
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                },
                {
                    "id": "plan",
                    "transitions": [
                        {"to": "code", "condition": "plan_ready"},
                        {"to": "plan", "condition": "plan_needs_revision"},
                    ],
                },
                {
                    "id": "code",
                    "transitions": [
                        {"to": "test", "condition": "code_written"},
                        {"to": "code", "condition": "code_needs_retry"},
                    ],
                },
                {
                    "id": "test",
                    "transitions": [
                        {"to": "review", "condition": "tests_pass"},
                        {"to": "code", "condition": "tests_fail"},
                    ],
                },
                {
                    "id": "review",
                    "transitions": [
                        {"to": "reflect", "condition": "review_pass"},
                        {"to": "code", "condition": "review_needs_changes"},
                    ],
                },
                {
                    "id": "reflect",
                    "transitions": [
                        {"to": "evolve", "condition": "evolution_proposed"},
                        {"to": "plan", "condition": "no_evolution_needed"},
                    ],
                },
            ]
        }
        graph_file = tmp_path / "graph.yaml"
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)
        return OutputContractValidator(str(graph_file))

    def test_valid_transition_for_init(self, validator: OutputContractValidator) -> None:
        """Test valid transition for init node."""
        output = "STATUS: success\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.valid is True
        assert result.transition == "goal_loaded"

    def test_invalid_transition_for_init(self, validator: OutputContractValidator) -> None:
        """Test invalid transition for init node."""
        output = "STATUS: success\nTRANSITION: plan_ready\n"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert any("Invalid TRANSITION" in v for v in result.violations)
        assert any("goal_loaded" in v for v in result.violations)

    def test_valid_transition_for_plan(self, validator: OutputContractValidator) -> None:
        """Test valid transitions for plan node."""
        output1 = "STATUS: success\nTRANSITION: plan_ready\n"
        result1 = validator.validate_output(output1, "plan")
        assert result1.valid is True

        output2 = "STATUS: failure\nTRANSITION: plan_needs_revision\n"
        result2 = validator.validate_output(output2, "plan")
        assert result2.valid is True

    def test_invalid_transition_for_code(self, validator: OutputContractValidator) -> None:
        """Test invalid transition for code node."""
        output = "STATUS: success\nTRANSITION: tests_pass\n"
        result = validator.validate_output(output, "code")
        assert result.valid is False
        assert any("Invalid TRANSITION" in v for v in result.violations)

    def test_valid_transitions_for_test(self, validator: OutputContractValidator) -> None:
        """Test valid transitions for test node."""
        output = "STATUS: success\nTRANSITION: tests_pass\n"
        result = validator.validate_output(output, "test")
        assert result.valid is True

    def test_valid_transitions_for_review(self, validator: OutputContractValidator) -> None:
        """Test valid transitions for review node."""
        output = "STATUS: success\nTRANSITION: review_pass\n"
        result = validator.validate_output(output, "review")
        assert result.valid is True

    def test_valid_transitions_for_reflect(self, validator: OutputContractValidator) -> None:
        """Test valid transitions for reflect node."""
        output = "STATUS: success\nTRANSITION: evolution_proposed\n"
        result = validator.validate_output(output, "reflect")
        assert result.valid is True

    def test_unknown_node_skips_transition_validation(self, validator: OutputContractValidator) -> None:
        """Test that unknown node ID does not cause transition validation failure."""
        output = "STATUS: success\nTRANSITION: anything\n"
        result = validator.validate_output(output, "unknown_node")
        # Unknown node has no transitions listed, so any transition value is accepted
        assert result.valid is True


class TestStatusParsing:
    """Tests for STATUS line parsing."""

    @pytest.fixture
    def validator(self) -> OutputContractValidator:
        """Create a validator without graph validation."""
        return OutputContractValidator()

    def test_status_success(self, validator: OutputContractValidator) -> None:
        """Test STATUS: success is valid."""
        output = "STATUS: success\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.status == "success"
        assert result.valid is True

    def test_status_failure(self, validator: OutputContractValidator) -> None:
        """Test STATUS: failure is valid."""
        output = "STATUS: failure\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.status == "failure"
        assert result.valid is True

    def test_status_invalid_value(self, validator: OutputContractValidator) -> None:
        """Test STATUS with invalid value."""
        output = "STATUS: partial\nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.valid is False
        assert any("Invalid STATUS" in v for v in result.violations)

    def test_status_with_whitespace(self, validator: OutputContractValidator) -> None:
        """Test STATUS parsing handles whitespace."""
        output = "  STATUS:  success  \nTRANSITION: goal_loaded\n"
        result = validator.validate_output(output, "init")
        assert result.status == "success"
        assert result.valid is True


class TestRunnerContractIntegration:
    """Tests for contract validation integration with runner.py Mode 3."""

    @pytest.fixture
    def runner_env(self, tmp_path: Path) -> Path:
        """Set up a complete runner environment in tmp_path."""

        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()

        state_data = {
            "current_node": "init",
            "iteration_count": 0,
            "max_iterations": 30,
            "goal": "",
            "status": "idle",
            "last_updated": "",
            "errors": [],
            "context": {"skills_loaded": [], "current_task": "", "phase": "startup"},
        }
        with open(kernel_dir / "state.yaml", "w") as f:
            yaml.safe_dump(state_data, f)

        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                    "max_retries": 1,
                },
                {
                    "id": "plan",
                    "prompt_file": "prompts/planner.md",
                    "description": "Plan tasks",
                    "transitions": [
                        {"to": "code", "condition": "plan_ready"},
                        {"to": "plan", "condition": "plan_needs_revision"},
                    ],
                    "max_retries": 2,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Write code",
                    "transitions": [],
                    "max_retries": 3,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("Orchestrator prompt")
        (kernel_dir / "prompts" / "planner.md").write_text("Planner prompt")
        (kernel_dir / "prompts" / "coder.md").write_text("Coder prompt")

        (kernel_dir / "BOOT.md").write_text("# Boot\nBoot content.")
        (kernel_dir / "constitution.md").write_text("# Constitution\nRules.")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao\nDao content.")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy\nStrategy.")

        # contracts dir
        contracts_dir = kernel_dir / "contracts"
        contracts_dir.mkdir()
        (contracts_dir / "output_format.md").write_text("# Output Format Contract\nSpec.")

        # memory dir
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "decisions.jsonl").touch()
        (memory_dir / "reflections.jsonl").touch()
        (memory_dir / "current_goal.md").touch()
        with open(memory_dir / "progress.yaml", "w") as f:
            yaml.safe_dump(
                {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}, f
            )

        # knowledge dir
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        return tmp_path

    def test_mode3_valid_output_advances(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 advances when output passes contract validation."""
        from unittest.mock import MagicMock, patch

        import runner

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("Done.\nSTATUS: success\nTRANSITION: goal_loaded\n", "")
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test contract valid",
                "--ai-command", "echo hello",
                "--max-iterations", "1",
                "--complexity", "high",
            ])

        assert state["current_node"] == "plan"

    def test_mode3_invalid_output_stays_on_node(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 stays on same node when output fails contract validation."""
        from unittest.mock import MagicMock, patch

        import runner

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # Missing STATUS line - should fail validation
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("Some output\nTRANSITION: goal_loaded\n", "")
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test contract invalid",
                "--ai-command", "echo hi",
                "--max-iterations", "2",
            ])

        # Should stay on init since contract validation failed
        assert state["current_node"] == "init"
        assert any("Contract violations" in str(e) for e in state.get("errors", []))

    def test_mode3_invalid_transition_value_stays(self, runner_env: Path, monkeypatch) -> None:
        """Test Mode 3 stays on node when TRANSITION value is invalid for that node."""
        from unittest.mock import MagicMock, patch

        import runner

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        # plan_ready is not valid for init node
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("Done.\nSTATUS: success\nTRANSITION: plan_ready\n", "")
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            state = runner.main([
                "--goal", "test bad transition",
                "--ai-command", "echo hi",
                "--max-iterations", "2",
                "--complexity", "high",
            ])

        assert state["current_node"] == "init"
        assert any("Contract violations" in str(e) for e in state.get("errors", []))

    def test_mode3_contract_violation_logged_to_stderr(
        self, runner_env: Path, monkeypatch, capsys
    ) -> None:
        """Test that contract violations are printed to stderr."""
        from unittest.mock import MagicMock, patch

        import runner

        monkeypatch.setattr(runner, "KERNEL_ROOT", runner_env)

        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("No required lines here", "")
        mock_proc.returncode = 0
        mock_proc.kill.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc):
            runner.main([
                "--goal", "test violation logging",
                "--ai-command", "echo hi",
                "--max-iterations", "1",
            ])

        captured = capsys.readouterr()
        assert "[CONTRACT VIOLATION]" in captured.err


class TestContextAssemblerContract:
    """Tests for context_assembler including output format contract."""

    def test_assembled_output_includes_contract(self, tmp_path: Path) -> None:
        """Test that assembled context includes output format contract section."""
        from kernel.context_assembler import ContextAssembler
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        # Set up directory structure
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "constitution.md").write_text("# Constitution")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")
        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("# Orchestrator")
        contracts_dir = kernel_dir / "contracts"
        contracts_dir.mkdir()
        (contracts_dir / "output_format.md").write_text("# Output Format Contract\nSpec here.")

        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                }
            ],
            "default_start": "init",
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        assembler = ContextAssembler(tmp_path)
        graph = GraphExecutor(str(kernel_dir / "graph.yaml"))
        knowledge = KnowledgeStore(str(knowledge_dir))

        state = {"current_node": "init", "goal": "test", "iteration_count": 0,
                 "max_iterations": 30, "status": "running", "errors": [],
                 "context": {"skills_loaded": []}}
        node = {"id": "init"}

        result = assembler.assemble(state, node, graph, knowledge)
        assert "=== OUTPUT FORMAT CONTRACT ===" in result
        assert "# Output Format Contract" in result
        assert "Spec here." in result

    def test_assembled_output_without_contract_file(self, tmp_path: Path) -> None:
        """Test that missing contract file does not break assembly."""
        from kernel.context_assembler import ContextAssembler
        from kernel.graph_executor import GraphExecutor
        from knowledge.store import KnowledgeStore

        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "philosophy").mkdir()
        (kernel_dir / "philosophy" / "dao.md").write_text("# Dao")
        (kernel_dir / "philosophy" / "strategy.md").write_text("# Strategy")
        (kernel_dir / "prompts").mkdir()
        (kernel_dir / "prompts" / "orchestrator.md").write_text("# Orchestrator")
        # No contracts directory

        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Initialize",
                    "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                }
            ],
            "default_start": "init",
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        assembler = ContextAssembler(tmp_path)
        graph = GraphExecutor(str(kernel_dir / "graph.yaml"))
        knowledge = KnowledgeStore(str(knowledge_dir))

        state = {"current_node": "init", "goal": "test", "iteration_count": 0,
                 "max_iterations": 30, "status": "running", "errors": [],
                 "context": {"skills_loaded": []}}
        node = {"id": "init"}

        result = assembler.assemble(state, node, graph, knowledge)
        # Should not include the section when file is missing
        assert "=== OUTPUT FORMAT CONTRACT ===" not in result


# --- Robust Markdown Parsing Tests ---


@pytest.fixture
def validator() -> OutputContractValidator:
    """Create a validator without graph validation (for markdown variant tests)."""
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
            validator.validate_output(output, "test")
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


# --- Output Format Enforcement Tests ---


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


class TestFilesWrittenParsingWithGraph:
    """Tests for FILES_WRITTEN line parsing with graph validation."""

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
