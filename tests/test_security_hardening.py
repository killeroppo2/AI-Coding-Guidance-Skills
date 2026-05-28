"""Tests for security hardening: adversarial inputs and injection prevention.

Covers Round 9 iteration concerns:
- Shell injection via --goal
- Path traversal in project names and workspace paths
- Null bytes and control characters
- Unicode exploitation (RTL override, zero-width chars)
- Very long inputs
- YAML safety (yaml.safe_load usage)
- Adversarial AI output parsing
"""

from kernel.mode3_executor import _parse_transition
from kernel.validators import _sanitize_project_name, _validate_workspace_paths


class TestSanitizeProjectNameAdversarial:
    """Adversarial inputs to _sanitize_project_name."""

    def test_shell_injection_semicolon(self) -> None:
        """Shell injection with semicolons is neutralized."""
        result = _sanitize_project_name("test; rm -rf /")
        assert ";" not in result
        assert "/" not in result
        assert result == "test-rm--rf-"

    def test_shell_injection_pipe(self) -> None:
        """Shell injection with pipes is neutralized."""
        result = _sanitize_project_name("test | cat /etc/passwd")
        assert "|" not in result
        assert "/" not in result

    def test_shell_injection_backtick(self) -> None:
        """Shell injection with backticks is neutralized."""
        result = _sanitize_project_name("test `rm -rf /`")
        assert "`" not in result

    def test_shell_injection_dollar_paren(self) -> None:
        """Shell injection with $() is neutralized."""
        result = _sanitize_project_name("test $(rm -rf /)")
        assert "$" not in result
        assert "(" not in result
        assert ")" not in result

    def test_shell_injection_ampersand(self) -> None:
        """Shell injection with && is neutralized."""
        result = _sanitize_project_name("test && rm -rf /")
        assert "&" not in result

    def test_path_traversal_relative(self) -> None:
        """Path traversal with ../ is neutralized."""
        result = _sanitize_project_name("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert "etc" in result  # letters preserved

    def test_path_traversal_backslash(self) -> None:
        """Path traversal with backslashes is neutralized."""
        result = _sanitize_project_name("..\\..\\windows\\system32")
        assert "\\" not in result

    def test_null_bytes(self) -> None:
        """Null bytes are stripped from project names."""
        result = _sanitize_project_name("test\x00evil")
        assert "\x00" not in result
        assert result == "testevil"

    def test_null_bytes_between_safe_chars(self) -> None:
        """Null bytes between safe chars are stripped cleanly."""
        result = _sanitize_project_name("a\x00b\x00c")
        assert result == "abc"

    def test_very_long_input(self) -> None:
        """Very long input is truncated to 50 characters."""
        result = _sanitize_project_name("a" * 10000)
        assert len(result) == 50
        assert result == "a" * 50

    def test_very_long_with_special_chars(self) -> None:
        """Long input with special chars truncates after sanitization."""
        result = _sanitize_project_name("x!" * 5000)
        assert len(result) <= 50
        assert all(c in "x" for c in result)

    def test_unicode_control_characters(self) -> None:
        """Control characters (U+0001-U+001F) are stripped."""
        result = _sanitize_project_name("test\x01\x02\x03\x04evil")
        assert result == "testevil"

    def test_unicode_rtl_override(self) -> None:
        """RTL override character (U+202E) is stripped."""
        result = _sanitize_project_name("test\u202eevil")
        assert "\u202e" not in result
        assert result == "testevil"

    def test_unicode_zero_width_chars(self) -> None:
        """Zero-width characters are stripped."""
        result = _sanitize_project_name("te\u200bst\u200c\u200d")
        assert "\u200b" not in result
        assert "\u200c" not in result
        assert "\u200d" not in result
        assert result == "test"

    def test_unicode_bom(self) -> None:
        """BOM character (U+FEFF) is stripped."""
        result = _sanitize_project_name("\ufefftest")
        assert "\ufeff" not in result
        assert result == "test"

    def test_unicode_direction_marks(self) -> None:
        """Directional formatting characters are stripped."""
        result = _sanitize_project_name("he\u202allo\u202b")
        assert result == "hello"

    def test_only_control_chars_returns_empty(self) -> None:
        """Input of only control characters returns empty string."""
        result = _sanitize_project_name("\x00\x01\x02\x03")
        assert result == ""

    def test_newlines_and_tabs_stripped(self) -> None:
        """Newlines and tabs are treated as control characters."""
        result = _sanitize_project_name("test\n\r\tevil")
        assert "\n" not in result
        assert "\r" not in result
        assert "\t" not in result

    def test_result_is_filesystem_safe(self) -> None:
        """Result contains only a-z, 0-9, and hyphens."""
        import re

        adversarial_inputs = [
            "test; rm -rf /",
            "../../etc/passwd",
            "test\x00evil",
            "a" * 10000,
            "test\u202eevil",
            "\x01\x02\x03",
            "$(command)",
            "hello | world",
            "test\n\revil",
        ]
        for inp in adversarial_inputs:
            result = _sanitize_project_name(inp)
            assert re.match(r"^[a-z0-9-]*$", result), (
                f"Unsafe chars in result for input {repr(inp)}: {repr(result)}"
            )


class TestValidateWorkspacePathsAdversarial:
    """Adversarial path traversal tests for _validate_workspace_paths."""

    def test_relative_path_traversal(self) -> None:
        """Relative path traversal is detected."""
        violations = _validate_workspace_paths(["../../../etc/passwd"], "/workspace/project")
        assert len(violations) == 1
        assert "outside workspace" in violations[0]

    def test_deep_relative_traversal(self) -> None:
        """Deep relative traversal (many ../) is detected."""
        violations = _validate_workspace_paths(
            ["../../../../../../../../etc/shadow"], "/workspace/project"
        )
        assert len(violations) == 1

    def test_symlink_style_traversal(self) -> None:
        """Symlink-style path that escapes workspace is detected."""
        violations = _validate_workspace_paths(
            ["workspace/../../../etc/passwd"], "/workspace/project"
        )
        assert len(violations) == 1

    def test_absolute_path_outside(self) -> None:
        """Absolute paths outside workspace are detected."""
        violations = _validate_workspace_paths(["/etc/passwd"], "/workspace/project")
        assert len(violations) == 1

    def test_absolute_path_etc_shadow(self) -> None:
        """Sensitive system files are blocked."""
        violations = _validate_workspace_paths(["/etc/shadow"], "/workspace/project")
        assert len(violations) == 1

    def test_path_with_null_in_name(self) -> None:
        """Paths with embedded nulls in the name portion."""
        # os.path functions handle this gracefully
        violations = _validate_workspace_paths(
            ["/workspace/project/test\x00.py"], "/workspace/project"
        )
        # This should be inside workspace (or os handles it)
        # The key is it does not crash
        assert isinstance(violations, list)

    def test_valid_path_inside_workspace(self) -> None:
        """Valid paths inside workspace produce no violations."""
        violations = _validate_workspace_paths(
            ["/workspace/project/src/main.py"], "/workspace/project"
        )
        assert violations == []

    def test_valid_nested_path(self) -> None:
        """Deeply nested valid paths produce no violations."""
        violations = _validate_workspace_paths(
            ["/workspace/project/a/b/c/d/e/file.py"], "/workspace/project"
        )
        assert violations == []

    def test_workspace_path_itself(self) -> None:
        """The workspace path itself is valid."""
        violations = _validate_workspace_paths(["/workspace/project"], "/workspace/project")
        assert violations == []

    def test_empty_workspace_skips_check(self) -> None:
        """Empty workspace path means no check is performed."""
        violations = _validate_workspace_paths(["../../../anything"], "")
        assert violations == []

    def test_multiple_violations(self) -> None:
        """Multiple violating paths are all reported."""
        violations = _validate_workspace_paths(
            ["/etc/passwd", "../secret", "/root/.ssh/id_rsa"],
            "/workspace/project",
        )
        assert len(violations) == 3

    def test_mixed_valid_and_invalid(self) -> None:
        """Mix of valid and invalid paths reports only invalid ones."""
        violations = _validate_workspace_paths(
            ["/workspace/project/ok.py", "/etc/passwd", "/workspace/project/also_ok.py"],
            "/workspace/project",
        )
        assert len(violations) == 1
        assert "/etc/passwd" in violations[0]


class TestParseTransitionAdversarial:
    """Adversarial AI output parsing tests for _parse_transition."""

    def test_very_large_output(self) -> None:
        """10MB of output does not hang or crash."""
        big_output = "x" * (10 * 1024 * 1024) + "\nTRANSITION: done\n"
        # With 1MB scan limit, the TRANSITION at the end may not be found
        # The key point is it does not hang
        result = _parse_transition(big_output)
        # Since we limit to 1MB scan, result is None (TRANSITION is after 1MB)
        assert result is None

    def test_large_output_with_early_transition(self) -> None:
        """TRANSITION at the start of large output is found."""
        big_output = "TRANSITION: early\n" + "x" * (10 * 1024 * 1024)
        result = _parse_transition(big_output)
        assert result == "early"

    def test_binary_data_control_chars(self) -> None:
        """Binary/control character data does not crash parser."""
        binary_output = "Hello\x00world\x01\x02\nTRANSITION: valid\n\x03\x04"
        result = _parse_transition(binary_output)
        assert result == "valid"

    def test_output_with_only_binary(self) -> None:
        """Pure binary output returns None."""
        binary_output = bytes(range(256)).decode("latin-1")
        result = _parse_transition(binary_output)
        assert result is None

    def test_multiple_transitions_takes_first(self) -> None:
        """Multiple TRANSITION lines: first one wins."""
        output = "TRANSITION: first\nTRANSITION: second\nTRANSITION: third"
        result = _parse_transition(output)
        assert result == "first"

    def test_transition_with_path_traversal(self) -> None:
        """TRANSITION value containing path traversal is rejected."""
        output = "TRANSITION: ../../evil"
        result = _parse_transition(output)
        assert result is None

    def test_transition_with_forward_slash(self) -> None:
        """TRANSITION value containing forward slash is rejected."""
        output = "TRANSITION: /etc/passwd"
        result = _parse_transition(output)
        assert result is None

    def test_transition_with_backslash(self) -> None:
        """TRANSITION value containing backslash is rejected."""
        output = "TRANSITION: ..\\windows\\system32"
        result = _parse_transition(output)
        assert result is None

    def test_transition_with_null_byte(self) -> None:
        """TRANSITION value containing null byte is rejected."""
        output = "TRANSITION: test\x00evil"
        result = _parse_transition(output)
        assert result is None

    def test_valid_transition_underscore(self) -> None:
        """Valid transition with underscores works."""
        output = "TRANSITION: plan_ready"
        result = _parse_transition(output)
        assert result == "plan_ready"

    def test_valid_transition_hyphen(self) -> None:
        """Valid transition with hyphens works."""
        output = "TRANSITION: task-complete"
        result = _parse_transition(output)
        assert result == "task-complete"

    def test_empty_transition_value(self) -> None:
        """TRANSITION with empty value returns empty string."""
        output = "TRANSITION: "
        result = _parse_transition(output)
        assert result == ""

    def test_empty_output(self) -> None:
        """Empty output returns None."""
        assert _parse_transition("") is None

    def test_output_with_very_long_lines(self) -> None:
        """Output with extremely long lines does not hang."""
        long_line = "a" * 1_000_000
        output = f"{long_line}\nTRANSITION: found\n{long_line}"
        result = _parse_transition(output)
        assert result == "found"


class TestYamlSafetyAudit:
    """Verify yaml.safe_load is used everywhere, never the unsafe variant."""

    def test_no_unsafe_yaml_load_in_codebase(self) -> None:
        """No Python file uses the unsafe yaml loader without SafeLoader."""
        import os

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # The pattern we are looking for (unsafe usage)
        unsafe_pattern = "yaml" + ".load("
        violations = []

        for dirpath, _dirs, files in os.walk(project_root):
            # Skip hidden dirs, __pycache__, venv
            if any(
                part.startswith(".")
                or part == "__pycache__"
                or part in ("venv", ".venv", "node_modules")
                for part in dirpath.split(os.sep)
            ):
                continue
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                # Skip this test file itself
                if os.path.basename(fpath) == "test_security_hardening.py":
                    continue
                try:
                    with open(fpath, encoding="utf-8") as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue
                # Check for yaml.load( without Loader= on same line
                for i, line in enumerate(content.splitlines(), 1):
                    if unsafe_pattern in line and "Loader=" not in line:
                        if "safe_load" not in line:
                            violations.append(f"{fpath}:{i}: {line.strip()}")

        assert violations == [], "Found unsafe yaml loader usage:\n" + "\n".join(violations)
