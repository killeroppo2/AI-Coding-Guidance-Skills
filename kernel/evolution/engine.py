"""Evolution engine for modifying kernel behavior.

This module handles proposing, validating, and applying evolutionary changes
to the kernel's workflow graph and prompt templates. It enforces immutability
constraints defined in the constitution.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# Files that are immutable and cannot be modified by the evolution engine.
# Stored in normalized form for reliable comparison.
IMMUTABLE_FILES = frozenset(
    os.path.normpath(p) for p in ("kernel/BOOT.md", "kernel/constitution.md", "runner.py")
)

# Valid change types
VALID_CHANGE_TYPES = frozenset({
    "add_node", "remove_node", "reorder", "modify_prompt", "add_skill", "add_rule"
})


class EvolutionEngine:
    """Manages kernel self-evolution within constitutional constraints.

    The evolution engine can modify prompts, graph transitions, and knowledge
    base entries, but is explicitly prohibited from modifying files listed
    in IMMUTABLE_FILES.
    """

    def __init__(self, kernel_dir: str, graph_executor: Any) -> None:
        """Initialize the evolution engine.

        Args:
            kernel_dir: Path to the kernel/ directory.
            graph_executor: A GraphExecutor instance.
        """
        self.kernel_dir = Path(kernel_dir)
        self.graph_executor = graph_executor
        self.history_file = self.kernel_dir / "evolution" / "history.jsonl"

    def propose_change(self, change_type: str, details: dict, reason: str) -> dict:
        """Create a change proposal dict with timestamp and ID.

        Args:
            change_type: Type of change (add_node, remove_node, etc.).
            details: Details of the change.
            reason: Reason for the change.

        Returns:
            Change proposal dict.
        """
        return {
            "id": str(uuid.uuid4()),
            "type": change_type,
            "details": details,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "proposed",
        }

    def validate_change(self, change: dict, state: dict | None = None) -> tuple[bool, str]:
        """Validate against constitution.

        MUST REJECT changes that touch protected paths. Also rejects
        invalid change types. All paths are normalized before comparison
        to prevent bypass via variants like ./kernel/BOOT.md or kernel//BOOT.md.

        If state is provided and contains user_owned_files, also rejects
        changes targeting user-owned files.

        Args:
            change: The change proposal dict.
            state: Optional state dict with user_owned_files list.

        Returns:
            Tuple of (is_valid, reason_string).
        """
        change_type = change.get("type", "")
        details = change.get("details", {})

        # Check change type validity
        if change_type not in VALID_CHANGE_TYPES:
            return (False, f"Invalid change type: {change_type}")

        # Check if change targets protected files (with path normalization)
        for field in ["target_file", "path", "file", "prompt_file"]:
            path_value = details.get(field, "")
            if not path_value:
                continue
            normalized = os.path.normpath(path_value)
            if normalized in IMMUTABLE_FILES:
                return (False, f"Cannot modify protected file: {path_value}")

        # Check if change targets user-owned files
        if state is not None:
            user_owned = state.get("user_owned_files", [])
            if user_owned:
                for field in ["target_file", "path", "file", "prompt_file"]:
                    path_value = details.get(field, "")
                    if not path_value:
                        continue
                    if path_value in user_owned:
                        return (False, "File is user-owned and cannot be modified by evolution")

        # For modify_prompt, check for path traversal escaping kernel/prompts/
        if change_type == "modify_prompt":
            prompt_file = details.get("prompt_file", "")
            if prompt_file:
                # Resolve against kernel_dir to detect traversal
                resolved = (self.kernel_dir / prompt_file).resolve()
                kernel_resolved = self.kernel_dir.resolve()
                if not str(resolved).startswith(str(kernel_resolved) + os.sep) and resolved != kernel_resolved:
                    return (False, f"Path traversal detected in prompt_file: {prompt_file}")
                # Also check if the resolved path matches any immutable file's absolute path
                for immutable in IMMUTABLE_FILES:
                    immutable_resolved = (self.kernel_dir.parent / immutable).resolve()
                    if resolved == immutable_resolved:
                        return (False, f"Cannot modify protected file: {prompt_file}")

        # Type-specific validation
        if change_type == "remove_node":
            node_id = details.get("node_id", "")
            if not node_id:
                return (False, "remove_node requires 'node_id' in details")

        if change_type == "add_node":
            node_dict = details.get("node", {})
            if not node_dict.get("id"):
                return (False, "add_node requires 'node.id' in details")

        return (True, "Change is valid")

    def apply_change(self, change: dict, state: dict | None = None) -> bool:
        """Apply the change. Log to history.jsonl.

        Args:
            change: The change dict to apply.
            state: Optional state dict for user-owned file checking.

        Returns:
            True if the change was applied successfully.
        """
        valid, reason = self.validate_change(change, state=state)
        if not valid:
            change["status"] = "rejected"
            change["rejection_reason"] = reason
            self._log_change(change)
            return False

        change_type = change.get("type", "")
        details = change.get("details", {})

        try:
            if change_type == "add_node":
                node_dict = details.get("node", {})
                self.graph_executor.add_node(node_dict)
                self.graph_executor.save_graph()

            elif change_type == "remove_node":
                node_id = details.get("node_id", "")
                # Save node definition before removal for rollback support
                change["details"]["node_backup"] = self.graph_executor.get_node(node_id)
                self.graph_executor.remove_node(node_id)
                self.graph_executor.save_graph()

            elif change_type == "modify_prompt":
                prompt_file = details.get("prompt_file", "")
                new_content = details.get("content", "")
                prompt_path = self.kernel_dir / prompt_file
                # Save original content before modification for rollback support
                if prompt_path.exists():
                    change["details"]["original_content"] = prompt_path.read_text(encoding="utf-8")
                prompt_path.parent.mkdir(parents=True, exist_ok=True)
                with open(prompt_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            elif change_type == "reorder":
                node_order = details.get("order", [])
                if node_order:
                    nodes = self.graph_executor.graph.get("nodes", [])
                    node_map = {n["id"]: n for n in nodes}
                    new_nodes = []
                    for nid in node_order:
                        if nid in node_map:
                            new_nodes.append(node_map[nid])
                    # Add any nodes not in the order list at the end
                    for n in nodes:
                        if n["id"] not in node_order:
                            new_nodes.append(n)
                    self.graph_executor.graph["nodes"] = new_nodes
                    self.graph_executor.save_graph()

            elif change_type == "add_skill":
                from kernel.skill_factory import SkillFactory
                skill_name = details.get("name", "")
                skill_description = details.get("description", "")
                skill_content = details.get("content", "")
                skill_tags = details.get("tags", [])
                knowledge_dir = str(self.kernel_dir.parent / "knowledge")
                factory = SkillFactory(knowledge_dir)
                factory.create_skill(skill_name, skill_description, skill_content, skill_tags)

            elif change_type == "add_rule":
                # This is handled by KnowledgeStore, just log it
                pass

            change["status"] = "applied"
            self._log_change(change)
            return True

        except (ValueError, KeyError) as e:
            change["status"] = "failed"
            change["error"] = str(e)
            self._log_change(change)
            return False

    def get_history(self) -> list:
        """Read history.jsonl and return all changes.

        Returns:
            List of change records.
        """
        if not self.history_file.exists():
            return []
        records = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def rollback(self, change_id: str) -> bool:
        """Find change by ID, reverse it, log rollback.

        Args:
            change_id: The ID of the change to rollback.

        Returns:
            True if rollback was successful.
        """
        history = self.get_history()
        target_change = None
        for record in history:
            if record.get("id") == change_id:
                target_change = record
                break

        if target_change is None:
            return False

        if target_change.get("status") != "applied":
            return False

        change_type = target_change.get("type", "")
        details = target_change.get("details", {})

        try:
            if change_type == "add_node":
                node_id = details.get("node", {}).get("id", "")
                if node_id:
                    self.graph_executor.remove_node(node_id)
                    self.graph_executor.save_graph()

            elif change_type == "remove_node":
                node_dict = details.get("node_backup", details.get("node", {}))
                if node_dict:
                    self.graph_executor.add_node(node_dict)
                    self.graph_executor.save_graph()

            elif change_type == "modify_prompt":
                prompt_file = details.get("prompt_file", "")
                original_content = details.get("original_content", "")
                if prompt_file and original_content:
                    prompt_path = self.kernel_dir / prompt_file
                    with open(prompt_path, "w", encoding="utf-8") as f:
                        f.write(original_content)

            # Log rollback
            rollback_record = {
                "id": str(uuid.uuid4()),
                "type": "rollback",
                "details": {"rolled_back_change_id": change_id},
                "reason": f"Rollback of change {change_id}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "applied",
            }
            self._log_change(rollback_record)
            return True

        except (ValueError, KeyError):
            return False

    def revert_if_worse(self, change_id: str, metrics_before: dict, metrics_after: dict, threshold: float = 0.1) -> bool:
        """Revert a change if metrics have degraded beyond threshold.

        Compares success_rate before and after. If it dropped by more than
        threshold, automatically rolls back the change.

        Args:
            change_id: The ID of the change to potentially revert.
            metrics_before: Node metrics dict before the change (from EvolutionMetrics.get_node_metrics).
            metrics_after: Node metrics dict after the change.
            threshold: Maximum acceptable drop in success_rate (default 0.1 = 10%).

        Returns:
            True if the change was reverted, False if it's acceptable.
        """
        before_rate = metrics_before.get("success_rate", 0.0)
        after_rate = metrics_after.get("success_rate", 0.0)

        if before_rate - after_rate > threshold:
            # Performance degraded, rollback
            self.rollback(change_id)
            return True
        return False

    def apply_if_confident(
        self, proposals: list, threshold: float = 0.7, max_applies: int = 1
    ) -> list[dict]:
        """Filter proposals by confidence and apply those above threshold.

        For each qualifying proposal, creates a proper change dict via
        propose_change(), validates it, and applies it. Proposals that
        fail validation are skipped. Stops after max_applies successful
        applications to bound the number of changes per cycle.

        Args:
            proposals: List of proposal dicts with confidence_score.
            threshold: Minimum confidence_score to auto-apply (default 0.7).
            max_applies: Maximum number of proposals to apply (default 1).

        Returns:
            List of applied change dicts.
        """
        applied: list[dict] = []
        for proposal in proposals:
            if len(applied) >= max_applies:
                break

            confidence = proposal.get("confidence_score", 0.0)
            if confidence <= threshold:
                continue

            change_type = proposal.get("type", "")
            details = proposal.get("details", {})
            reason = proposal.get("reason", "Auto-applied by feedback loop")

            change = self.propose_change(change_type, details, reason)

            # Validate before applying
            valid, _ = self.validate_change(change)
            if not valid:
                continue

            success = self.apply_change(change)
            if success:
                applied.append(change)

        return applied

    def _log_change(self, change: dict) -> None:
        """Append a change record to history.jsonl.

        Args:
            change: The change dict to log.
        """
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(change) + "\n")
