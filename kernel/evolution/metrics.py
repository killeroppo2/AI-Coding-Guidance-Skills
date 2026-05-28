"""Evolution metrics for tracking per-node performance over time."""

from collections import deque


class EvolutionMetrics:
    """Tracks success rate, retries, and duration per node over a sliding window.

    Provides quantitative data to support evolution decisions.
    """

    def __init__(self, window_size: int = 10):
        """Initialize metrics with configurable sliding window.

        Args:
            window_size: Number of recent iterations to track per node.
        """
        self.window_size = window_size
        self._data: dict[str, deque] = {}  # node_id -> deque of records

    def record_iteration(
        self, node_id: str, success: bool, retries: int = 0, duration: float = 0.0
    ) -> None:
        """Record an iteration result for a node.

        Args:
            node_id: The node that was executed.
            success: Whether the iteration succeeded.
            retries: Number of retries needed.
            duration: Duration in seconds.
        """
        if node_id not in self._data:
            self._data[node_id] = deque(maxlen=self.window_size)
        self._data[node_id].append({
            "success": success,
            "retries": retries,
            "duration": duration,
        })

    def get_node_metrics(self, node_id: str) -> dict:
        """Get aggregated metrics for a node.

        Returns:
            Dict with: success_rate (0.0-1.0), avg_retries, avg_duration, sample_count
        """
        if node_id not in self._data or len(self._data[node_id]) == 0:
            return {"success_rate": 0.0, "avg_retries": 0.0, "avg_duration": 0.0, "sample_count": 0}

        records = self._data[node_id]
        count = len(records)
        successes = sum(1 for r in records if r["success"])
        total_retries = sum(r["retries"] for r in records)
        total_duration = sum(r["duration"] for r in records)

        return {
            "success_rate": successes / count,
            "avg_retries": total_retries / count,
            "avg_duration": total_duration / count,
            "sample_count": count,
        }

    def get_overall_health(self) -> float:
        """Calculate overall system health as a composite score (0.0-1.0).

        Returns weighted average of all node success rates.
        Higher is healthier.
        """
        if not self._data:
            return 1.0  # No data = assume healthy

        total_weight = 0
        weighted_sum = 0.0
        for node_id in self._data:
            metrics = self.get_node_metrics(node_id)
            weight = metrics["sample_count"]
            weighted_sum += metrics["success_rate"] * weight
            total_weight += weight

        if total_weight == 0:
            return 1.0
        return weighted_sum / total_weight

    def compare_periods(self, node_id: str, split_at: int | None = None) -> dict:
        """Compare metrics between first half and second half of the window.

        Useful for detecting if a recent change improved or degraded performance.

        Args:
            node_id: The node to analyze.
            split_at: Index to split at. Default: middle of the data.

        Returns:
            Dict with before_success_rate, after_success_rate, delta.
        """
        if node_id not in self._data or len(self._data[node_id]) < 2:
            return {"before_success_rate": 0.0, "after_success_rate": 0.0, "delta": 0.0}

        records = list(self._data[node_id])
        if split_at is None:
            split_at = len(records) // 2

        before = records[:split_at]
        after = records[split_at:]

        before_rate = sum(1 for r in before if r["success"]) / len(before) if before else 0.0
        after_rate = sum(1 for r in after if r["success"]) / len(after) if after else 0.0

        return {
            "before_success_rate": before_rate,
            "after_success_rate": after_rate,
            "delta": after_rate - before_rate,
        }
