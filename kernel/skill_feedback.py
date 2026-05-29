"""Learning feedback store - 以战养战 (use battle to nourish battle)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class SkillFeedbackStore:
    """Record and query skill outcome data for learning-based routing."""

    def __init__(self, memory_dir: str) -> None:
        """Initialize the feedback store.

        Args:
            memory_dir: Path to the memory directory.
        """
        self._path = Path(memory_dir) / "skill_feedback.jsonl"

    def record(
        self,
        node_id: str,
        skills_used: list[str],
        outcome: str,
        goal_type: str,
    ) -> None:
        """Append a feedback entry to the store.

        Args:
            node_id: The graph node where the skills were used.
            skills_used: List of skill names that were active.
            outcome: Result of the iteration ('success' or 'failed').
            goal_type: The type of goal being worked on.
        """
        entry = {
            "node_id": node_id,
            "skills_used": skills_used,
            "outcome": outcome,
            "goal_type": goal_type,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self._prune()

    def get_recommendations(
        self, node_id: str, goal_type: str, top_n: int = 3
    ) -> list[str]:
        """Get recommended skills based on historical success rates.

        Args:
            node_id: The graph node to get recommendations for.
            goal_type: The goal type to filter by.
            top_n: Maximum number of recommendations to return.

        Returns:
            List of skill names sorted by success rate (descending).
        """
        entries = self._read_entries()

        # Filter by node_id and goal_type
        filtered = [
            e for e in entries
            if e.get("node_id") == node_id and e.get("goal_type") == goal_type
        ]

        # Compute success/total per skill
        skill_stats: dict[str, dict[str, int]] = {}
        for entry in filtered:
            for skill in entry.get("skills_used", []):
                if skill not in skill_stats:
                    skill_stats[skill] = {"successes": 0, "total": 0}
                skill_stats[skill]["total"] += 1
                if entry.get("outcome") == "success":
                    skill_stats[skill]["successes"] += 1

        # Filter: >= 3 data points AND >= 60% success rate
        qualified: list[tuple[str, float]] = []
        for skill, stats in skill_stats.items():
            if stats["total"] >= 3:
                rate = stats["successes"] / stats["total"]
                if rate >= 0.6:
                    qualified.append((skill, rate))

        # Sort by success rate descending
        qualified.sort(key=lambda x: x[1], reverse=True)
        return [skill for skill, _ in qualified[:top_n]]

    def get_stats(self) -> dict:
        """Return summary statistics about the feedback store.

        Returns:
            Dict with total_entries, unique_skills, unique_nodes, top_skills.
        """
        entries = self._read_entries()

        all_skills: set[str] = set()
        all_nodes: set[str] = set()
        skill_stats: dict[str, dict[str, int]] = {}

        for entry in entries:
            all_nodes.add(entry.get("node_id", ""))
            for skill in entry.get("skills_used", []):
                all_skills.add(skill)
                if skill not in skill_stats:
                    skill_stats[skill] = {"successes": 0, "total": 0}
                skill_stats[skill]["total"] += 1
                if entry.get("outcome") == "success":
                    skill_stats[skill]["successes"] += 1

        # Top 5 skills by success rate (must have at least 1 entry)
        rated: list[tuple[str, float]] = []
        for skill, stats in skill_stats.items():
            if stats["total"] > 0:
                rate = stats["successes"] / stats["total"]
                rated.append((skill, rate))
        rated.sort(key=lambda x: x[1], reverse=True)
        top_skills = [skill for skill, _ in rated[:5]]

        return {
            "total_entries": len(entries),
            "unique_skills": len(all_skills),
            "unique_nodes": len(all_nodes),
            "top_skills": top_skills,
        }

    def _prune(self, max_entries: int = 500) -> None:
        """Keep only the last max_entries lines in the file.

        Args:
            max_entries: Maximum number of entries to retain.
        """
        if not self._path.exists():
            return

        lines = self._path.read_text().strip().split("\n")
        if len(lines) > max_entries:
            kept = lines[-max_entries:]
            self._path.write_text("\n".join(kept) + "\n")

    def _read_entries(self) -> list[dict]:
        """Read all valid JSONL entries from the store file."""
        if not self._path.exists():
            return []

        entries: list[dict] = []
        for line in self._path.read_text().strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
