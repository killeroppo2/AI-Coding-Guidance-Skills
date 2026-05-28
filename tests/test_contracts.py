"""Tests for kernel/contracts - output format contract validation."""

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
        import runner

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
        import runner
        from unittest.mock import patch, MagicMock

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
        import runner
        from unittest.mock import patch, MagicMock

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
        import runner
        from unittest.mock import patch, MagicMock

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
        import runner
        from unittest.mock import patch, MagicMock

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
