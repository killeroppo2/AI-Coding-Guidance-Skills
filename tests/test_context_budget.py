"""Tests for kernel/context_budget.py."""

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

    def test_negative_total_tokens_clamped_to_zero(self):
        """Negative total_tokens should be clamped to 0."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("neg", -500, {"x": 100}, 10000)

        stats = tracker.get_stats()
        assert stats["total_tokens_assembled"] == 0
        assert stats["avg_utilization_pct"] == 0.0

    def test_negative_budget_limit_clamped_to_zero(self):
        """Negative budget_limit should be clamped to 0."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("neg_budget", 5000, {}, -1000)

        stats = tracker.get_stats()
        assert stats["total_budget_available"] == 0
        assert stats["avg_utilization_pct"] == 0.0

    def test_both_negative_clamped(self):
        """Both negative tokens and budget should be clamped to 0."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("both_neg", -100, {}, -200)

        stats = tracker.get_stats()
        assert stats["total_tokens_assembled"] == 0
        assert stats["total_budget_available"] == 0
        assert stats["avg_utilization_pct"] == 0.0

    def test_empty_sections_in_efficiency_report(self):
        """get_efficiency_report handles empty sections dict."""
        tracker = ContextBudgetTracker()
        tracker.record_assembly("empty_sections", 5000, {}, 10000)

        report = tracker.get_efficiency_report()
        assert "Context Budget Report" in report
        assert "empty_sections" in report
        # Should not crash when sections is empty

    def test_max_records_adjusts_totals_correctly(self):
        """When old records are evicted, totals are correctly decremented."""
        tracker = ContextBudgetTracker(max_records=2)
        tracker.record_assembly("a", 1000, {}, 5000)
        tracker.record_assembly("b", 2000, {}, 5000)
        tracker.record_assembly("c", 3000, {}, 5000)

        stats = tracker.get_stats()
        assert stats["assemblies"] == 2
        # "a" was evicted, so totals = b(2000) + c(3000)
        assert stats["total_tokens_assembled"] == 5000
        assert stats["total_budget_available"] == 10000

    def test_very_large_token_counts(self):
        """Very large token counts are handled without overflow."""
        tracker = ContextBudgetTracker()
        large = 10**9  # 1 billion
        tracker.record_assembly("huge", large, {"ctx": large}, large * 2)

        stats = tracker.get_stats()
        assert stats["total_tokens_assembled"] == large
        assert stats["avg_utilization_pct"] == 50.0

    def test_memory_bounded_with_many_assemblies(self):
        """10000 record_assembly calls should stay bounded at max_records."""
        tracker = ContextBudgetTracker(max_records=100)
        for i in range(10000):
            tracker.record_assembly(f"node_{i}", 1000, {"s": 1000}, 2000)

        stats = tracker.get_stats()
        # Should only retain max_records entries
        assert stats["assemblies"] == 100
        # Total should reflect only the last 100 records
        assert stats["total_tokens_assembled"] == 100 * 1000
        assert stats["total_budget_available"] == 100 * 2000

    def test_deque_backed_records_o1_operations(self):
        """Verify that the tracker uses deque for O(1) append/eviction."""
        from collections import deque

        tracker = ContextBudgetTracker(max_records=50)
        assert isinstance(tracker._records, deque)
        assert tracker._records.maxlen == 50
