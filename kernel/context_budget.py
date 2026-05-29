"""Context budget tracking and analytics.

Inspired by context-mode's AnalyticsEngine, this module tracks token usage
across iterations to report efficiency and identify waste.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssemblyRecord:
    """Record of a single context assembly.

    Attributes:
        node_id: The node for which context was assembled.
        total_tokens: Total tokens used in the assembly.
        sections: Mapping of section names to token counts.
        budget_limit: The token budget limit for this assembly.
        utilization_pct: Percentage of budget used.
    """

    node_id: str
    total_tokens: int
    sections: dict[str, int] = field(default_factory=dict)
    budget_limit: int = 0
    utilization_pct: float = 0.0


class ContextBudgetTracker:
    """Tracks context token usage across iterations.

    Provides efficiency reporting similar to context-mode's ctx_stats.
    """

    def __init__(self, max_records: int = 100) -> None:
        """Initialize the budget tracker.

        Args:
            max_records: Maximum number of assembly records to retain.
        """
        self._records: deque[AssemblyRecord] = deque(maxlen=max_records)
        self._max_records = max_records
        self._total_assembled: int = 0
        self._total_budget: int = 0

    def record_assembly(
        self,
        node_id: str,
        total_tokens: int,
        sections: dict[str, int],
        budget_limit: int,
    ) -> None:
        """Record a context assembly event.

        Args:
            node_id: The node for which context was assembled.
            total_tokens: Total tokens used (negative values treated as 0).
            sections: Mapping of section names to token counts.
            budget_limit: The token budget limit (negative values treated as 0).
        """
        # Clamp negative values to 0
        total_tokens = max(0, total_tokens)
        budget_limit = max(0, budget_limit)
        utilization = (total_tokens / budget_limit * 100) if budget_limit > 0 else 0.0
        record = AssemblyRecord(
            node_id=node_id,
            total_tokens=total_tokens,
            sections=sections,
            budget_limit=budget_limit,
            utilization_pct=utilization,
        )
        # If at capacity, the deque will auto-evict the oldest record
        if len(self._records) == self._max_records:
            removed = self._records[0]
            self._total_assembled -= removed.total_tokens
            self._total_budget -= removed.budget_limit
        self._records.append(record)
        self._total_assembled += total_tokens
        self._total_budget += budget_limit

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics.

        Returns:
            Dict with keys: assemblies, total_tokens_assembled,
            total_budget_available, avg_utilization_pct, avg_tokens_per_assembly.
        """
        if not self._records:
            return {
                "assemblies": 0,
                "total_tokens_assembled": 0,
                "total_budget_available": 0,
                "avg_utilization_pct": 0.0,
                "avg_tokens_per_assembly": 0,
            }
        avg_util = sum(r.utilization_pct for r in self._records) / len(self._records)
        avg_tokens = self._total_assembled // len(self._records)
        return {
            "assemblies": len(self._records),
            "total_tokens_assembled": self._total_assembled,
            "total_budget_available": self._total_budget,
            "avg_utilization_pct": round(avg_util, 1),
            "avg_tokens_per_assembly": avg_tokens,
        }

    def get_efficiency_report(self) -> str:
        """Return a human-readable efficiency report.

        Returns:
            Multi-line string with context budget statistics.
        """
        stats = self.get_stats()
        if stats["assemblies"] == 0:
            return "尚未记录上下文组装数据。"
        lines = [
            "上下文预算报告",
            "=" * 40,
            f"组装次数: {stats['assemblies']}",
            f"平均利用率: {stats['avg_utilization_pct']:.1f}%",
            f"平均token/次: {stats['avg_tokens_per_assembly']:,}",
            f"总token使用量: {stats['total_tokens_assembled']:,}",
            f"总预算容量: {stats['total_budget_available']:,}",
        ]
        # Section breakdown from last assembly
        if self._records:
            last = self._records[-1]
            lines.append("")
            lines.append(f"最近一次组装 ({last.node_id}):")
            for section, tokens in sorted(last.sections.items(), key=lambda x: -x[1]):
                lines.append(f"  {section}: {tokens:,} tokens")
        return "\n".join(lines)
