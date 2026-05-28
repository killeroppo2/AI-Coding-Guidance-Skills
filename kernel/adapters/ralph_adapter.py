"""Ralph integration adapter.

Bridges between the kernel's TaskManager format (memory/tasks.yaml)
and Ralph's prd.json format for autonomous execution.
"""

import re
from typing import Any


class RalphAdapter:
    """Converts between kernel task format and Ralph prd.json format."""

    def export_to_prd_json(self, tasks: list[dict], goal: str) -> dict[str, Any]:
        """Convert kernel tasks to Ralph's prd.json structure.

        Args:
            tasks: List of kernel task dicts (id, title, description, status, dependencies).
            goal: The project goal string.

        Returns:
            A dict conforming to Ralph's prd.json format.
        """
        branch_name = "ralph/" + self._to_kebab_case(goal)
        user_stories = []
        for i, task in enumerate(tasks):
            story_id = f"US-{i + 1:03d}"
            title = task.get("title", "")
            description = task.get("description", "")
            if not description:
                description = f"As a developer, I want {title}"
            acceptance_criteria = task.get("acceptance_criteria", [])
            if not acceptance_criteria:
                acceptance_criteria = [f"{title} is complete", "Typecheck passes"]
            elif "Typecheck passes" not in acceptance_criteria:
                acceptance_criteria = list(acceptance_criteria) + ["Typecheck passes"]
            priority = i + 1
            passes = task.get("status") == "done"
            user_stories.append({
                "id": story_id,
                "title": title,
                "description": description,
                "acceptanceCriteria": acceptance_criteria,
                "priority": priority,
                "passes": passes,
                "notes": "",
            })
        return {
            "project": self._derive_project_name(goal),
            "branchName": branch_name,
            "description": goal,
            "userStories": user_stories,
        }

    def import_from_prd_json(self, prd_data: dict[str, Any]) -> list[dict]:
        """Convert Ralph's prd.json userStories to kernel task format.

        Args:
            prd_data: Dict conforming to Ralph's prd.json format.

        Returns:
            List of kernel task dicts.
        """
        user_stories = prd_data.get("userStories", [])
        # Sort by priority (stable sort preserves input order as tie-breaker)
        sorted_stories = sorted(
            user_stories, key=lambda s: s.get("priority", 1)
        )
        tasks = []
        # Track the last task index that had a strictly lower priority
        last_lower_priority_idx: int | None = None
        prev_priority: int | None = None
        for i, story in enumerate(sorted_stories):
            task_id = f"T-{i + 1:03d}"
            status = "done" if story.get("passes", False) else "pending"
            dependencies: list[str] = []
            current_priority = story.get("priority", 1)

            if i > 0 and prev_priority is not None:
                if current_priority > prev_priority:
                    # Priority is strictly greater: depend on the last task
                    # with the previous (lower) priority value
                    dependencies = [f"T-{i:03d}"]
                    last_lower_priority_idx = i - 1
                elif current_priority == prev_priority and last_lower_priority_idx is not None:
                    # Same priority as previous: parallel tasks, depend on the
                    # last task with a strictly lower priority
                    dependencies = [f"T-{last_lower_priority_idx + 1:03d}"]

            prev_priority = current_priority
            tasks.append({
                "id": task_id,
                "title": story.get("title", ""),
                "description": story.get("description", ""),
                "status": status,
                "dependencies": dependencies,
            })
        return tasks

    def _to_kebab_case(self, text: str) -> str:
        """Convert a string to kebab-case.

        Args:
            text: Input string.

        Returns:
            Kebab-case version of the string.
        """
        # Lowercase, replace spaces/underscores with hyphens, remove special chars
        name = text.lower().strip()
        name = re.sub(r"[_\s]+", "-", name)
        name = re.sub(r"[^a-z0-9-]", "", name)
        # Collapse multiple hyphens
        name = re.sub(r"-+", "-", name)
        name = name.strip("-")
        return name[:50]

    def _derive_project_name(self, goal: str) -> str:
        """Derive a project name from the goal string.

        Takes the first few meaningful words from the goal.

        Args:
            goal: The goal string.

        Returns:
            A short project name.
        """
        # Take meaningful words, title-case them
        words = re.sub(r"[^a-zA-Z0-9\s]", "", goal).split()
        # Filter out very short words (articles, prepositions) unless they're the only ones
        meaningful = [w for w in words if len(w) > 2] or words
        # Take first 3 words, title-case
        name_parts = meaningful[:3]
        return "".join(w.capitalize() for w in name_parts)
