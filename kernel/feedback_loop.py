"""Feedback loop that ties the reflector to the evolution engine.

After each cycle, reads real iteration data, calls the reflector,
and auto-applies confident proposals via the evolution engine.
"""

import json
from pathlib import Path
from typing import Any

from kernel.evolution.engine import EvolutionEngine
from kernel.evolution.historian import EvolutionHistorian
from kernel.evolution.metrics import EvolutionMetrics
from kernel.reflector import Reflector


class FeedbackLoop:
    """Connects iteration analysis to automatic kernel evolution.

    After each execution cycle, the feedback loop:
    1. Analyzes the iteration via the reflector
    2. Records the reflection
    3. Reads recent reflections for pattern detection
    4. Generates evolution proposals
    5. Auto-applies proposals with confidence above threshold
    6. Records metrics for tracking
    """

    def __init__(
        self,
        memory_dir: str,
        reflector: Reflector,
        evolution_engine: EvolutionEngine,
        metrics: EvolutionMetrics,
        max_applies_per_cycle: int = 1,
        history_file: Path | None = None,
        skill_accumulator=None,
    ) -> None:
        """Initialize the feedback loop.

        Args:
            memory_dir: Path to the memory/ directory.
            reflector: Reflector instance for iteration analysis.
            evolution_engine: EvolutionEngine for applying changes.
            metrics: EvolutionMetrics for tracking performance.
            max_applies_per_cycle: Max proposals to apply per cycle (default 1).
            history_file: Path to evolution history.jsonl. If provided,
                          creates an EvolutionHistorian for analysis and pruning.
            skill_accumulator: Optional SkillAccumulator instance. When provided
                               and a project completes, analyze_completion() is called.
        """
        self.memory_dir = Path(memory_dir)
        self.reflector = reflector
        self.evolution_engine = evolution_engine
        self.metrics = metrics
        self.threshold = 0.7
        self.max_applies_per_cycle = max_applies_per_cycle
        self.historian: EvolutionHistorian | None = None
        self.skill_accumulator = skill_accumulator
        if history_file is not None:
            self.historian = EvolutionHistorian(history_file)

    def run_cycle(self, iteration_data: dict) -> dict:
        """Run a full feedback cycle after an iteration.

        1. Analyze iteration via reflector
        2. Record the reflection
        3. Read recent reflections (last 10)
        4. Generate evolution proposals
        4b. Adjust proposal confidence based on historical effectiveness
        5. Apply proposals with confidence > threshold
        6. Record metrics
        7. Auto-prune history if historian is available

        Args:
            iteration_data: Dict with keys: node, result, errors, iteration.

        Returns:
            Dict with: reflection, proposals_generated, proposals_applied,
            proposals_skipped.
        """
        # 1. Analyze iteration
        reflection = self.reflector.analyze_iteration(iteration_data)

        # 2. Record the reflection
        self._record_reflection(reflection)

        # 3. Read recent reflections
        recent = self._read_recent_reflections(count=10)

        # 4. Generate evolution proposals
        proposals = self.reflector.propose_evolution(recent)

        # 4b. Adjust confidence based on historical effectiveness
        if self.historian:
            effectiveness = self.historian.analyze_effectiveness()
            for proposal in proposals:
                ptype = proposal.get("type", "")
                if ptype in effectiveness:
                    if effectiveness[ptype]["stick_rate"] < 0.3:
                        current = proposal.get("confidence_score", 0.0)
                        proposal["confidence_score"] = max(0.0, current - 0.3)

        # 5. Apply confident proposals (capped per cycle)
        applied = self.evolution_engine.apply_if_confident(
            proposals, self.threshold, max_applies=self.max_applies_per_cycle
        )

        # 6. Record metrics
        node_id = iteration_data.get("node", "unknown")
        success = reflection.get("success", False)
        self.metrics.record_iteration(node_id, success=success)

        # 6b. If project is complete, trigger skill accumulation
        if self.skill_accumulator and iteration_data.get("project_complete"):
            recent_reflections = self._read_recent_reflections(count=50)
            project_data = {
                "goal": iteration_data.get("goal", ""),
                "skills_used": iteration_data.get("skills_used", []),
                "outcome": iteration_data.get("result", ""),
                "reflections": recent_reflections,
            }
            self.skill_accumulator.analyze_completion(project_data)

        # 7. Auto-prune history
        if self.historian:
            self.historian.prune_history(max_entries=500)

        proposals_skipped = len(proposals) - len(applied)

        return {
            "reflection": reflection,
            "proposals_generated": len(proposals),
            "proposals_applied": len(applied),
            "proposals_skipped": proposals_skipped,
        }

    def _read_recent_reflections(self, count: int = 10) -> list[dict]:
        """Read last N reflections from reflections.jsonl.

        Args:
            count: Number of recent reflections to read.

        Returns:
            List of reflection dicts (most recent last).
        """
        reflections_path = self.memory_dir / "reflections.jsonl"
        if not reflections_path.exists():
            return []

        records: list[dict] = []
        with open(reflections_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return records[-count:]

    def _record_reflection(self, reflection: dict) -> None:
        """Append reflection to reflections.jsonl.

        After appending, if the file exceeds 1000 lines, prune to keep
        only the last 500 lines.

        Args:
            reflection: Reflection dict to record.
        """
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        reflections_path = self.memory_dir / "reflections.jsonl"
        with open(reflections_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(reflection) + "\n")

        # Prune if file exceeds 1000 lines: keep only last 500
        try:
            lines = reflections_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > 1000:
                keep = lines[-500:]
                reflections_path.write_text("\n".join(keep) + "\n", encoding="utf-8")
        except OSError:
            pass
