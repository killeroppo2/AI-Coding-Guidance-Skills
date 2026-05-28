"""Migration 002: Add provider and model fields to state.yaml."""

from pathlib import Path

import yaml

from kernel.migrations.base import Migration


class M002AddProviderFields(Migration):
    """Add provider and model fields to state.yaml."""

    version: str = "0.2.0"
    description: str = "Add provider and model fields to state.yaml"

    def check(self, kernel_root: Path) -> bool:
        """Return True if provider or model field is missing from state.yaml.

        Args:
            kernel_root: The root directory of the kernel project.

        Returns:
            True if migration needs to be applied.
        """
        state_path = kernel_root / "kernel" / "state.yaml"
        if not state_path.exists():
            return True
        data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        return "provider" not in data or "model" not in data

    def up(self, kernel_root: Path) -> None:
        """Add provider and model fields to state.yaml if missing.

        Args:
            kernel_root: The root directory of the kernel project.
        """
        state_path = kernel_root / "kernel" / "state.yaml"
        if state_path.exists():
            data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        else:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
        if "provider" not in data:
            data["provider"] = "cli"
        if "model" not in data:
            data["model"] = None
        state_path.write_text(yaml.safe_dump(data, default_flow_style=False), encoding="utf-8")

    def down(self, kernel_root: Path) -> None:
        """Remove provider and model fields from state.yaml.

        Args:
            kernel_root: The root directory of the kernel project.
        """
        state_path = kernel_root / "kernel" / "state.yaml"
        if not state_path.exists():
            return
        data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
        data.pop("provider", None)
        data.pop("model", None)
        state_path.write_text(yaml.safe_dump(data, default_flow_style=False), encoding="utf-8")
