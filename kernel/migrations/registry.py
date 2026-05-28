"""Migration registry holding all available migrations in order."""

from kernel.migrations.base import Migration
from kernel.migrations.m001_initial_schema import M001InitialSchema
from kernel.migrations.m002_add_provider_fields import M002AddProviderFields

MIGRATIONS: list[type[Migration]] = [M001InitialSchema, M002AddProviderFields]


def get_pending_migrations(current_version: str) -> list[type[Migration]]:
    """Return migrations whose version is greater than current_version.

    Args:
        current_version: The current migration version string (e.g., '0.0.0').

    Returns:
        List of migration classes that still need to be applied.
    """
    current_tuple = tuple(int(x) for x in current_version.split("."))
    return [
        m
        for m in MIGRATIONS
        if tuple(int(x) for x in m.version.split(".")) > current_tuple
    ]
