"""Output format contract validation for kernel AI responses.

This module provides the OutputContractValidator class which validates
AI output against the formal output format specification defined in
kernel/contracts/output_format.md.
"""

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ContractResult:
    """Result of validating AI output against the output format contract.

    Attributes:
        valid: Whether the output conforms to the contract.
        transition: The parsed TRANSITION value, or None if missing.
        files_written: List of file paths reported via FILES_WRITTEN.
        errors: List of error messages reported via ERROR lines.
        status: The parsed STATUS value (success/failure), or empty string.
        violations: List of contract violation descriptions.
    """

    valid: bool
    transition: str | None = None
    files_written: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = ""
    violations: list[str] = field(default_factory=list)


class OutputContractValidator:
    """Validates AI output against the kernel output format contract.

    The validator parses output for required lines (TRANSITION, STATUS)
    and optional lines (FILES_WRITTEN, ERROR), then checks that values
    are valid for the given node based on graph.yaml transitions.
    """

    def __init__(self, graph_path: str | Path | None = None) -> None:
        """Initialize the validator.

        Args:
            graph_path: Path to graph.yaml for transition validation.
                        If None, transition value validation is skipped.
        """
        self._valid_transitions: dict[str, list[str]] = {}
        if graph_path is not None:
            self._load_valid_transitions(Path(graph_path))

    def _load_valid_transitions(self, graph_path: Path) -> None:
        """Load valid transition conditions per node from graph.yaml.

        Args:
            graph_path: Path to the graph.yaml file.
        """
        if not graph_path.exists():
            return
        with open(graph_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for node in data.get("nodes", []):
            node_id = node.get("id", "")
            conditions = []
            for transition in node.get("transitions", []):
                condition = transition.get("condition", "")
                if condition:
                    conditions.append(condition)
            self._valid_transitions[node_id] = conditions

    def _strip_markdown(self, line: str) -> str:
        """Remove markdown formatting from a line.

        Strips leading `> `, `- `, `* `, `**`, backticks, trailing `**`,
        and any leading/trailing whitespace.

        Args:
            line: The raw line text.

        Returns:
            The line with markdown formatting removed.
        """
        result = line.strip()
        # Strip leading blockquote marker
        if result.startswith("> "):
            result = result[2:]
        elif result.startswith(">"):
            result = result[1:]
        # Strip leading list markers
        if result.startswith("- "):
            result = result[2:]
        elif result.startswith("* "):
            result = result[2:]
        # Strip leading bold markers
        if result.startswith("**"):
            result = result[2:]
        # Strip leading backticks
        result = result.lstrip("`")
        # Strip trailing bold markers
        if result.endswith("**"):
            result = result[:-2]
        # Strip trailing backticks
        result = result.rstrip("`")
        # Remove inline bold/backtick markers around keywords (e.g. KEYWORD:** val -> KEYWORD: val)
        result = re.sub(r"\*{1,2}(?=\s*:)", "", result)
        result = re.sub(r":\s*\*{1,2}\s*", ": ", result)
        # Remove backticks adjacent to the colon (e.g. KEYWORD`: value -> KEYWORD: value)
        result = re.sub(r"`(?=\s*:)", "", result)
        result = re.sub(r":\s*`\s*", ": ", result)
        # Final strip
        result = result.strip()
        return result

    def _extract_from_code_blocks(self, output: str, keyword: str) -> str | None:
        """Search inside ``` code blocks for lines matching the keyword pattern.

        Inside code blocks, content is literal text so no markdown stripping
        is needed. Uses a simple regex anchored to start of line.

        Args:
            output: The full AI output string.
            keyword: The keyword to search for (e.g., 'TRANSITION').

        Returns:
            The value after the keyword and colon, or None if not found.
        """
        pattern = re.compile(
            r"^" + keyword + r"\s*:\s*(.+)",
            re.IGNORECASE,
        )
        in_code_block = False
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                match = pattern.match(stripped)
                if match:
                    return match.group(1).strip()
        return None

    def _semantic_infer_transition(self, output: str) -> str | None:
        """Infer transition from natural language phrases in the output.

        Checks the full output text (case-insensitive) for known phrases
        and maps them to transition values. Emits a WARNING when inference
        is used.

        Args:
            output: The full AI output string.

        Returns:
            The inferred transition string, or None if no match.
        """
        phrase_map = [
            (["all tests pass", "tests passing"], "tests_pass"),
            (["plan is ready", "plan complete"], "plan_ready"),
            (["goal loaded", "context initialized"], "goal_loaded"),
            (["code written", "implementation complete"], "code_written"),
            (["review pass", "code quality acceptable"], "review_pass"),
            (["no evolution", "no changes needed"], "no_evolution_needed"),
        ]
        output_lower = output.lower()
        for phrases, transition in phrase_map:
            for phrase in phrases:
                if phrase in output_lower:
                    warnings.warn(
                        f"TRANSITION inferred from semantic content: '{phrase}' -> '{transition}'",
                        stacklevel=2,
                    )
                    return transition
        return None

    def validate_output(self, output: str, node_id: str) -> ContractResult:
        """Validate AI output against the output format contract.

        Parses the output for TRANSITION, STATUS, FILES_WRITTEN, and ERROR
        lines, then validates values against the contract rules.

        Args:
            output: The raw AI output string.
            node_id: The current node ID for transition validation.

        Returns:
            A ContractResult with parsed values and any violations.
        """
        violations: list[str] = []
        transition = self._parse_transition(output)
        status = self._parse_status(output)
        files_written = self._parse_files_written(output)
        errors = self._parse_errors(output)

        # Validate TRANSITION
        if transition is None:
            violations.append("Missing required TRANSITION line")
        elif self._valid_transitions:
            valid_for_node = self._valid_transitions.get(node_id, [])
            if valid_for_node and transition not in valid_for_node:
                violations.append(
                    f"Invalid TRANSITION '{transition}' for node '{node_id}'. "
                    f"Valid transitions: {valid_for_node}"
                )

        # Validate STATUS
        if not status:
            violations.append("Missing required STATUS line")
        elif status not in ("success", "failure"):
            violations.append(
                f"Invalid STATUS '{status}'. Must be 'success' or 'failure'"
            )

        valid = len(violations) == 0

        return ContractResult(
            valid=valid,
            transition=transition,
            files_written=files_written,
            errors=errors,
            status=status,
            violations=violations,
        )

    def _parse_transition(self, output: str) -> str | None:
        """Parse the TRANSITION line from output.

        Uses _strip_markdown first, then a strict anchored regex on the
        cleaned text to avoid false positives. Falls back to code block
        extraction and semantic inference.

        Args:
            output: The raw AI output.

        Returns:
            The transition condition string, or None if not found.
        """
        pattern = re.compile(
            r"^TRANSITION\s*:\s*(.+)",
            re.IGNORECASE,
        )
        for line in output.splitlines():
            stripped = self._strip_markdown(line)
            match = pattern.match(stripped)
            if match:
                return match.group(1).strip()

        # Try extracting from code blocks
        result = self._extract_from_code_blocks(output, "TRANSITION")
        if result is not None:
            return result

        # Fallback to semantic inference
        return self._semantic_infer_transition(output)

    def _parse_status(self, output: str) -> str:
        """Parse the STATUS line from output.

        Uses _strip_markdown first, then a strict anchored regex on the
        cleaned text to avoid false positives. Falls back to code block
        extraction.

        Args:
            output: The raw AI output.

        Returns:
            The status string, or empty string if not found.
        """
        pattern = re.compile(
            r"^STATUS\s*:\s*(.+)",
            re.IGNORECASE,
        )
        for line in output.splitlines():
            stripped = self._strip_markdown(line)
            match = pattern.match(stripped)
            if match:
                return match.group(1).strip()

        # Try extracting from code blocks
        result = self._extract_from_code_blocks(output, "STATUS")
        if result is not None:
            return result

        return ""

    def _parse_files_written(self, output: str) -> list[str]:
        """Parse FILES_WRITTEN lines from output.

        Uses _strip_markdown first, then a strict anchored regex on the
        cleaned text to avoid false positives. Falls back to code block
        extraction.

        Args:
            output: The raw AI output.

        Returns:
            List of file paths found.
        """
        pattern = re.compile(
            r"^FILES_WRITTEN\s*:\s*(.*)",
            re.IGNORECASE,
        )
        files: list[str] = []
        for line in output.splitlines():
            stripped = self._strip_markdown(line)
            match = pattern.match(stripped)
            if match:
                raw = match.group(1).strip()
                if raw:
                    files.extend(
                        f.strip() for f in raw.split(",") if f.strip()
                    )

        if not files:
            # Try extracting from code blocks
            result = self._extract_from_code_blocks(output, "FILES_WRITTEN")
            if result is not None:
                files.extend(
                    f.strip() for f in result.split(",") if f.strip()
                )

        return files

    def _parse_errors(self, output: str) -> list[str]:
        """Parse ERROR lines from output.

        Uses _strip_markdown first, then a strict anchored regex on the
        cleaned text to avoid false positives. Falls back to code block
        extraction.

        Args:
            output: The raw AI output.

        Returns:
            List of error messages found.
        """
        pattern = re.compile(
            r"^ERROR\s*:\s*(.*)",
            re.IGNORECASE,
        )
        errors: list[str] = []
        for line in output.splitlines():
            stripped = self._strip_markdown(line)
            match = pattern.match(stripped)
            if match:
                msg = match.group(1).strip()
                if msg:
                    errors.append(msg)

        if not errors:
            # Try extracting from code blocks
            result = self._extract_from_code_blocks(output, "ERROR")
            if result is not None:
                msg = result.strip()
                if msg:
                    errors.append(msg)

        return errors
