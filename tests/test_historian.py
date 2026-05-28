"""Tests for the EvolutionHistorian class and FeedbackLoop integration."""

import json
import uuid
from pathlib import Path

import pytest
import yaml

from kernel.evolution.historian import EvolutionHistorian
from kernel.evolution.metrics import EvolutionMetrics
from kernel.feedback_loop import FeedbackLoop


def _make_entry(
    change_type="add_node",
    status="applied",
    node_id="",
    change_id=None,
    details=None,
):
    """Helper to create a history entry."""
    if details is None:
        details = {}
    if node_id:
        details["node_id"] = node_id
    return {
        "id": change_id or str(uuid.uuid4()),
        "type": change_type,
        "details": details,
        "reason": "test reason",
        "timestamp": "2025-01-01T00:00:00Z",
        "status": status,
    }


def _write_entries(history_file: Path, entries: list[dict]) -> None:
    """Write entries to a JSONL file."""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestLoadHistory:
    """Tests for EvolutionHistorian.load_history."""

    def test_load_history_empty_file(self, tmp_path: Path) -> None:
        """Test loading from an empty file returns []."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        history_file.parent.mkdir(parents=True)
        history_file.touch()

        historian = EvolutionHistorian(history_file)
        result = historian.load_history()
        assert result == []

    def test_load_history_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from a nonexistent file returns []."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        historian = EvolutionHistorian(history_file)
        result = historian.load_history()
        assert result == []

    def test_load_history_with_valid_entries(self, tmp_path: Path) -> None:
        """Test loading valid entries from history file."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied", node_id="plan"),
            _make_entry("remove_node", "rejected", node_id="old_node"),
            _make_entry("modify_prompt", "applied"),
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        result = historian.load_history()
        assert len(result) == 3
        assert result[0]["type"] == "add_node"
        assert result[1]["status"] == "rejected"

    def test_load_history_skips_invalid_json(self, tmp_path: Path) -> None:
        """Test that invalid JSON lines are skipped."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        history_file.parent.mkdir(parents=True)
        with open(history_file, "w") as f:
            f.write(json.dumps(_make_entry("add_node", "applied")) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps(_make_entry("remove_node", "applied")) + "\n")

        historian = EvolutionHistorian(history_file)
        result = historian.load_history()
        assert len(result) == 2


class TestSummarizeHistory:
    """Tests for EvolutionHistorian.summarize_history."""

    def test_summarize_empty_history(self, tmp_path: Path) -> None:
        """Test summarize with empty history."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        history_file.parent.mkdir(parents=True)
        history_file.touch()

        historian = EvolutionHistorian(history_file)
        summary = historian.summarize_history()
        assert summary["total_changes"] == 0
        assert summary["applied_count"] == 0
        assert summary["rejected_count"] == 0
        assert summary["failed_count"] == 0
        assert summary["rolled_back_count"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["most_modified_nodes"] == []
        assert summary["change_type_distribution"] == {}

    def test_summarize_mixed_statuses(self, tmp_path: Path) -> None:
        """Test summarize with mixed applied, rejected, failed, and rollback entries."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        change_id = str(uuid.uuid4())
        entries = [
            _make_entry("add_node", "applied", node_id="plan", change_id=change_id),
            _make_entry("add_node", "applied", node_id="code"),
            _make_entry("remove_node", "rejected", node_id="old"),
            _make_entry("modify_prompt", "failed"),
            _make_entry("add_node", "applied", node_id="plan"),
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": change_id},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:05Z",
                "status": "applied",
            },
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        summary = historian.summarize_history()

        assert summary["total_changes"] == 6
        assert summary["applied_count"] == 3
        assert summary["rejected_count"] == 1
        assert summary["failed_count"] == 1
        assert summary["rolled_back_count"] == 1
        # success_rate = 3 applied / 5 non-rollback = 0.6
        assert summary["success_rate"] == pytest.approx(0.6)

    def test_summarize_most_modified_nodes(self, tmp_path: Path) -> None:
        """Test that most_modified_nodes extracts node_id from details."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied", node_id="plan"),
            _make_entry("add_node", "applied", node_id="plan"),
            _make_entry("add_node", "applied", node_id="plan"),
            _make_entry("remove_node", "applied", node_id="code"),
            _make_entry("remove_node", "applied", node_id="code"),
            _make_entry("add_node", "applied", node_id="test"),
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        summary = historian.summarize_history()

        # plan=3, code=2, test=1
        nodes = summary["most_modified_nodes"]
        assert len(nodes) == 3
        assert nodes[0] == ("plan", 3)
        assert nodes[1] == ("code", 2)
        assert nodes[2] == ("test", 1)

    def test_summarize_change_type_distribution(self, tmp_path: Path) -> None:
        """Test change_type_distribution counts correctly."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied"),
            _make_entry("add_node", "applied"),
            _make_entry("remove_node", "rejected"),
            _make_entry("modify_prompt", "applied"),
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        summary = historian.summarize_history()

        assert summary["change_type_distribution"]["add_node"] == 2
        assert summary["change_type_distribution"]["remove_node"] == 1
        assert summary["change_type_distribution"]["modify_prompt"] == 1

    def test_summarize_node_id_from_nested_node_dict(self, tmp_path: Path) -> None:
        """Test that node_id is extracted from details.node.id if node_id is absent."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied", details={"node": {"id": "review"}}),
            _make_entry("add_node", "applied", details={"node": {"id": "review"}}),
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        summary = historian.summarize_history()
        assert ("review", 2) in summary["most_modified_nodes"]


class TestPruneHistory:
    """Tests for EvolutionHistorian.prune_history."""

    def test_prune_with_fewer_than_max_entries(self, tmp_path: Path) -> None:
        """Test that prune does nothing when entries <= max_entries."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [_make_entry("add_node", "applied") for _ in range(5)]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        archived = historian.prune_history(max_entries=500)

        assert archived == 0
        # History should remain unchanged
        remaining = historian.load_history()
        assert len(remaining) == 5

    def test_prune_with_exactly_max_entries(self, tmp_path: Path) -> None:
        """Test that prune does nothing when entries == max_entries."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [_make_entry("add_node", "applied") for _ in range(10)]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        archived = historian.prune_history(max_entries=10)

        assert archived == 0

    def test_prune_creates_archive_and_trims(self, tmp_path: Path) -> None:
        """Test that prune moves old entries to archive and trims history."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [_make_entry("add_node", "applied", change_id=f"id_{i}") for i in range(20)]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        archived = historian.prune_history(max_entries=5)

        assert archived == 15
        # History should have only 5 entries (the last 5)
        remaining = historian.load_history()
        assert len(remaining) == 5
        assert remaining[0]["id"] == "id_15"
        assert remaining[4]["id"] == "id_19"

    def test_prune_archive_file_contains_correct_entries(self, tmp_path: Path) -> None:
        """Test that the archive file contains the pruned entries."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [_make_entry("add_node", "applied", change_id=f"id_{i}") for i in range(10)]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        historian.prune_history(max_entries=3)

        # Check archive dir was created
        assert historian.archive_dir.exists()

        # Find the archive file
        archive_files = list(historian.archive_dir.glob("archive_*.jsonl"))
        assert len(archive_files) == 1

        # Read archive entries
        with open(archive_files[0], "r") as f:
            archive_entries = [json.loads(line) for line in f if line.strip()]

        assert len(archive_entries) == 7
        assert archive_entries[0]["id"] == "id_0"
        assert archive_entries[6]["id"] == "id_6"

    def test_prune_with_custom_archive_dir(self, tmp_path: Path) -> None:
        """Test pruning with a custom archive directory."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        custom_archive = tmp_path / "custom_archive"
        entries = [_make_entry("add_node", "applied") for _ in range(10)]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file, archive_dir=custom_archive)
        historian.prune_history(max_entries=5)

        assert custom_archive.exists()
        archive_files = list(custom_archive.glob("archive_*.jsonl"))
        assert len(archive_files) == 1


class TestAnalyzeEffectiveness:
    """Tests for EvolutionHistorian.analyze_effectiveness."""

    def test_no_rollbacks_shows_stick_rate_1(self, tmp_path: Path) -> None:
        """Test that with no rollbacks, all types have stick_rate 1.0."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied"),
            _make_entry("add_node", "applied"),
            _make_entry("modify_prompt", "applied"),
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        result = historian.analyze_effectiveness()

        assert result["add_node"]["applied"] == 2
        assert result["add_node"]["reverted"] == 0
        assert result["add_node"]["stick_rate"] == 1.0
        assert result["modify_prompt"]["stick_rate"] == 1.0

    def test_correctly_counts_reverts_per_type(self, tmp_path: Path) -> None:
        """Test that reverts are counted per change type."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        id1 = "change-1"
        id2 = "change-2"
        id3 = "change-3"
        entries = [
            _make_entry("add_node", "applied", change_id=id1),
            _make_entry("add_node", "applied", change_id=id2),
            _make_entry("modify_prompt", "applied", change_id=id3),
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id1},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:03Z",
                "status": "applied",
            },
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id3},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:04Z",
                "status": "applied",
            },
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        result = historian.analyze_effectiveness()

        # add_node: 2 applied, 1 reverted -> stick_rate = 0.5
        assert result["add_node"]["applied"] == 2
        assert result["add_node"]["reverted"] == 1
        assert result["add_node"]["stick_rate"] == pytest.approx(0.5)

        # modify_prompt: 1 applied, 1 reverted -> stick_rate = 0.0
        assert result["modify_prompt"]["applied"] == 1
        assert result["modify_prompt"]["reverted"] == 1
        assert result["modify_prompt"]["stick_rate"] == pytest.approx(0.0)

    def test_all_changes_reverted_shows_stick_rate_0(self, tmp_path: Path) -> None:
        """Test that when all changes are reverted, stick_rate is 0.0."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        id1 = "change-1"
        id2 = "change-2"
        entries = [
            _make_entry("add_node", "applied", change_id=id1),
            _make_entry("add_node", "applied", change_id=id2),
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id1},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:02Z",
                "status": "applied",
            },
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id2},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:03Z",
                "status": "applied",
            },
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        result = historian.analyze_effectiveness()

        assert result["add_node"]["applied"] == 2
        assert result["add_node"]["reverted"] == 2
        assert result["add_node"]["stick_rate"] == pytest.approx(0.0)

    def test_empty_history(self, tmp_path: Path) -> None:
        """Test analyze_effectiveness with empty history."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        history_file.parent.mkdir(parents=True)
        history_file.touch()

        historian = EvolutionHistorian(history_file)
        result = historian.analyze_effectiveness()
        assert result == {}

    def test_rollback_of_unknown_id_is_ignored(self, tmp_path: Path) -> None:
        """Test that rollback referencing unknown id does not crash."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied"),
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": "nonexistent-id"},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:01Z",
                "status": "applied",
            },
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        result = historian.analyze_effectiveness()
        # add_node has 1 applied, 0 reverted
        assert result["add_node"]["applied"] == 1
        assert result["add_node"]["reverted"] == 0
        assert result["add_node"]["stick_rate"] == 1.0


class TestGetEvolutionVelocity:
    """Tests for EvolutionHistorian.get_evolution_velocity."""

    def test_velocity_with_applied_changes(self, tmp_path: Path) -> None:
        """Test velocity calculation with applied changes in window."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied"),
            _make_entry("add_node", "applied"),
            _make_entry("add_node", "rejected"),
            _make_entry("modify_prompt", "applied"),
            _make_entry("remove_node", "failed"),
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        # Window=10, 3 applied out of 5 entries (all within window)
        velocity = historian.get_evolution_velocity(window=10)
        assert velocity == pytest.approx(3.0 / 10.0)

    def test_velocity_with_empty_history(self, tmp_path: Path) -> None:
        """Test velocity returns 0.0 for empty history."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        history_file.parent.mkdir(parents=True)
        history_file.touch()

        historian = EvolutionHistorian(history_file)
        velocity = historian.get_evolution_velocity(window=10)
        assert velocity == 0.0

    def test_velocity_uses_last_window_entries(self, tmp_path: Path) -> None:
        """Test that velocity only counts entries in the last window."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        # 15 entries total, first 10 are rejected, last 5 are applied
        entries = [_make_entry("add_node", "rejected") for _ in range(10)]
        entries += [_make_entry("add_node", "applied") for _ in range(5)]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        # Window of 5 should see all 5 applied
        velocity = historian.get_evolution_velocity(window=5)
        assert velocity == pytest.approx(5.0 / 5.0)

    def test_velocity_excludes_rollback_type(self, tmp_path: Path) -> None:
        """Test that rollback entries (even with status applied) are not counted."""
        history_file = tmp_path / "evolution" / "history.jsonl"
        entries = [
            _make_entry("add_node", "applied"),
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": "some-id"},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:01Z",
                "status": "applied",
            },
        ]
        _write_entries(history_file, entries)

        historian = EvolutionHistorian(history_file)
        velocity = historian.get_evolution_velocity(window=10)
        # Only 1 non-rollback applied entry
        assert velocity == pytest.approx(1.0 / 10.0)


class TestFeedbackLoopHistorianIntegration:
    """Tests for FeedbackLoop integration with EvolutionHistorian."""

    @pytest.fixture
    def loop_with_historian(self, tmp_path: Path):
        """Create a FeedbackLoop with historian enabled."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "reflections.jsonl").touch()

        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()
        (kernel_dir / "prompts").mkdir()

        graph_file = kernel_dir / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "init",
                    "prompt_file": "prompts/orchestrator.md",
                    "description": "Init",
                    "transitions": [{"to": "code", "condition": "goal_loaded"}],
                    "max_retries": 1,
                },
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Code",
                    "transitions": [],
                    "max_retries": 3,
                },
            ],
            "default_start": "init",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        from kernel.evolution.engine import EvolutionEngine
        from kernel.graph_executor import GraphExecutor
        from kernel.reflector import Reflector
        from knowledge.store import KnowledgeStore

        knowledge = KnowledgeStore(str(knowledge_dir))
        graph_executor = GraphExecutor(str(graph_file))
        reflector = Reflector(str(memory_dir), knowledge)
        engine = EvolutionEngine(str(kernel_dir), graph_executor)
        metrics = EvolutionMetrics()

        history_file = kernel_dir / "evolution" / "history.jsonl"

        loop = FeedbackLoop(
            str(memory_dir),
            reflector,
            engine,
            metrics,
            history_file=history_file,
        )

        return loop, history_file, kernel_dir

    def test_historian_prunes_when_history_exceeds_500(
        self, loop_with_historian, tmp_path: Path
    ) -> None:
        """Test that FeedbackLoop auto-prunes when history exceeds 500."""
        loop, history_file, kernel_dir = loop_with_historian

        # Write 510 entries to history
        entries = [_make_entry("add_node", "applied", change_id=f"id_{i}") for i in range(510)]
        _write_entries(history_file, entries)

        iteration_data = {
            "node": "code",
            "result": "success",
            "errors": [],
            "iteration": 1,
        }

        loop.run_cycle(iteration_data)

        # After pruning, history should have max 500 entries
        # (plus potentially one more from the cycle itself, but in this case
        # no proposals are applied so no new entries)
        remaining = loop.historian.load_history()
        assert len(remaining) <= 500

        # Archive should exist
        archive_dir = history_file.parent / "archive"
        assert archive_dir.exists()

    def test_low_stick_rate_reduces_proposal_confidence(
        self, loop_with_historian, tmp_path: Path
    ) -> None:
        """Test that proposals with low stick_rate get reduced confidence."""
        loop, history_file, kernel_dir = loop_with_historian

        # Create history with add_node type that always gets reverted
        id1 = "change-1"
        id2 = "change-2"
        id3 = "change-3"
        entries = [
            _make_entry("add_node", "applied", change_id=id1),
            _make_entry("add_node", "applied", change_id=id2),
            _make_entry("add_node", "applied", change_id=id3),
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id1},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:03Z",
                "status": "applied",
            },
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id2},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:04Z",
                "status": "applied",
            },
            {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": id3},
                "reason": "revert",
                "timestamp": "2025-01-01T00:00:05Z",
                "status": "applied",
            },
        ]
        _write_entries(history_file, entries)

        # Verify effectiveness shows stick_rate 0.0 for add_node
        effectiveness = loop.historian.analyze_effectiveness()
        assert effectiveness["add_node"]["stick_rate"] == pytest.approx(0.0)

        # Mock the reflector to return a proposal with type=add_node and confidence 0.8
        original_propose = loop.reflector.propose_evolution
        loop.reflector.propose_evolution = lambda recent: [
            {
                "type": "add_node",
                "details": {"node": {"id": "new_node"}},
                "reason": "test",
                "confidence_score": 0.8,
            }
        ]

        iteration_data = {
            "node": "code",
            "result": "success",
            "errors": [],
            "iteration": 1,
        }

        result = loop.run_cycle(iteration_data)

        # The proposal had confidence 0.8, reduced by 0.3 = 0.5
        # With threshold 0.7, it should NOT be applied
        assert result["proposals_applied"] == 0
        assert result["proposals_generated"] == 1

        # Restore
        loop.reflector.propose_evolution = original_propose

    def test_no_historian_does_not_error(self, tmp_path: Path) -> None:
        """Test that FeedbackLoop works fine without historian."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "reflections.jsonl").touch()

        kernel_dir = tmp_path / "kernel"
        kernel_dir.mkdir()
        (kernel_dir / "evolution").mkdir()
        (kernel_dir / "prompts").mkdir()

        graph_file = kernel_dir / "graph.yaml"
        graph_data = {
            "nodes": [
                {
                    "id": "code",
                    "prompt_file": "prompts/coder.md",
                    "description": "Code",
                    "transitions": [],
                    "max_retries": 3,
                },
            ],
            "default_start": "code",
            "max_iterations": 30,
        }
        with open(graph_file, "w") as f:
            yaml.safe_dump(graph_data, f)

        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        for sub in ["rules", "skills", "patterns"]:
            (knowledge_dir / sub).mkdir()
            with open(knowledge_dir / sub / "_index.yaml", "w") as f:
                yaml.safe_dump({"items": []}, f)

        from kernel.evolution.engine import EvolutionEngine
        from kernel.graph_executor import GraphExecutor
        from kernel.reflector import Reflector
        from knowledge.store import KnowledgeStore

        knowledge = KnowledgeStore(str(knowledge_dir))
        graph_executor = GraphExecutor(str(graph_file))
        reflector = Reflector(str(memory_dir), knowledge)
        engine = EvolutionEngine(str(kernel_dir), graph_executor)
        metrics = EvolutionMetrics()

        # No history_file => no historian
        loop = FeedbackLoop(str(memory_dir), reflector, engine, metrics)
        assert loop.historian is None

        iteration_data = {
            "node": "code",
            "result": "success",
            "errors": [],
            "iteration": 1,
        }
        result = loop.run_cycle(iteration_data)
        assert "reflection" in result
