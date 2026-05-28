"""Knowledge store for rules, skills, and patterns.

This module provides read/write access to the kernel's knowledge base,
including rules (manual and learned), skills, and patterns.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml


class KnowledgeStore:
    """Manages the kernel's knowledge base on the filesystem.

    The knowledge base is organized into:
    - rules/: Manual and learned rules that constrain behavior
    - skills/: Reusable skill definitions
    - patterns/: Code and architecture patterns
    """

    def __init__(self, knowledge_dir: str, skills_dir: str | None = None) -> None:
        """Initialize the knowledge store.

        Args:
            knowledge_dir: Path to the knowledge/ directory.
            skills_dir: Optional path to the skills/ directory. Defaults to
                the skills/ directory at the project root (sibling of knowledge/).
        """
        self.knowledge_root = Path(knowledge_dir)
        self.rules_dir = self.knowledge_root / "rules"
        if skills_dir is not None:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = self.knowledge_root.parent / "skills"
        self.patterns_dir = self.knowledge_root / "patterns"

    def _load_index(self, category_dir: Path) -> dict:
        """Load the _index.yaml for a given category directory.

        Args:
            category_dir: Path to the category directory.

        Returns:
            The parsed index dict with 'items' list.
        """
        index_path = category_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # Support both legacy "items" and new "core_items"/"community_items"
            if "items" not in data:
                core = data.get("core_items", [])
                community = data.get("community_items", [])
                data["items"] = core + community
            return data
        return {"items": []}

    def _save_index(self, category_dir: Path, index_data: dict) -> None:
        """Save the _index.yaml for a given category directory.

        Args:
            category_dir: Path to the category directory.
            index_data: The index dict to save.
        """
        category_dir.mkdir(parents=True, exist_ok=True)
        index_path = category_dir / "_index.yaml"
        with open(index_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(index_data, f, default_flow_style=False, allow_unicode=True)

    def add_rule(self, rule: dict, learned: bool = False) -> None:
        """Add rule to manual/ or learned/ as YAML file, update _index.yaml.

        Args:
            rule: Rule dict with keys: name, description, content, tags, source.
            learned: If True, add to learned/ subdirectory. Otherwise manual/.
        """
        name = rule.get("name", "unnamed")
        safe_name = name.replace(" ", "_").lower()
        subdir = "learned" if learned else "manual"
        target_dir = self.rules_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write rule file
        rule_file = target_dir / f"{safe_name}.yaml"
        rule_data = dict(rule)
        rule_data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        with open(rule_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(rule_data, f, default_flow_style=False, allow_unicode=True)

        # Update index
        index = self._load_index(self.rules_dir)
        # Remove existing entry with same name if present
        index["items"] = [
            item for item in index["items"] if item.get("name") != name
        ]
        index["items"].append({
            "name": name,
            "path": f"{subdir}/{safe_name}.yaml",
            "tags": rule.get("tags", []),
            "description": rule.get("description", ""),
            "created_at": rule_data["created_at"],
        })
        self._save_index(self.rules_dir, index)

    def get_rules(self, filter_tags: list | None = None) -> list:
        """Get all rules, optionally filtered by tags.

        Args:
            filter_tags: If provided, only return rules with at least one matching tag.

        Returns:
            List of rule dicts.
        """
        index = self._load_index(self.rules_dir)
        items = index.get("items", [])
        if filter_tags is None:
            return items
        return [
            item for item in items
            if any(tag in item.get("tags", []) for tag in filter_tags)
        ]

    def add_skill(self, name: str, description: str, tags: list | None = None,
                  path: str | None = None) -> None:
        """Register a skill in _index.yaml.

        Args:
            name: Skill name.
            description: Skill description.
            tags: Optional list of tags.
            path: Optional path to the skill directory.
        """
        if tags is None:
            tags = []
        if path is None:
            path = name

        index = self._load_index(self.skills_dir)
        # Remove existing entry with same name
        index["items"] = [
            item for item in index["items"] if item.get("name") != name
        ]
        index["items"].append({
            "name": name,
            "path": path,
            "description": description,
            "tags": tags,
            "composable_with": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_index(self.skills_dir, index)

    def get_skill(self, name: str) -> dict:
        """Get skill metadata from index.

        Args:
            name: The skill name.

        Returns:
            The skill dict from the index.

        Raises:
            KeyError: If skill is not found.
        """
        index = self._load_index(self.skills_dir)
        for item in index.get("items", []):
            if item.get("name") == name:
                return item
        raise KeyError(f"Skill not found: {name}")

    def list_skills(self, tags: list | None = None) -> list:
        """List all skills, optionally filtered by tags.

        Args:
            tags: If provided, only return skills with at least one matching tag.

        Returns:
            List of skill dicts.
        """
        index = self._load_index(self.skills_dir)
        items = index.get("items", [])
        if tags is None:
            return items
        return [
            item for item in items
            if any(tag in item.get("tags", []) for tag in tags)
        ]

    def list_core_skills(self) -> list:
        """List only core skills (those defined in core_items).

        Returns:
            List of core skill dicts, or all items if using legacy format.
        """
        index_path = self.skills_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if "core_items" in data:
                return data["core_items"]
            # Legacy format: all items are considered core
            return data.get("items", [])
        return []

    def add_pattern(self, pattern: dict) -> None:
        """Add a pattern, update _index.yaml.

        Args:
            pattern: Pattern dict with keys: name, description, content, tags, context.
        """
        name = pattern.get("name", "unnamed")
        safe_name = name.replace(" ", "_").lower()
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

        # Write pattern file
        pattern_file = self.patterns_dir / f"{safe_name}.yaml"
        pattern_data = dict(pattern)
        pattern_data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        with open(pattern_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(pattern_data, f, default_flow_style=False, allow_unicode=True)

        # Update index
        index = self._load_index(self.patterns_dir)
        # Remove existing entry with same name
        index["items"] = [
            item for item in index["items"] if item.get("name") != name
        ]
        index["items"].append({
            "name": name,
            "path": f"{safe_name}.yaml",
            "tags": pattern.get("tags", []),
            "description": pattern.get("description", ""),
            "created_at": pattern_data["created_at"],
        })
        self._save_index(self.patterns_dir, index)

    def get_patterns(self, filter_tags: list | None = None) -> list:
        """Get patterns, optionally filtered by tags.

        Args:
            filter_tags: If provided, only return patterns with at least one matching tag.

        Returns:
            List of pattern dicts.
        """
        index = self._load_index(self.patterns_dir)
        items = index.get("items", [])
        if filter_tags is None:
            return items
        return [
            item for item in items
            if any(tag in item.get("tags", []) for tag in filter_tags)
        ]

    def rebuild_index(self, category: str) -> None:
        """Rebuild _index.yaml for given category by scanning the directory.

        Args:
            category: One of 'rules', 'skills', 'patterns'.

        Raises:
            ValueError: If category is not valid.
        """
        if category == "rules":
            category_dir = self.rules_dir
        elif category == "skills":
            category_dir = self.skills_dir
        elif category == "patterns":
            category_dir = self.patterns_dir
        else:
            raise ValueError(
                f"Invalid category: {category}."
                " Must be one of: rules, skills, patterns"
            )

        items = []
        if category == "rules":
            # Scan manual/ and learned/ subdirectories
            for subdir in ["manual", "learned"]:
                sub_path = category_dir / subdir
                if sub_path.exists():
                    for yaml_file in sorted(sub_path.glob("*.yaml")):
                        with open(yaml_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        items.append({
                            "name": data.get("name", yaml_file.stem),
                            "path": f"{subdir}/{yaml_file.name}",
                            "tags": data.get("tags", []),
                            "description": data.get("description", ""),
                            "created_at": data.get("created_at", ""),
                        })
        elif category == "skills":
            # Scan for _index entries based on skill directories
            # Skills are registered via add_skill, so just scan index if it exists
            # For rebuild, we look at subdirectories with SKILL.md
            if category_dir.exists():
                for item_path in sorted(category_dir.iterdir()):
                    if item_path.is_dir() and (item_path / "SKILL.md").exists():
                        items.append({
                            "name": item_path.name,
                            "path": item_path.name,
                            "description": "",
                            "tags": [],
                            "composable_with": [],
                            "created_at": "",
                        })
        elif category == "patterns":
            if category_dir.exists():
                for yaml_file in sorted(category_dir.glob("*.yaml")):
                    if yaml_file.name == "_index.yaml":
                        continue
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    items.append({
                        "name": data.get("name", yaml_file.stem),
                        "path": yaml_file.name,
                        "tags": data.get("tags", []),
                        "description": data.get("description", ""),
                        "created_at": data.get("created_at", ""),
                    })

        self._save_index(category_dir, {"items": items})
