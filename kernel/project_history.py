"""Project history tracking - records completed projects for future reference.

Provides similarity search to bootstrap new goals from past successes.
"""

import json
import re
from collections import Counter
from pathlib import Path

STOP_WORDS = frozenset({
    "a", "an", "the", "is", "of", "to", "for", "with", "in", "on",
    "and", "or", "as", "that", "this", "it",
})


class ProjectHistory:
    """Records and queries completed project history.

    Stores completed projects in JSONL format and provides similarity
    search by keyword overlap to find relevant past projects.
    """

    def __init__(self, memory_dir: str) -> None:
        """Initialize project history.

        Args:
            memory_dir: Path to the memory/ directory.
        """
        self.memory_dir = Path(memory_dir)
        self.history_path = self.memory_dir / "projects_completed.jsonl"

    def record_project(self, project: dict) -> None:
        """Record a completed project to history.

        Args:
            project: Dict with: goal, skills_used, iterations_needed,
                     outcome ('success'|'failed'|'abandoned'), timestamp,
                     nodes_visited (list of node ids traversed).
        """
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(project) + "\n")

    def get_similar_past_projects(self, goal: str, top_k: int = 3) -> list[dict]:
        """Find past projects with similar goals using keyword overlap.

        Tokenizes the goal into keywords, compares against stored project
        goals, returns top_k by overlap score.

        Args:
            goal: The new goal to find similar projects for.
            top_k: Number of results to return (default 3).

        Returns:
            List of project dicts sorted by similarity (highest first).
        """
        history = self._load_history()
        if not history:
            return []

        goal_tokens = self._tokenize(goal)
        if not goal_tokens:
            return []

        scored: list[tuple[float, dict]] = []
        for project in history:
            project_tokens = self._tokenize(project.get("goal", ""))
            overlap = len(goal_tokens & project_tokens)
            score = overlap / max(len(goal_tokens), 1)
            if score > 0:
                scored.append((score, project))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [project for _, project in scored[:top_k]]

    def get_recommended_skills(self, goal: str) -> list[str]:
        """Get skill recommendations based on similar past successful projects.

        Finds similar past projects that succeeded, returns the union of
        their skills_used lists (deduplicated).

        Args:
            goal: The goal to get recommendations for.

        Returns:
            List of recommended skill names.
        """
        similar = self.get_similar_past_projects(goal, top_k=3)
        skills: list[str] = []
        seen: set[str] = set()

        for project in similar:
            if project.get("outcome") == "success":
                for skill in project.get("skills_used", []):
                    if skill not in seen:
                        seen.add(skill)
                        skills.append(skill)

        return skills

    def get_stats(self) -> dict:
        """Get overall project history statistics.

        Returns:
            Dict with: total_projects, success_rate, most_used_skills (top 5),
            avg_iterations.
        """
        history = self._load_history()

        if not history:
            return {
                "total_projects": 0,
                "success_rate": 0.0,
                "most_used_skills": [],
                "avg_iterations": 0.0,
            }

        total = len(history)
        successes = sum(1 for p in history if p.get("outcome") == "success")
        success_rate = successes / total if total > 0 else 0.0

        all_skills: list[str] = []
        total_iterations = 0
        for project in history:
            all_skills.extend(project.get("skills_used", []))
            total_iterations += project.get("iterations_needed", 0)

        skill_counts = Counter(all_skills)
        most_used = [skill for skill, _ in skill_counts.most_common(5)]
        avg_iterations = total_iterations / total if total > 0 else 0.0

        return {
            "total_projects": total,
            "success_rate": success_rate,
            "most_used_skills": most_used,
            "avg_iterations": avg_iterations,
        }

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase keyword set.

        Removes common stop words, splits on non-alphanumeric.
        """
        words = re.split(r"[^a-zA-Z0-9]+", text.lower())
        return {w for w in words if w and w not in STOP_WORDS}

    def _load_history(self) -> list[dict]:
        """Load all project records from JSONL."""
        if not self.history_path.exists():
            return []

        records: list[dict] = []
        with open(self.history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records
