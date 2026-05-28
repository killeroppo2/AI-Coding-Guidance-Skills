"""Environment setup checker for the AI development kernel."""

import sys
from pathlib import Path
from typing import Any


class SetupChecker:
    """Validates the environment and project setup for the AI development kernel."""

    def __init__(self, project_root: str | None = None):
        """Initialize the checker with the project root directory.

        Args:
            project_root: Path to the project root. Defaults to the directory
                containing this script.
        """
        if project_root is None:
            self.root = Path(__file__).parent
        else:
            self.root = Path(project_root)

    def check_python_version(self) -> tuple[bool, str]:
        """Check that Python version is >= 3.11.

        Returns:
            Tuple of (passed, message).
        """
        major = sys.version_info.major
        minor = sys.version_info.minor
        patch = sys.version_info.micro
        version_str = f"{major}.{minor}.{patch}"
        if major >= 3 and minor >= 11:
            return (True, f"Python {version_str}")
        return (False, f"Python {version_str} found, need >= 3.11")

    def check_pyyaml_installed(self) -> tuple[bool, str]:
        """Check that pyyaml is importable.

        Returns:
            Tuple of (passed, message).
        """
        try:
            import yaml

            version = getattr(yaml, "__version__", "unknown")
            return (True, f"pyyaml {version} installed")
        except ImportError:
            return (False, "pyyaml not found")

    def check_kernel_files_present(self) -> tuple[bool, str]:
        """Check that required kernel files exist.

        Checks for: kernel/graph.yaml, kernel/state.yaml, kernel/BOOT.md,
        kernel/constitution.md

        Returns:
            Tuple of (passed, message).
        """
        required_files = [
            "kernel/graph.yaml",
            "kernel/state.yaml",
            "kernel/BOOT.md",
            "kernel/constitution.md",
        ]
        missing = []
        for rel_path in required_files:
            if not (self.root / rel_path).exists():
                missing.append(rel_path)
        if not missing:
            return (True, f"All {len(required_files)} kernel files present")
        return (False, f"Missing: {', '.join(missing)}")

    def check_graph_loadable(self) -> tuple[bool, str]:
        """Check that kernel/graph.yaml is valid YAML with a 'nodes' key.

        Returns:
            Tuple of (passed, message).
        """
        graph_path = self.root / "kernel" / "graph.yaml"
        if not graph_path.exists():
            return (False, "kernel/graph.yaml not found")
        try:
            import yaml

            with open(graph_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return (False, "graph.yaml is not a valid YAML mapping")
            if "nodes" not in data:
                return (False, "graph.yaml missing 'nodes' key")
            node_count = len(data["nodes"])
            return (True, f"graph.yaml valid with {node_count} nodes")
        except Exception as e:
            return (False, f"graph.yaml load error: {e}")

    def check_skill_paths(self) -> tuple[bool, str]:
        """Check that all skill paths in _index.yaml resolve to existing directories.

        Returns:
            Tuple of (passed, message).
        """
        index_path = self.root / "skills" / "_index.yaml"
        if not index_path.exists():
            return (False, "skills/_index.yaml not found")
        try:
            import yaml

            with open(index_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return (False, "_index.yaml is not a valid YAML mapping")
            items = data.get("items", [])
            if not items:
                return (True, "No skill items to validate")
            missing = []
            for item in items:
                path_str = item.get("path", "")
                if not path_str:
                    continue
                skill_dir = self.root / "skills" / path_str
                if not skill_dir.is_dir():
                    missing.append(path_str)
            if not missing:
                return (True, f"All {len(items)} skill paths valid")
            return (False, f"Missing: {', '.join(missing)}")
        except Exception as e:
            return (False, f"_index.yaml load error: {e}")

    def run_all_checks(self) -> list[dict[str, Any]]:
        """Run all checks in order.

        Returns:
            List of dicts with keys: check, passed, message.
        """
        checks = [
            ("python_version", self.check_python_version),
            ("pyyaml_installed", self.check_pyyaml_installed),
            ("kernel_files_present", self.check_kernel_files_present),
            ("graph_loadable", self.check_graph_loadable),
            ("skill_paths", self.check_skill_paths),
        ]
        results = []
        for name, func in checks:
            passed, message = func()
            results.append({"check": name, "passed": passed, "message": message})
        return results

    def print_results(self, results: list[dict[str, Any]]) -> int:
        """Print formatted results and return exit code.

        Args:
            results: List of check result dicts.

        Returns:
            0 if all checks pass, 1 if any fail.
        """
        all_pass = True
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            if not r["passed"]:
                all_pass = False
            print(f"  [{status}] {r['check']}: {r['message']}")
        if all_pass:
            print("\nAll checks passed!")
        else:
            print("\nSome checks failed. Please fix the issues above.")
        return 0 if all_pass else 1


if __name__ == "__main__":
    checker = SetupChecker()
    results = checker.run_all_checks()
    exit_code = checker.print_results(results)
    sys.exit(exit_code)
