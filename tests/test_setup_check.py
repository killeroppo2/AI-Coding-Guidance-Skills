"""Tests for setup_check.py - environment validation."""

import sys

import yaml

from setup_check import SetupChecker


class TestCheckPythonVersion:
    """Tests for check_python_version."""

    def test_passes_on_current_python(self):
        """Current Python should pass (we require >= 3.11 and run on 3.12)."""
        checker = SetupChecker()
        passed, message = checker.check_python_version()
        assert passed is True
        assert "Python" in message
        assert f"{sys.version_info.major}.{sys.version_info.minor}" in message

    def test_message_includes_version(self):
        """Message should contain the full version string."""
        checker = SetupChecker()
        _, message = checker.check_python_version()
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert expected in message


class TestCheckPyyamlInstalled:
    """Tests for check_pyyaml_installed."""

    def test_passes_when_yaml_importable(self):
        """pyyaml should be detected when installed."""
        checker = SetupChecker()
        passed, message = checker.check_pyyaml_installed()
        assert passed is True
        assert "pyyaml" in message
        assert "installed" in message

    def test_message_includes_version(self):
        """Message should include the yaml version."""
        checker = SetupChecker()
        _, message = checker.check_pyyaml_installed()
        import yaml as _yaml

        assert _yaml.__version__ in message


class TestCheckKernelFilesPresent:
    """Tests for check_kernel_files_present with tmp_path fixtures."""

    def test_passes_with_all_files(self, tmp_path):
        """Should pass when all required kernel files exist."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "graph.yaml").write_text("nodes: []")
        (kernel_dir / "state.yaml").write_text("status: idle")
        (kernel_dir / "BOOT.md").write_text("# Boot")
        (kernel_dir / "constitution.md").write_text("# Rules")

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_kernel_files_present()
        assert passed is True
        assert "All 4 kernel files present" in message

    def test_fails_with_missing_files(self, tmp_path):
        """Should fail and list missing files."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "graph.yaml").write_text("nodes: []")
        # Missing: state.yaml, BOOT.md, constitution.md

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_kernel_files_present()
        assert passed is False
        assert "Missing:" in message
        assert "state.yaml" in message
        assert "BOOT.md" in message
        assert "constitution.md" in message

    def test_fails_with_no_kernel_dir(self, tmp_path):
        """Should fail when kernel directory does not exist."""
        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_kernel_files_present()
        assert passed is False
        assert "Missing:" in message

    def test_fails_with_partial_files(self, tmp_path):
        """Should report only the missing files."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "graph.yaml").write_text("nodes: []")
        (kernel_dir / "state.yaml").write_text("status: idle")
        # Missing: BOOT.md, constitution.md

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_kernel_files_present()
        assert passed is False
        assert "BOOT.md" in message
        assert "constitution.md" in message
        assert "graph.yaml" not in message
        assert "state.yaml" not in message


class TestCheckGraphLoadable:
    """Tests for check_graph_loadable."""

    def test_passes_with_valid_graph(self, tmp_path):
        """Should pass with valid YAML containing nodes key."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        graph_data = {
            "version": "1.0",
            "nodes": [
                {"id": "init", "description": "Start"},
                {"id": "plan", "description": "Plan"},
            ],
        }
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump(graph_data, f)

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_graph_loadable()
        assert passed is True
        assert "valid with 2 nodes" in message

    def test_fails_with_invalid_yaml(self, tmp_path):
        """Should fail with malformed YAML."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "graph.yaml").write_text("{{invalid: yaml: [[[")

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_graph_loadable()
        assert passed is False
        assert "load error" in message

    def test_fails_with_missing_nodes_key(self, tmp_path):
        """Should fail when 'nodes' key is absent."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        with open(kernel_dir / "graph.yaml", "w") as f:
            yaml.safe_dump({"version": "1.0", "description": "No nodes"}, f)

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_graph_loadable()
        assert passed is False
        assert "missing 'nodes' key" in message

    def test_fails_when_graph_not_found(self, tmp_path):
        """Should fail when graph.yaml does not exist."""
        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_graph_loadable()
        assert passed is False
        assert "not found" in message

    def test_fails_when_yaml_is_not_mapping(self, tmp_path):
        """Should fail when graph.yaml contains a non-mapping value."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "graph.yaml").write_text("- item1\n- item2\n")

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_graph_loadable()
        assert passed is False
        assert "not a valid YAML mapping" in message


class TestCheckSkillPaths:
    """Tests for check_skill_paths."""

    def test_passes_with_valid_skill_paths(self, tmp_path):
        """Should pass when all skill paths resolve to directories."""
        # Create skill directories
        (tmp_path / "skills" / "ralph").mkdir(parents=True)
        (tmp_path / "skills" / "prd").mkdir(parents=True)

        # Create _index.yaml
        index_data = {
            "items": [
                {"name": "ralph", "path": "ralph"},
                {"name": "prd", "path": "prd"},
            ]
        }
        with open(tmp_path / "skills" / "_index.yaml", "w") as f:
            yaml.safe_dump(index_data, f)

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_skill_paths()
        assert passed is True
        assert "All 2 skill paths valid" in message

    def test_fails_with_missing_skill_dirs(self, tmp_path):
        """Should fail and list missing skill directories."""
        (tmp_path / "skills").mkdir(parents=True)

        index_data = {
            "items": [
                {"name": "ralph", "path": "ralph"},
                {"name": "missing", "path": "missing"},
            ]
        }
        with open(tmp_path / "skills" / "_index.yaml", "w") as f:
            yaml.safe_dump(index_data, f)

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_skill_paths()
        assert passed is False
        assert "Missing:" in message
        assert "ralph" in message
        assert "missing" in message

    def test_fails_when_index_not_found(self, tmp_path):
        """Should fail when _index.yaml does not exist."""
        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_skill_paths()
        assert passed is False
        assert "not found" in message

    def test_passes_with_empty_items(self, tmp_path):
        """Should pass when items list is empty."""
        (tmp_path / "skills").mkdir(parents=True)
        index_data = {"items": []}
        with open(tmp_path / "skills" / "_index.yaml", "w") as f:
            yaml.safe_dump(index_data, f)

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_skill_paths()
        assert passed is True
        assert "No skill items to validate" in message

    def test_fails_when_index_not_mapping(self, tmp_path):
        """Should fail when _index.yaml is not a mapping."""
        (tmp_path / "skills").mkdir(parents=True)
        (tmp_path / "skills" / "_index.yaml").write_text("- item1\n")

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_skill_paths()
        assert passed is False
        assert "not a valid YAML mapping" in message

    def test_skips_items_with_empty_path(self, tmp_path):
        """Should skip items with empty or missing path field."""
        (tmp_path / "skills").mkdir(parents=True)
        index_data = {
            "items": [
                {"name": "nopath"},
                {"name": "empty", "path": ""},
            ]
        }
        with open(tmp_path / "skills" / "_index.yaml", "w") as f:
            yaml.safe_dump(index_data, f)

        checker = SetupChecker(str(tmp_path))
        passed, message = checker.check_skill_paths()
        assert passed is True


class TestRunAllChecks:
    """Tests for run_all_checks."""

    def test_returns_correct_length(self):
        """Should return 5 check results."""
        checker = SetupChecker()
        results = checker.run_all_checks()
        assert len(results) == 5

    def test_each_result_has_required_keys(self):
        """Each result dict should have check, passed, and message keys."""
        checker = SetupChecker()
        results = checker.run_all_checks()
        for r in results:
            assert "check" in r
            assert "passed" in r
            assert "message" in r

    def test_check_names_match_expected(self):
        """Check names should be in the expected order."""
        checker = SetupChecker()
        results = checker.run_all_checks()
        expected_names = [
            "python_version",
            "pyyaml_installed",
            "kernel_files_present",
            "graph_loadable",
            "skill_paths",
        ]
        assert [r["check"] for r in results] == expected_names


class TestPrintResults:
    """Tests for print_results."""

    def test_returns_zero_when_all_pass(self, capsys):
        """Should return 0 when all checks pass."""
        checker = SetupChecker()
        results = [
            {"check": "test1", "passed": True, "message": "OK"},
            {"check": "test2", "passed": True, "message": "OK"},
        ]
        exit_code = checker.print_results(results)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "All checks passed" in captured.out

    def test_returns_one_when_any_fail(self, capsys):
        """Should return 1 when any check fails."""
        checker = SetupChecker()
        results = [
            {"check": "test1", "passed": True, "message": "OK"},
            {"check": "test2", "passed": False, "message": "Bad"},
        ]
        exit_code = checker.print_results(results)
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.out
        assert "Some checks failed" in captured.out

    def test_prints_all_results(self, capsys):
        """Should print a line for each check result."""
        checker = SetupChecker()
        results = [
            {"check": "alpha", "passed": True, "message": "Good"},
            {"check": "beta", "passed": False, "message": "Bad"},
            {"check": "gamma", "passed": True, "message": "Fine"},
        ]
        checker.print_results(results)
        captured = capsys.readouterr()
        assert "alpha" in captured.out
        assert "beta" in captured.out
        assert "gamma" in captured.out
