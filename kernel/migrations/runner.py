"""Migration runner: applies pending migrations and tracks version state."""

from pathlib import Path

from kernel.migrations.registry import get_pending_migrations

MIGRATION_VERSION_FILE = ".migration_version"


def get_current_version(kernel_root: Path) -> str:
    """Read the current migration version from the version file.

    Args:
        kernel_root: The root directory of the kernel project.

    Returns:
        The current version string, or '0.0.0' if the file does not exist.
    """
    version_path = kernel_root / "kernel" / MIGRATION_VERSION_FILE
    if not version_path.exists():
        return "0.0.0"
    return version_path.read_text(encoding="utf-8").strip()


def set_current_version(kernel_root: Path, version: str) -> None:
    """Write the current migration version to the version file.

    Args:
        kernel_root: The root directory of the kernel project.
        version: The version string to write.
    """
    version_path = kernel_root / "kernel" / MIGRATION_VERSION_FILE
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text(version + "\n", encoding="utf-8")


def run_pending_migrations(kernel_root: Path) -> list[str]:
    """Run all pending migrations and return the list of applied versions.

    Migrations whose ``check()`` returns False are considered already satisfied;
    the version marker advances past them but they are not included in the
    returned list.  Only migrations that actually executed ``up()`` are returned.

    Args:
        kernel_root: The root directory of the kernel project.

    Returns:
        List of version strings for migrations that actually mutated state.
    """
    current = get_current_version(kernel_root)
    pending = get_pending_migrations(current)
    applied: list[str] = []

    for migration_cls in pending:
        migration = migration_cls()
        if migration.check(kernel_root):
            try:
                migration.up(kernel_root)
            except Exception as exc:
                print(f"Migration {migration.version} ({migration.description}) failed: {exc}")
                raise
            applied.append(migration.version)
        set_current_version(kernel_root, migration.version)

    return applied
