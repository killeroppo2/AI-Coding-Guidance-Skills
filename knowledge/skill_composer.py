"""Skill composition for combining and applying skills.

This module handles composing multiple skills together and applying
them in the context of a development task.
"""

from pathlib import Path
from typing import Any

import yaml


def _estimate_tokens(text: str) -> int:
    """Estimate token count with CJK-awareness.

    CJK characters (U+4E00 to U+9FFF) tokenize to ~1.5 tokens each.
    ASCII/Latin text tokenizes to ~0.25 tokens per character.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ascii_chars = len(text) - cjk_chars
    return int(cjk_chars * 1.5 + ascii_chars * 0.25)


class SkillComposer:
    """Composes and applies skills from the knowledge base.

    Skills are reusable capability definitions that can be combined
    to handle complex development tasks.
    """

    def __init__(self, knowledge_store: Any) -> None:
        """Initialize the skill composer.

        Args:
            knowledge_store: A KnowledgeStore instance.
        """
        self.knowledge_store = knowledge_store

    def compose(self, skill_names: list, max_tokens: int | None = None) -> str:
        """Load each skill's SKILL.md content and combine into one prompt string.

        Prefixes each with a header (## Skill: {name}).

        Args:
            skill_names: List of skill names to compose.
            max_tokens: Optional token budget. If set, estimate tokens as
                len(content)//4 and stop adding skills once budget exceeded.

        Returns:
            Combined prompt string with all skill content.

        Raises:
            ValueError: If any skill is missing (blocking errors only).
        """
        issues = self.validate_composition(skill_names)
        # Only raise on blocking errors (not warnings)
        blocking = [i for i in issues if not i.startswith("Warning:")]
        if blocking:
            raise ValueError(f"Composition validation failed: {'; '.join(blocking)}")

        ordered = self.resolve_order(skill_names)
        parts = []
        total_tokens = 0
        excluded = []

        for name in ordered:
            content = self.get_skill_content(name)
            section = f"## Skill: {name}\n\n{content}"
            if max_tokens is not None:
                estimated = _estimate_tokens(section)
                if total_tokens + estimated > max_tokens:
                    excluded.append(name)
                    continue
                total_tokens += estimated
            parts.append(section)

        # If we have excluded skills due to token budget and there are remaining
        if max_tokens is not None and excluded:
            # Also collect any remaining skills not yet processed
            result = "\n\n---\n\n".join(parts)
            result += (
                f"\n\n---\n\n## [TRUNCATED]\n\n"
                f"The following skills were excluded due to token budget: "
                f"{', '.join(excluded)}"
            )
            return result

        return "\n\n---\n\n".join(parts)

    def validate_composition(self, skill_names: list) -> list:
        """Return list of issues (missing skills, conflict warnings, etc.).

        Args:
            skill_names: List of skill names to validate.

        Returns:
            List of issue strings. Empty if all valid.
        """
        issues = []
        if not skill_names:
            issues.append("No skills specified")
            return issues
        for name in skill_names:
            try:
                self.knowledge_store.get_skill(name)
            except KeyError:
                issues.append(f"Skill not found: {name}")

        # Add conflict warnings (non-blocking)
        if not issues:
            conflicts = self.detect_conflicts(skill_names)
            issues.extend(conflicts)

        return issues

    def detect_conflicts(self, skill_names: list) -> list[str]:
        """Detect potential incompatibilities between skills.

        If skill A is not in skill B's composable_with AND skill B is not in
        skill A's composable_with, they have no known compatibility relationship.
        Return a warning for each such pair.

        Args:
            skill_names: List of skill names to check.

        Returns:
            List of warning strings about potentially incompatible skill pairs.
        """
        warnings = []
        # Build a map of composable_with for each skill in the list
        composable_map: dict[str, list[str]] = {}
        for name in skill_names:
            try:
                skill = self.knowledge_store.get_skill(name)
                composable_map[name] = skill.get("composable_with", [])
            except KeyError:
                composable_map[name] = []

        # Check each pair
        checked = set()
        for i, skill_a in enumerate(skill_names):
            for j, skill_b in enumerate(skill_names):
                if i >= j:
                    continue
                pair = (skill_a, skill_b)
                if pair in checked:
                    continue
                checked.add(pair)

                a_composable = composable_map.get(skill_a, [])
                b_composable = composable_map.get(skill_b, [])

                if skill_b not in a_composable and skill_a not in b_composable:
                    warnings.append(
                        f"Warning: {skill_a} and {skill_b} have no known compatibility relationship"
                    )

        return warnings

    def compose_for_phase(self, phase_name: str) -> str:
        """Auto-select and compose skills for a given workflow phase.

        Reads the workflow section of skills/_index.yaml to get the list of
        skills for the given phase, then composes them.

        Args:
            phase_name: One of the workflow phases (e.g., 'execution_phase',
                'idea_phase').

        Returns:
            Composed prompt string for all skills in that phase.

        Raises:
            ValueError: If phase_name is not found in the workflow definition.
        """
        index_path = self.knowledge_store.skills_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                index_data = yaml.safe_load(f) or {}
        else:
            index_data = {}

        workflow = index_data.get("workflow", {})
        # Also check core_workflow and community_workflow for new format
        if not workflow:
            core_wf = index_data.get("core_workflow", {})
            community_wf = index_data.get("community_workflow", {})
            workflow = {**core_wf, **community_wf}
        if phase_name not in workflow:
            available = list(workflow.keys())
            raise ValueError(
                f"Phase '{phase_name}' not found in workflow. Available phases: {available}"
            )

        skill_names = workflow[phase_name]
        return self.compose(skill_names)

    def get_skill_content(self, skill_name: str) -> str:
        """Read the SKILL.md file for a given skill.

        Args:
            skill_name: The skill name.

        Returns:
            The content of the SKILL.md file.

        Raises:
            FileNotFoundError: If the SKILL.md file does not exist.
        """
        skill = self.knowledge_store.get_skill(skill_name)
        skill_path = Path(skill.get("path", skill_name))

        # Try relative to knowledge_root/skills/
        skill_md = self.knowledge_store.skills_dir / skill_path / "SKILL.md"
        if skill_md.exists():
            content: str = skill_md.read_text(encoding="utf-8")
            return content

        # Try the path directly (for skills at repo root level)
        # Go up from knowledge dir to find repo root
        repo_root = self.knowledge_store.knowledge_root.parent
        alt_path = repo_root / skill_path / "SKILL.md"
        if alt_path.exists():
            content = alt_path.read_text(encoding="utf-8")
            return content

        raise FileNotFoundError(
            f"SKILL.md not found for skill '{skill_name}' at {skill_md} or {alt_path}"
        )

    def resolve_order(self, skill_names: list) -> list:
        """Resolve ordering for skill composition based on composable_with.

        Skills that are referenced in more other skills' composable_with lists
        are considered more foundational and placed earlier. Uses stable sort
        to maintain original order for equal scores.

        Handles cycles gracefully by returning original order if detected.

        Args:
            skill_names: List of skill names.

        Returns:
            Ordered list of skill names (foundational first).
        """
        if len(skill_names) <= 1:
            return list(skill_names)

        # Build composable_with map for skills in the input list
        composable_map: dict[str, list[str]] = {}
        for name in skill_names:
            try:
                skill = self.knowledge_store.get_skill(name)
                composable_map[name] = skill.get("composable_with", [])
            except KeyError:
                composable_map[name] = []

        # Count how many other input skills reference each skill in their
        # composable_with. Higher count = more foundational.
        input_set = set(skill_names)
        foundation_score: dict[str, int] = {name: 0 for name in skill_names}

        for name in skill_names:
            for dep in composable_map.get(name, []):
                if dep in input_set:
                    # 'name' declares compatibility with 'dep',
                    # so 'dep' is more foundational
                    foundation_score[dep] += 1

        # Check for cycles: if A composable_with B and B composable_with A,
        # and they have equal scores, that's fine (stable sort preserves order).
        # But for a true topological cycle check, we verify we can produce
        # a valid ordering using Kahn's algorithm.
        # Build a directed graph: edge from dep -> name means dep should come
        # before name (because name lists dep in composable_with)
        in_degree: dict[str, int] = {name: 0 for name in skill_names}
        graph: dict[str, list[str]] = {name: [] for name in skill_names}

        for name in skill_names:
            for dep in composable_map.get(name, []):
                if dep in input_set:
                    graph[dep].append(name)
                    in_degree[name] += 1

        # Kahn's algorithm for cycle detection
        queue = [n for n in skill_names if in_degree[n] == 0]
        sorted_count = 0
        for node in queue:
            sorted_count += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if sorted_count != len(skill_names):
            # Cycle detected, return original order
            return list(skill_names)

        # Sort by foundation_score descending, maintaining original order for ties
        indexed = list(enumerate(skill_names))
        indexed.sort(key=lambda x: (-foundation_score[x[1]], x[0]))
        return [name for _, name in indexed]
