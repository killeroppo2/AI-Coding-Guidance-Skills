"""Base migration class defining the migration interface."""

import abc
from pathlib import Path


class Migration(abc.ABC):
    """Abstract base class for data migrations.

    Subclasses must define version, description, and implement
    the up(), down(), and check() methods.
    """

    version: str
    """Semver version string for this migration (e.g., '0.1.0')."""

    description: str
    """Human-readable description of what this migration does."""

    @abc.abstractmethod
    def up(self, kernel_root: Path) -> None:
        """Apply the migration forward.

        Args:
            kernel_root: The root directory of the kernel project.
        """

    @abc.abstractmethod
    def down(self, kernel_root: Path) -> None:
        """Revert the migration.

        Args:
            kernel_root: The root directory of the kernel project.
        """

    @abc.abstractmethod
    def check(self, kernel_root: Path) -> bool:
        """Check whether this migration needs to be applied.

        Args:
            kernel_root: The root directory of the kernel project.

        Returns:
            True if the migration needs to be applied, False otherwise.
        """
