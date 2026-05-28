"""Skill accumulation engine - auto-creates skills from repeated patterns.

The core moat: the more you use this system, the smarter it gets.
Tracks patterns across projects and auto-generates skills when patterns
repeat 3+ times.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class SkillAccumulator:
    """Analyzes completed projects to detect and accumulate reusable patterns.

    When a pattern appears 3+ times across projects, auto-proposes a new skill.
    Tracks per-skill metrics: times_used, success_rate, avg_iterations.
    """

    def __init__(self, skills_dir: str, memory_dir: str) -> None:
        """Initialize the skill accumulator.

        Args:
            skills_dir: Path to the skills/ directory.
            memory_dir: Path to the memory/ directory.
        """
        self.skills_dir = Path(skills_dir)
        self.memory_dir = Path(memory_dir)
        self.metrics_path = self.skills_dir / "_metrics.yaml"

    def analyze_completion(self, project_data: dict) -> list[dict]:
        """Analyze a completed project for reusable patterns.

        Reads reflections, extracts recurring patterns (node sequences,
        error-resolution pairs, skill combinations), and proposes new
        skills for patterns appearing 3+ times.

        Args:
            project_data: Dict with goal, skills_used, outcome, reflections.

        Returns:
            List of proposed skill dicts (name, description, content, tags).
        """
        reflections = project_data.get("reflections", [])
        patterns = self.detect_patterns(reflections)

        proposed_skills: list[dict] = []
        for pattern in patterns:
            if pattern["frequency"] >= 3:
                skill_name = self._pattern_to_skill_name(pattern["name"])
                proposed_skills.append({
                    "name": skill_name,
                    "description": f"Auto-generated from {pattern['pattern_type']} pattern: {pattern['name']}",
                    "content": pattern["content"],
                    "tags": ["auto-generated", pattern["pattern_type"]],
                })

        return proposed_skills

    def detect_patterns(self, reflections: list[dict]) -> list[dict]:
        """Detect recurring patterns in reflections.

        Patterns detected:
        - Same node succeeding consistently -> workflow pattern
        - Specific error being resolved the same way -> resolution pattern
        - Same skill combination being effective -> combo pattern

        Args:
            reflections: List of reflection dicts.

        Returns:
            List of pattern dicts with: name, frequency, pattern_type, content.
        """
        if not reflections:
            return []

        patterns: list[dict] = []

        # Detect workflow patterns: nodes that succeed 3+ consecutive times
        node_successes: dict[str, int] = {}
        for reflection in reflections:
            node = reflection.get("node", "")
            success = reflection.get("success", False)
            if node and success:
                node_successes[node] = node_successes.get(node, 0) + 1

        for node, count in node_successes.items():
            if count >= 3:
                patterns.append({
                    "name": f"{node}-workflow",
                    "frequency": count,
                    "pattern_type": "workflow",
                    "content": f"Node '{node}' succeeds consistently ({count} times). "
                               f"This workflow pattern is reliable.",
                })

        # Detect resolution patterns: same error resolved 3+ times
        error_resolutions: dict[str, int] = {}
        for reflection in reflections:
            errors = reflection.get("errors", [])
            node = reflection.get("node", "")
            for error in errors:
                key = f"{node}:{error}" if node else error
                error_resolutions[key] = error_resolutions.get(key, 0) + 1

        for error_key, count in error_resolutions.items():
            if count >= 3:
                patterns.append({
                    "name": f"resolve-{error_key.split(':')[0]}",
                    "frequency": count,
                    "pattern_type": "resolution",
                    "content": f"Error pattern '{error_key}' resolved {count} times. "
                               f"Known resolution approach available.",
                })

        return patterns

    def update_metrics(self, skill_name: str, success: bool, iterations: int) -> None:
        """Update metrics for a skill after usage.

        Args:
            skill_name: Name of the skill used.
            success: Whether the project using this skill succeeded.
            iterations: Number of iterations the project took.
        """
        metrics = self._load_metrics()

        if skill_name not in metrics:
            metrics[skill_name] = {
                "times_used": 0,
                "successes": 0,
                "total_iterations": 0,
            }

        metrics[skill_name]["times_used"] += 1
        if success:
            metrics[skill_name]["successes"] += 1
        metrics[skill_name]["total_iterations"] += iterations

        self._save_metrics(metrics)

    def get_skill_metrics(self, skill_name: str) -> dict:
        """Get metrics for a specific skill.

        Returns:
            Dict with: times_used, success_rate, avg_iterations.
            Returns zeros if skill has no metrics.
        """
        metrics = self._load_metrics()

        if skill_name not in metrics:
            return {"times_used": 0, "success_rate": 0.0, "avg_iterations": 0.0}

        entry = metrics[skill_name]
        times_used = entry["times_used"]
        success_rate = entry["successes"] / times_used if times_used > 0 else 0.0
        avg_iterations = entry["total_iterations"] / times_used if times_used > 0 else 0.0

        return {
            "times_used": times_used,
            "success_rate": success_rate,
            "avg_iterations": avg_iterations,
        }

    def get_all_metrics(self) -> dict:
        """Get metrics for all tracked skills.

        Returns:
            Dict mapping skill_name -> metrics dict.
        """
        raw_metrics = self._load_metrics()
        result: dict[str, dict] = {}

        for skill_name, entry in raw_metrics.items():
            times_used = entry["times_used"]
            success_rate = entry["successes"] / times_used if times_used > 0 else 0.0
            avg_iterations = entry["total_iterations"] / times_used if times_used > 0 else 0.0
            result[skill_name] = {
                "times_used": times_used,
                "success_rate": success_rate,
                "avg_iterations": avg_iterations,
            }

        return result

    def _load_metrics(self) -> dict:
        """Load metrics from _metrics.yaml."""
        if not self.metrics_path.exists():
            return {}
        with open(self.metrics_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data else {}

    def _save_metrics(self, metrics: dict) -> None:
        """Save metrics to _metrics.yaml."""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        with open(self.metrics_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(metrics, f, default_flow_style=False, allow_unicode=True)

    def _pattern_to_skill_name(self, pattern_name: str) -> str:
        """Convert a pattern name to a valid kebab-case skill name.

        Args:
            pattern_name: Raw pattern name.

        Returns:
            Kebab-case skill name.
        """
        import re
        # Replace non-alphanumeric with hyphens, lowercase
        name = re.sub(r"[^a-z0-9]+", "-", pattern_name.lower())
        # Remove leading/trailing hyphens
        name = name.strip("-")
        # Collapse multiple hyphens
        name = re.sub(r"-+", "-", name)
        return name or "unnamed-pattern"
