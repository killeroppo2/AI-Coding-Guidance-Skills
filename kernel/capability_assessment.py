"""Capability assessment for goal-skill matching.

Implements 知彼知己 (know yourself and your enemy) - the kernel must know
what it can and cannot do before attempting a goal.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml

# Stop words that are too generic to be skill-matchable
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "will",
        "build",
        "create",
        "make",
        "using",
        "want",
        "need",
        "to",
        "of",
        "in",
        "on",
        "is",
        "it",
        "be",
    }
)


class CapabilityAssessor:
    """Assesses kernel capabilities against a development goal."""

    def assess_capabilities(self, goal: str, skills: list[dict]) -> dict:
        """Assess skill coverage for a goal.

        Tokenizes goal into meaningful words (lowercase, >= 3 chars, excluding
        common stop words). For each goal keyword, checks if any skill's tags
        or description words contain it.

        Args:
            goal: The development goal text.
            skills: List of skill dicts with keys: name, tags, description.

        Returns:
            {
                "covered": [skill names that match at least one goal keyword],
                "gaps": [goal keywords that no skill matches],
                "confidence": float 0.0-1.0 (matched_keywords / total_keywords),
            }
        """
        if not goal or not goal.strip():
            return {"covered": [], "gaps": [], "confidence": 0.0}

        goal_keywords = self._tokenize_goal(goal)

        if not goal_keywords:
            return {"covered": [], "gaps": [], "confidence": 0.0}

        if not skills:
            return {"covered": [], "gaps": list(goal_keywords), "confidence": 0.0}

        # Build a set of all skill tags and description words
        covered_skills: list[str] = []
        matched_keywords: set[str] = set()

        for skill in skills:
            tags = [t.lower() for t in skill.get("tags", [])]
            desc_words = set(skill.get("description", "").lower().split())
            skill_words = set(tags) | desc_words
            name = skill.get("name", "")

            skill_matches = False
            for keyword in goal_keywords:
                if keyword in skill_words:
                    matched_keywords.add(keyword)
                    skill_matches = True

            if skill_matches:
                covered_skills.append(name)

        gaps = [kw for kw in goal_keywords if kw not in matched_keywords]
        confidence = len(matched_keywords) / len(goal_keywords) if goal_keywords else 0.0

        return {
            "covered": covered_skills,
            "gaps": gaps,
            "confidence": confidence,
        }

    def identify_skill_gaps(
        self, goal_keywords: list[str], available_skill_tags: list[str]
    ) -> list[str]:
        """Find goal keywords with no matching skill tags.

        Args:
            goal_keywords: Tokenized goal words.
            available_skill_tags: All tags from all available skills (flattened).

        Returns:
            List of unmatched keywords.
        """
        tag_set = {t.lower() for t in available_skill_tags}
        return [kw for kw in goal_keywords if kw.lower() not in tag_set]

    def suggest_skill_creation(self, gaps: list[str]) -> list[dict]:
        """Suggest new skills to create for identified gaps.

        For each gap keyword, suggest a skill definition.

        Args:
            gaps: List of gap keywords.

        Returns:
            List of skill suggestion dicts.
        """
        if not gaps:
            return []
        return [
            {
                "name": f"{keyword}-skill",
                "description": f"Skill for {keyword} development",
                "tags": [keyword],
            }
            for keyword in gaps
        ]

    def write_assessment(self, assessment: dict, goal: str, memory_dir: str) -> None:
        """Write assessment results to memory/assessment.yaml.

        Args:
            assessment: The dict from assess_capabilities.
            goal: The original goal string.
            memory_dir: Path to memory directory.
        """
        memory_path = Path(memory_dir)
        memory_path.mkdir(parents=True, exist_ok=True)

        suggestions = self.suggest_skill_creation(assessment.get("gaps", []))

        data = {
            "goal": goal,
            "confidence": assessment.get("confidence", 0.0),
            "covered_skills": assessment.get("covered", []),
            "skill_gaps": assessment.get("gaps", []),
            "suggestions": suggestions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        assessment_path = memory_path / "assessment.yaml"
        with open(assessment_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    def _tokenize_goal(self, goal: str) -> list[str]:
        """Tokenize a goal into meaningful keywords.

        Filters out words shorter than 3 characters and common stop words.

        Args:
            goal: The goal text.

        Returns:
            List of lowercase keyword strings.
        """
        words = goal.lower().split()
        return [w for w in words if len(w) >= 3 and w not in STOP_WORDS]
