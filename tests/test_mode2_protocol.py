"""Tests for Mode 2 protocol documentation consistency.

Validates that mode2_protocol.md and state_transitions.md are consistent
with the actual kernel codebase (graph.yaml, file structure).
"""

import re
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def kernel_root() -> Path:
    """Return the root directory of the kernel project."""
    return Path(__file__).parent.parent


@pytest.fixture
def graph_data(kernel_root: Path) -> dict:
    """Load and return the parsed graph.yaml data."""
    graph_path = kernel_root / "kernel" / "graph.yaml"
    with open(graph_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def graph_node_ids(graph_data: dict) -> list[str]:
    """Extract all node IDs from graph.yaml."""
    return [node["id"] for node in graph_data.get("nodes", [])]


@pytest.fixture
def mode2_protocol_content(kernel_root: Path) -> str:
    """Read mode2_protocol.md content."""
    path = kernel_root / "kernel" / "contracts" / "mode2_protocol.md"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def state_transitions_content(kernel_root: Path) -> str:
    """Read state_transitions.md content."""
    path = kernel_root / "kernel" / "contracts" / "state_transitions.md"
    return path.read_text(encoding="utf-8")


class TestStateTransitionsConsistency:
    """Tests that state_transitions.md matches graph.yaml."""

    def test_all_graph_nodes_in_transitions_doc(
        self, graph_node_ids: list[str], state_transitions_content: str
    ) -> None:
        """All node IDs from graph.yaml appear in state_transitions.md."""
        for node_id in graph_node_ids:
            assert node_id in state_transitions_content, (
                f"Node '{node_id}' from graph.yaml not found in state_transitions.md"
            )

    def test_all_transitions_from_graph_documented(
        self, graph_data: dict, state_transitions_content: str
    ) -> None:
        """All transitions defined in graph.yaml are documented."""
        for node in graph_data.get("nodes", []):
            source = node["id"]
            for transition in node.get("transitions", []):
                target = transition["to"]
                condition = transition["condition"]
                # Check that the transition row exists in the table
                assert condition in state_transitions_content, (
                    f"Transition condition '{condition}' ({source}->{target}) "
                    f"not found in state_transitions.md"
                )
                assert target in state_transitions_content, (
                    f"Target node '{target}' for condition '{condition}' "
                    f"not found in state_transitions.md"
                )

    def test_transition_table_has_correct_source_target_pairs(
        self, graph_data: dict, state_transitions_content: str
    ) -> None:
        """Transition table rows match source->target from graph.yaml."""
        # Extract table rows from state_transitions.md
        table_pattern = re.compile(
            r"\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|"
        )
        table_rows = table_pattern.findall(state_transitions_content)
        # Filter out header row
        doc_transitions = [
            (src, tgt, cond)
            for src, tgt, cond in table_rows
            if src not in ("Source", "---")
        ]

        # Build expected transitions from graph.yaml
        expected = []
        for node in graph_data.get("nodes", []):
            source = node["id"]
            for transition in node.get("transitions", []):
                expected.append((source, transition["to"], transition["condition"]))

        for src, tgt, cond in expected:
            assert (src, tgt, cond) in doc_transitions, (
                f"Expected transition ({src}->{tgt} via {cond}) "
                f"not found in transition table"
            )

    def test_documented_fields_updated_on_transition(
        self, state_transitions_content: str
    ) -> None:
        """Required state fields are documented in the update rules."""
        required_fields = ["current_node", "iteration_count", "last_updated", "node_visits"]
        for field_name in required_fields:
            assert field_name in state_transitions_content, (
                f"Field '{field_name}' not documented in state_transitions.md"
            )


class TestMode2ProtocolConsistency:
    """Tests that mode2_protocol.md references are valid."""

    def test_referenced_files_exist(
        self, kernel_root: Path, mode2_protocol_content: str
    ) -> None:
        """File paths referenced in mode2_protocol.md exist in the project."""
        # Extract file paths from the table and text
        file_refs = [
            "kernel/state.yaml",
            "memory/tasks.yaml",
            "kernel/graph.yaml",
            "memory/decisions.jsonl",
            "memory/reflections.jsonl",
        ]
        for file_ref in file_refs:
            assert file_ref in mode2_protocol_content, (
                f"Expected file reference '{file_ref}' not in mode2_protocol.md"
            )
            # Check actual file exists (tasks.yaml may not exist yet, so check parent dir)
            file_path = kernel_root / file_ref
            if file_ref == "memory/tasks.yaml":
                # tasks.yaml is created at runtime, verify parent exists
                assert file_path.parent.exists(), (
                    f"Parent directory for '{file_ref}' does not exist"
                )
            else:
                assert file_path.exists(), (
                    f"File '{file_ref}' referenced in mode2_protocol.md does not exist"
                )

    def test_yaml_examples_parse_correctly(
        self, mode2_protocol_content: str
    ) -> None:
        """YAML code blocks in mode2_protocol.md parse without errors."""
        # Extract YAML code blocks (```yaml ... ```)
        yaml_blocks = re.findall(
            r"```yaml\n(.*?)```", mode2_protocol_content, re.DOTALL
        )
        assert len(yaml_blocks) > 0, "No YAML examples found in mode2_protocol.md"

        for i, block in enumerate(yaml_blocks):
            # Strip comment lines that start with # (YAML comments are fine,
            # but some blocks have explanatory comments before the YAML)
            # Filter out lines that are pure JSON (for decisions.jsonl example)
            lines = block.strip().split("\n")
            # Remove leading comment lines
            yaml_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    # This is a JSON line example, skip YAML parsing
                    continue
                yaml_lines.append(line)

            yaml_content = "\n".join(yaml_lines)
            # Strip comment-only lines for content check
            non_comment_lines = [
                l for l in yaml_lines
                if l.strip() and not l.strip().startswith("#")
            ]
            if not non_comment_lines:
                # Block only had comments or JSON lines, skip
                continue

            try:
                result = yaml.safe_load(yaml_content)
                assert result is not None, (
                    f"YAML block {i + 1} parsed to None"
                )
            except yaml.YAMLError as e:
                pytest.fail(
                    f"YAML block {i + 1} in mode2_protocol.md failed to parse: {e}"
                )

    def test_documents_yaml_format_for_state(
        self, mode2_protocol_content: str
    ) -> None:
        """mode2_protocol.md documents YAML format for state files."""
        assert "YAML" in mode2_protocol_content
        assert "kernel/state.yaml" in mode2_protocol_content

    def test_documents_jsonl_format_for_logs(
        self, mode2_protocol_content: str
    ) -> None:
        """mode2_protocol.md documents JSONL format for log files."""
        assert "JSONL" in mode2_protocol_content
        assert "decisions.jsonl" in mode2_protocol_content
        assert "reflections.jsonl" in mode2_protocol_content


class TestBootMdReferences:
    """Tests that BOOT.md references the new contract files."""

    def test_boot_md_references_mode2_protocol(self, kernel_root: Path) -> None:
        """BOOT.md references mode2_protocol.md."""
        boot_path = kernel_root / "kernel" / "BOOT.md"
        content = boot_path.read_text(encoding="utf-8")
        assert "kernel/contracts/mode2_protocol.md" in content

    def test_boot_md_references_state_transitions(self, kernel_root: Path) -> None:
        """BOOT.md references state_transitions.md."""
        boot_path = kernel_root / "kernel" / "BOOT.md"
        content = boot_path.read_text(encoding="utf-8")
        assert "kernel/contracts/state_transitions.md" in content

    def test_boot_md_has_mode2_helper_section(self, kernel_root: Path) -> None:
        """BOOT.md has the Mode 2 Protocol References section."""
        boot_path = kernel_root / "kernel" / "BOOT.md"
        content = boot_path.read_text(encoding="utf-8")
        assert "Mode 2 Protocol References" in content
