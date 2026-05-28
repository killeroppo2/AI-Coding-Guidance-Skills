"""Evolution history analysis, pruning, and archival."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


class EvolutionHistorian:
    """Analyzes, summarizes, and prunes evolution history.

    Provides insights into what changes work and which get reverted,
    enabling the feedback loop to make better evolution decisions.
    """

    def __init__(self, history_file: Path | str, archive_dir: Path | str | None = None):
        """
        Args:
            history_file: Path to evolution/history.jsonl
            archive_dir: Path to evolution/archive/ directory for pruned entries.
                         Defaults to history_file.parent / "archive"
        """
        self.history_file = Path(history_file)
        self.archive_dir = (
            Path(archive_dir) if archive_dir else self.history_file.parent / "archive"
        )

    def load_history(self) -> list[dict]:
        """Load all entries from history.jsonl."""
        if not self.history_file.exists():
            return []
        records: list[dict] = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def summarize_history(self) -> dict:
        """Compute summary statistics.

        Returns dict with:
        - total_changes: int
        - applied_count: int
        - rejected_count: int
        - failed_count: int
        - rolled_back_count: int (entries where type="rollback")
        - success_rate: float (applied / total non-rollback entries)
        - most_modified_nodes: list of top 3 (node_id, count) tuples
        - change_type_distribution: dict of type -> count
        """
        entries = self.load_history()
        total_changes = len(entries)
        applied_count = 0
        rejected_count = 0
        failed_count = 0
        rolled_back_count = 0
        node_counter: Counter = Counter()
        type_counter: Counter = Counter()

        for entry in entries:
            status = entry.get("status", "")
            change_type = entry.get("type", "")
            type_counter[change_type] += 1

            if change_type == "rollback":
                rolled_back_count += 1
                continue

            if status == "applied":
                applied_count += 1
            elif status == "rejected":
                rejected_count += 1
            elif status == "failed":
                failed_count += 1

            # Track modified nodes
            details = entry.get("details", {})
            node_id = details.get("node_id", "")
            if not node_id:
                node_id = (
                    details.get("node", {}).get("id", "")
                    if isinstance(details.get("node"), dict)
                    else ""
                )
            if node_id:
                node_counter[node_id] += 1

        non_rollback = total_changes - rolled_back_count
        success_rate = applied_count / non_rollback if non_rollback > 0 else 0.0

        most_modified_nodes = node_counter.most_common(3)

        return {
            "total_changes": total_changes,
            "applied_count": applied_count,
            "rejected_count": rejected_count,
            "failed_count": failed_count,
            "rolled_back_count": rolled_back_count,
            "success_rate": success_rate,
            "most_modified_nodes": most_modified_nodes,
            "change_type_distribution": dict(type_counter),
        }

    def prune_history(self, max_entries: int = 500) -> int:
        """Archive old entries keeping only the most recent max_entries.

        Moves older entries to archive_dir/archive_YYYYMMDD_HHMMSS.jsonl.
        Returns the number of entries archived.
        """
        entries = self.load_history()
        if len(entries) <= max_entries:
            return 0

        to_archive = entries[:-max_entries]
        to_keep = entries[-max_entries:]

        # Create archive directory
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Write archived entries
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_file = self.archive_dir / f"archive_{timestamp}.jsonl"
        with open(archive_file, "w", encoding="utf-8") as f:
            for entry in to_archive:
                f.write(json.dumps(entry) + "\n")

        # Rewrite history with only kept entries
        with open(self.history_file, "w", encoding="utf-8") as f:
            for entry in to_keep:
                f.write(json.dumps(entry) + "\n")

        return len(to_archive)

    def analyze_effectiveness(self) -> dict:
        """Analyze which change types tend to stick vs get reverted.

        Returns dict mapping change_type to:
        - applied: int (how many were applied)
        - reverted: int (how many were rolled back)
        - stick_rate: float (1.0 - reverted/applied, or 1.0 if none applied)

        To determine reverts: look at rollback entries and find the original
        change they rolled back (via details.rolled_back_change_id), then
        get that change's type.
        """
        entries = self.load_history()

        # Build a map of id -> entry for lookup
        id_to_entry: dict[str, dict] = {}
        for entry in entries:
            entry_id = entry.get("id", "")
            if entry_id:
                id_to_entry[entry_id] = entry

        # Count applied per type
        applied_per_type: Counter = Counter()
        reverted_per_type: Counter = Counter()

        for entry in entries:
            change_type = entry.get("type", "")
            if change_type == "rollback":
                # Find the original change that was rolled back
                rolled_back_id = entry.get("details", {}).get("rolled_back_change_id", "")
                if rolled_back_id and rolled_back_id in id_to_entry:
                    original_type = id_to_entry[rolled_back_id].get("type", "")
                    if original_type:
                        reverted_per_type[original_type] += 1
            else:
                if entry.get("status") == "applied":
                    applied_per_type[change_type] += 1

        # Build result
        all_types = set(applied_per_type.keys()) | set(reverted_per_type.keys())
        result: dict[str, dict] = {}
        for ctype in all_types:
            applied = applied_per_type.get(ctype, 0)
            reverted = reverted_per_type.get(ctype, 0)
            if applied > 0:
                stick_rate = 1.0 - (reverted / applied)
            else:
                stick_rate = 1.0
            result[ctype] = {
                "applied": applied,
                "reverted": reverted,
                "stick_rate": stick_rate,
            }

        return result

    def get_evolution_velocity(self, window: int = 10) -> float:
        """Calculate changes applied per window of iterations.

        Counts applied changes in the last `window` entries of history.
        Returns: applied_count / window (as a rate).
        """
        entries = self.load_history()
        if not entries:
            return 0.0

        recent = entries[-window:]
        applied_count = sum(
            1 for e in recent if e.get("status") == "applied" and e.get("type") != "rollback"
        )
        return applied_count / window
