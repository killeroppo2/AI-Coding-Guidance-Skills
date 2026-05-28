"""Tests for the kernel migration system."""

from pathlib import Path

import pytest
import yaml

from kernel.migrations.base import Migration
from kernel.migrations.m001_initial_schema import M001InitialSchema
from kernel.migrations.m002_add_provider_fields import M002AddProviderFields
from kernel.migrations.registry import MIGRATIONS, get_pending_migrations
from kernel.migrations.runner import (
    get_current_version,
    run_pending_migrations,
    set_current_version,
)


class TestMigrationBase:
    """Tests for the abstract Migration base class."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Migration cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Migration()  # type: ignore[abstract]


class TestM001InitialSchema:
    """Tests for M001InitialSchema migration."""

    def test_check_returns_true_on_incomplete_state(self, tmp_path: Path) -> None:
        """check() returns True when state.yaml is missing required fields."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(yaml.safe_dump({"current_node": "init"}), encoding="utf-8")
        migration = M001InitialSchema()
        assert migration.check(tmp_path) is True

    def test_check_returns_true_on_missing_state(self, tmp_path: Path) -> None:
        """check() returns True when state.yaml does not exist."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        migration = M001InitialSchema()
        assert migration.check(tmp_path) is True

    def test_check_returns_false_on_complete_state(self, tmp_path: Path) -> None:
        """check() returns False when all required fields are present."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        complete_state = {
            "current_node": "init",
            "iteration_count": 0,
            "status": "idle",
            "goal": "",
            "errors": [],
            "node_visits": {},
            "max_iterations": 30,
            "complexity": "auto",
        }
        state_path.write_text(yaml.safe_dump(complete_state), encoding="utf-8")
        migration = M001InitialSchema()
        assert migration.check(tmp_path) is False

    def test_up_adds_missing_fields(self, tmp_path: Path) -> None:
        """up() adds missing required fields with defaults."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(
            yaml.safe_dump({"current_node": "plan", "status": "running"}),
            encoding="utf-8",
        )
        migration = M001InitialSchema()
        migration.up(tmp_path)

        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert data["current_node"] == "plan"  # preserved
        assert data["status"] == "running"  # preserved
        assert data["iteration_count"] == 0
        assert data["goal"] == ""
        assert data["errors"] == []
        assert data["node_visits"] == {}
        assert data["max_iterations"] == 30
        assert data["complexity"] == "auto"

    def test_up_creates_state_if_missing(self, tmp_path: Path) -> None:
        """up() creates state.yaml if it does not exist."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        migration = M001InitialSchema()
        migration.up(tmp_path)

        state_path = kernel_dir / "state.yaml"
        assert state_path.exists()
        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert data["current_node"] == "init"
        assert data["max_iterations"] == 30

    def test_down_is_noop(self, tmp_path: Path) -> None:
        """down() is a no-op and does not modify state.yaml."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        original = {"current_node": "init", "iteration_count": 0}
        state_path.write_text(yaml.safe_dump(original), encoding="utf-8")

        migration = M001InitialSchema()
        migration.down(tmp_path)

        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert data == original


class TestM002AddProviderFields:
    """Tests for M002AddProviderFields migration."""

    def test_check_returns_true_when_fields_missing(self, tmp_path: Path) -> None:
        """check() returns True when provider or model fields are missing."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(
            yaml.safe_dump({"current_node": "init", "status": "idle"}),
            encoding="utf-8",
        )
        migration = M002AddProviderFields()
        assert migration.check(tmp_path) is True

    def test_check_returns_false_when_fields_present(self, tmp_path: Path) -> None:
        """check() returns False when both provider and model are present."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(yaml.safe_dump({"provider": "cli", "model": None}), encoding="utf-8")
        migration = M002AddProviderFields()
        assert migration.check(tmp_path) is False

    def test_up_adds_provider_and_model(self, tmp_path: Path) -> None:
        """up() adds provider and model fields to state.yaml."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(yaml.safe_dump({"current_node": "init"}), encoding="utf-8")
        migration = M002AddProviderFields()
        migration.up(tmp_path)

        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert data["provider"] == "cli"
        assert data["model"] is None
        assert data["current_node"] == "init"  # preserved

    def test_up_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        """up() does not overwrite existing provider/model values."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(
            yaml.safe_dump({"provider": "openai", "model": "gpt-4o"}),
            encoding="utf-8",
        )
        migration = M002AddProviderFields()
        migration.up(tmp_path)

        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"

    def test_down_removes_provider_and_model(self, tmp_path: Path) -> None:
        """down() removes provider and model fields from state.yaml."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(
            yaml.safe_dump({"current_node": "init", "provider": "cli", "model": None}),
            encoding="utf-8",
        )
        migration = M002AddProviderFields()
        migration.down(tmp_path)

        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        assert "provider" not in data
        assert "model" not in data
        assert data["current_node"] == "init"  # preserved

    def test_down_handles_missing_state(self, tmp_path: Path) -> None:
        """down() does nothing when state.yaml does not exist."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        migration = M002AddProviderFields()
        migration.down(tmp_path)  # should not raise


class TestRunner:
    """Tests for the migration runner functions."""

    def test_get_current_version_returns_default(self, tmp_path: Path) -> None:
        """get_current_version() returns '0.0.0' when no file exists."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        assert get_current_version(tmp_path) == "0.0.0"

    def test_get_current_version_reads_from_file(self, tmp_path: Path) -> None:
        """get_current_version() reads version from the version file."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        version_file = kernel_dir / ".migration_version"
        version_file.write_text("0.1.0\n", encoding="utf-8")
        assert get_current_version(tmp_path) == "0.1.0"

    def test_set_current_version_writes_file(self, tmp_path: Path) -> None:
        """set_current_version() writes the version to the version file."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        set_current_version(tmp_path, "0.2.0")
        version_file = kernel_dir / ".migration_version"
        assert version_file.exists()
        assert version_file.read_text(encoding="utf-8").strip() == "0.2.0"

    def test_run_pending_migrations_applies_all(self, tmp_path: Path) -> None:
        """run_pending_migrations() applies all pending migrations from 0.0.0."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(yaml.safe_dump({"current_node": "init"}), encoding="utf-8")

        applied = run_pending_migrations(tmp_path)

        assert applied == ["0.1.0", "0.2.0"]
        data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
        # M001 fields
        assert data["max_iterations"] == 30
        assert data["complexity"] == "auto"
        # M002 fields
        assert data["provider"] == "cli"
        assert data["model"] is None
        # Version updated
        assert get_current_version(tmp_path) == "0.2.0"

    def test_run_pending_migrations_skips_applied(self, tmp_path: Path) -> None:
        """run_pending_migrations() advances version but does not list skipped migrations."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(
            yaml.safe_dump({"current_node": "init", "provider": "cli", "model": None}),
            encoding="utf-8",
        )
        set_current_version(tmp_path, "0.1.0")

        applied = run_pending_migrations(tmp_path)

        # M002 check() returns False because fields exist, so it's not in applied
        assert applied == []
        # But the version marker still advances past the migration
        assert get_current_version(tmp_path) == "0.2.0"

    def test_run_pending_migrations_none_pending(self, tmp_path: Path) -> None:
        """run_pending_migrations() returns empty list when all applied."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(yaml.safe_dump({"current_node": "init"}), encoding="utf-8")
        set_current_version(tmp_path, "0.2.0")

        applied = run_pending_migrations(tmp_path)

        assert applied == []

    def test_run_pending_migrations_error_in_up(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """run_pending_migrations() prints diagnostic and re-raises on up() failure."""
        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        state_path = kernel_dir / "state.yaml"
        state_path.write_text(yaml.safe_dump({"current_node": "init"}), encoding="utf-8")

        # Patch M001's up() to raise an error
        def bad_up(self: object, kernel_root: Path) -> None:
            raise RuntimeError("disk full")

        monkeypatch.setattr(M001InitialSchema, "up", bad_up)

        with pytest.raises(RuntimeError, match="disk full"):
            run_pending_migrations(tmp_path)

        captured = capsys.readouterr()
        assert "Migration 0.1.0" in captured.out
        assert "disk full" in captured.out
        # Version should NOT have advanced past the failed migration
        assert get_current_version(tmp_path) == "0.0.0"


class TestRegistry:
    """Tests for the migration registry."""

    def test_migrations_list_is_ordered(self) -> None:
        """MIGRATIONS list contains migrations in version order."""
        assert len(MIGRATIONS) == 2
        assert MIGRATIONS[0].version == "0.1.0"
        assert MIGRATIONS[1].version == "0.2.0"

    def test_get_pending_from_zero(self) -> None:
        """get_pending_migrations('0.0.0') returns all migrations."""
        pending = get_pending_migrations("0.0.0")
        assert len(pending) == 2
        assert pending[0] is M001InitialSchema
        assert pending[1] is M002AddProviderFields

    def test_get_pending_from_first(self) -> None:
        """get_pending_migrations('0.1.0') returns only second migration."""
        pending = get_pending_migrations("0.1.0")
        assert len(pending) == 1
        assert pending[0] is M002AddProviderFields

    def test_get_pending_from_latest(self) -> None:
        """get_pending_migrations('0.2.0') returns empty list."""
        pending = get_pending_migrations("0.2.0")
        assert pending == []

    def test_get_pending_from_future(self) -> None:
        """get_pending_migrations('1.0.0') returns empty list."""
        pending = get_pending_migrations("1.0.0")
        assert pending == []
