"""Tests for kernel/context_budget.py."""

import pytest

from kernel.context_budget import AssemblyRecord, ContextBudgetTracker


class TestAssemblyRecord:
    """Tests for AssemblyRecord dataclass."""

    def test_defaults(self):
        """AssemblyRecord should have sensible defaults."""
        record = AssemblyRecord(node_id="init", total_tokens=100)
        assert record.node_id == "init"
        assert record.total_tokens == 100
        assert record.sections == {}
        assert record.budget_limit == 0
        assert record.utilization_pct == 0.0

    def test_with_all_fields(self):
        """AssemblyRecord should store all provided fields."""
        record = AssemblyRecord(
            node_id="plan",
            total_tokens=5000,
            sections={"skills": 2000, "history": 3000},
            budget_limit=10000,
            utilization_pct=50.0,
        )
        assert record.node_id == "plan"
        assert record.total_tokens == 5000
        assert record.sections == {"skills": 2000, "history": 3000}
        assert record.budget_limit == 10000
        assert record.utilization_pct == 50.0


class TestContextBudgetTracker:
    """Tests for ContextBudgetTracker."""

    def test_empty_stats(self):
        """get_stats on empty tracker returns zeroes."""
        tracker = ContextBudgetTracker()
        stats = tracker.get_stats()
        assert stats["assemblies"] == 0
        assert stats["total_tokens_assembled"] == 0
        assert stats["total_budget_available"] == 0
        assert stats["avg_utilization_pct"] == 0.0
        assert stats["avg_tokens_per_assembly"] == 0

    def test_record_assembly(self):
        """record_assembly stores records correctly."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly(
            node_id="init",
            total_tokens=8000,
            sections={"boot": 2000, "state": 1000, "skills": 5000},
            budget_limit=32000,
        )
        stats = tracker.get_stats()
        assert stats["assemblies"] == 1
        assert stats["total_tokens_assembled"] == 8000
        assert stats["total_budget_available"] == 32000
        assert stats["avg_utilization_pct"] == 25.0
        assert stats["avg_tokens_per_assembly"] == 8000

    def test_multiple_assemblies_stats(self):
        """get_stats correctly averages across multiple assemblies."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("init", 8000, {"boot": 8000}, 32000)
        tracker.record_assembly("plan", 16000, {"plan": 16000}, 32000)

        stats = tracker.get_stats()
        assert stats["assemblies"] == 2
        assert stats["total_tokens_assembled"] == 24000
        assert stats["total_budget_available"] == 64000
        assert stats["avg_utilization_pct"] == 37.5  # (25 + 50) / 2
        assert stats["avg_tokens_per_assembly"] == 12000

    def test_max_records_bounding(self):
        """Records beyond max_records should be evicted (FIFO)."""
        tracker = ContextBudgetTracker(max_records=3)
        tracker.record_assembly("node_1", 1000, {}, 10000)
        tracker.record_assembly("node_2", 2000, {}, 10000)
        tracker.record_assembly("node_3", 3000, {}, 10000)
        tracker.record_assembly("node_4", 4000, {}, 10000)

        stats = tracker.get_stats()
        assert stats["assemblies"] == 3
        # node_1 was evicted, so totals = 2000 + 3000 + 4000
        assert stats["total_tokens_assembled"] == 9000
        assert stats["total_budget_available"] == 30000

    def test_zero_budget_limit(self):
        """Zero budget_limit should result in 0% utilization."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("init", 5000, {"boot": 5000}, 0)

        stats = tracker.get_stats()
        assert stats["avg_utilization_pct"] == 0.0

    def test_efficiency_report_empty(self):
        """get_efficiency_report on empty tracker returns a message."""
        tracker = ContextBudgetTracker()
        report = tracker.get_efficiency_report()
        assert report == "No context assemblies recorded yet."

    def test_efficiency_report_with_data(self):
        """get_efficiency_report produces readable multi-line output."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly(
            "code",
            20000,
            {"skills": 10000, "state": 5000, "prompt": 5000},
            32000,
        )

        report = tracker.get_efficiency_report()
        assert "Context Budget Report" in report
        assert "Assemblies: 1" in report
        assert "code" in report
        assert "skills: 10,000 tokens" in report
        assert "state: 5,000 tokens" in report
        assert "prompt: 5,000 tokens" in report

    def test_efficiency_report_utilization(self):
        """get_efficiency_report shows correct utilization percentage."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("init", 16000, {"a": 16000}, 32000)

        report = tracker.get_efficiency_report()
        assert "50.0%" in report

    def test_record_assembly_calculates_utilization(self):
        """record_assembly should correctly compute utilization_pct."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("test", 25000, {}, 50000)

        stats = tracker.get_stats()
        assert stats["avg_utilization_pct"] == 50.0
