"""Migration 001: Ensure state.yaml has all required fields."""

from pathlib import Path

import yaml

from kernel.migrations.base import Migration


class M001InitialSchema(Migration):
    """Ensure state.yaml has all required fields with default values."""

    version: str = "0.1.0"
    description: str = "Ensure state.yaml has all required fields"

    REQUIRED_FIELDS: dict = {
        "current_node": "init",
        "iteration_count": 0,
        "status": "idle",
        "goal": "",
        "errors": [],
        "node_visits": {},
        "max_iterations": 30,
        "complexity": "auto",
    }

    def check(self, kernel_root: Path) -> bool:
        """Return True if any required field is missing from state.yaml.

        Args:
            kernel_root: The root directory of the kernel project.

        Returns:
            True if migration needs to be applied.
        """
        state_path = kernel_root / "kernel" / "state.yaml"
        if not state_path.exists():
            return True
        data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        return any(field not in data for field in self.REQUIRED_FIELDS)

    def up(self, kernel_root: Path) -> None:
        """Add missing required fields to state.yaml.

        Args:
            kernel_root: The root directory of the kernel project.
        """
        state_path = kernel_root / "kernel" / "state.yaml"
        if state_path.exists():
            data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        else:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
        for field, default in self.REQUIRED_FIELDS.items():
            if field not in data:
                data[field] = default
        state_path.write_text(yaml.safe_dump(data, default_flow_style=False), encoding="utf-8")

    def down(self, kernel_root: Path) -> None:
        """No-op: cannot safely remove fields.

        Args:
            kernel_root: The root directory of the kernel project.
        """
