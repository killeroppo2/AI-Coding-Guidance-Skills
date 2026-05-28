"""Skill factory for programmatic skill creation.

This module provides the SkillFactory class which creates new skills
(directory + SKILL.md + register in _index.yaml) with validation
for kebab-case naming.
"""

import re
from pathlib import Path

from knowledge.store import KnowledgeStore


class SkillFactory:
    """Creates and registers new skills in the knowledge base.

    Handles directory creation, SKILL.md generation, and index registration
    with kebab-case name validation.
    """

    def __init__(self, knowledge_dir: str) -> None:
        """Initialize the skill factory.

        Args:
            knowledge_dir: Path to the knowledge/ directory.
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.store = KnowledgeStore(knowledge_dir)

    def validate_skill_name(self, name: str) -> tuple[bool, str]:
        """Validate that a skill name is valid kebab-case.

        Valid names: lowercase a-z0-9 with hyphens allowed in the middle.
        Rejects: empty, uppercase, spaces, starts/ends with hyphen, double hyphens,
        special characters.

        Args:
            name: The skill name to validate.

        Returns:
            Tuple of (is_valid, reason). reason is empty string if valid.
        """
        if not name:
            return (False, "Skill name cannot be empty")

        if name != name.lower():
            return (False, "Skill name must be lowercase")

        if " " in name:
            return (False, "Skill name cannot contain spaces")

        if name.startswith("-"):
            return (False, "Skill name cannot start with a hyphen")

        if name.endswith("-"):
            return (False, "Skill name cannot end with a hyphen")

        if "--" in name:
            return (False, "Skill name cannot contain double hyphens")

        if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
            return (
                False,
                "Skill name must be kebab-case"
                " (lowercase letters, digits, and single hyphens)",
            )

        return (True, "")

    def create_skill(self, name: str, description: str, content: str,
                     tags: list[str] | None = None) -> Path:
        """Create a new skill with directory, SKILL.md, and index registration.

        Args:
            name: Skill name (must be valid kebab-case).
            description: Short description of the skill.
            content: Main content for the SKILL.md file.
            tags: Optional list of tags for the skill.

        Returns:
            Path to the created skill directory.

        Raises:
            ValueError: If the skill name is invalid.
        """
        valid, reason = self.validate_skill_name(name)
        if not valid:
            raise ValueError(f"Invalid skill name '{name}': {reason}")

        skill_dir = self.knowledge_dir.parent / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(f"# {name}\n\n{description}\n\n{content}", encoding="utf-8")

        self.store.add_skill(name, description, tags or [], name)

        return skill_dir

    def create_skill_from_template(self, name: str, description: str,
                                   sections: dict[str, str],
                                   tags: list[str] | None = None) -> Path:
        """Create a skill from named sections.

        Builds SKILL.md content from a dict of sections, where each key becomes
        a ## heading and each value becomes the section body.

        Args:
            name: Skill name (must be valid kebab-case).
            description: Short description of the skill.
            sections: Dict mapping section names to content.
            tags: Optional list of tags for the skill.

        Returns:
            Path to the created skill directory.

        Raises:
            ValueError: If the skill name is invalid.
        """
        content_parts = []
        for section_name, section_content in sections.items():
            content_parts.append(f"## {section_name.title()}\n\n{section_content}\n")

        content = "\n".join(content_parts)
        return self.create_skill(name, description, content, tags)
