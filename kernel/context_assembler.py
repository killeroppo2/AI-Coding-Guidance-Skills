"""Context assembler for Mode 3 AI execution.

This module assembles a full context prompt from kernel components,
suitable for piping to an AI CLI tool via subprocess.
"""

import sys
from pathlib import Path
from typing import Any

import yaml


class ContextAssembler:
    """Assembles full context prompt from kernel components."""

    # Tiering rules: section_key -> list of allowed node IDs, or None for all nodes
    TIER_RULES: dict[str, list[str] | None] = {
        "boot": ["init"],
        "constitution": ["init"],
        "dao": ["reflect", "evolve"],
        "strategy": ["plan", "reflect"],
        "output_format": None,
        "evolution_history": ["reflect", "evolve"],
        "recent_reflections": ["reflect"],
        "node_prompt": None,
        "state_summary": None,
        "current_task": ["code", "test", "review"],
        "plan": ["plan", "code"],
        "workspace_manifest": ["code", "test", "review"],
        "decisions": ["reflect"],
    }

    def __init__(self, kernel_root: Path, max_skill_content_chars: int = 8000):
        """Initialize the context assembler.

        Args:
            kernel_root: Path to the project root directory.
            max_skill_content_chars: Maximum characters allowed per skill content.
        """
        self.kernel_root = kernel_root
        self.max_skill_content_chars = max_skill_content_chars
        self._last_node_id: str | None = None
        self._last_iteration_count: int = 0
        self._last_successful: bool = False

    def _should_include(self, section_key: str, node_id: str | None,
                        tier_rules: dict) -> bool:
        """Check if a section should be included for the given node.

        Args:
            section_key: The key identifying the section in tier_rules.
            node_id: The current node ID, or None for backward compat.
            tier_rules: Dict mapping section keys to allowed node ID lists.

        Returns:
            True if the section should be included.
        """
        if node_id is None:
            return True
        allowed = tier_rules.get(section_key)
        if allowed is None:
            return True
        return node_id in allowed

    def assemble(self, state: dict, node: dict, graph_executor: Any,
                 knowledge_store: Any, token_budget: int = 32000) -> str:
        """Assemble full context from BOOT.md + state + node prompt + philosophy + skills.

        Returns a single formatted string suitable for piping to an AI.

        Args:
            state: Current state dict from StateManager.
            node: Current node dict from GraphExecutor.
            graph_executor: GraphExecutor instance for prompt path resolution.
            knowledge_store: KnowledgeStore instance for skill loading.
            token_budget: Maximum estimated tokens (len//4). Default 32000.

        Returns:
            A single formatted string with all context sections.
        """
        node_id = node.get("id", None)

        tier_rules = self.TIER_RULES

        sections = []

        # 1. BOOT.md (core)
        if self._should_include("boot", node_id, tier_rules):
            boot_path = self.kernel_root / "kernel" / "BOOT.md"
            boot_content = self._read_file(boot_path)
            sections.append(f"=== BOOT SEQUENCE ===\n\n{boot_content}")

        # 2. Constitution (core)
        if self._should_include("constitution", node_id, tier_rules):
            const_path = self.kernel_root / "kernel" / "constitution.md"
            const_content = self._read_file(const_path)
            if const_content and not const_content.startswith("(file not found"):
                sections.append(f"=== CONSTITUTION (IMMUTABLE) ===\n\n{const_content}")

        # 3. Current state summary (core - always included)
        state_summary = self._format_state(state)
        sections.append(f"=== CURRENT STATE ===\n\n{state_summary}")

        # 4. Current task from tasks.yaml (core)
        if self._should_include("current_task", node_id, tier_rules):
            current_task = self._load_current_task()
            if current_task:
                sections.append(f"=== CURRENT TASK ===\n\n{current_task}")

        # 4b. Progress (trimmable - priority 4, removed last among trimmable)
        progress_content = self._load_progress()
        progress_section = ""
        if progress_content:
            progress_section = f"=== PROGRESS ===\n\n{progress_content}"

        # 4c. Plan (trimmable - priority 3)
        plan_section = ""
        if self._should_include("plan", node_id, tier_rules):
            plan_content = self._load_plan()
            if plan_content:
                plan_section = f"=== PLAN ===\n\n{plan_content}"

        # 4d. Workspace Manifest (trimmable - priority 2)
        workspace_section = ""
        if self._should_include("workspace_manifest", node_id, tier_rules):
            workspace_path = state.get("workspace_path", "")
            workspace_content = self._load_workspace_manifest(workspace_path)
            if workspace_content:
                workspace_section = f"=== WORKSPACE MANIFEST ===\n\n{workspace_content}"

        # 4e. Recent Decisions (trimmable - priority 1, removed first)
        decisions_section = ""
        if self._should_include("decisions", node_id, tier_rules):
            decisions_content = self._load_recent_decisions()
            if decisions_content:
                decisions_section = f"=== RECENT DECISIONS ===\n\n{decisions_content}"

        # 5. Current node's prompt file (core - always included)
        prompt_file = graph_executor.get_prompt_for_node(node.get("id", ""))
        if prompt_file:
            prompt_path = self.kernel_root / "kernel" / prompt_file
            prompt_content = self._read_file(prompt_path)
        else:
            prompt_content = "(no prompt file configured for this node)"
        sections.append(f"=== NODE PROMPT ({node.get('id', 'unknown')}) ===\n\n{prompt_content}")

        # 6. Philosophy - dao.md
        if self._should_include("dao", node_id, tier_rules):
            dao_path = self.kernel_root / "kernel" / "philosophy" / "dao.md"
            dao_content = self._read_file(dao_path)
            sections.append(f"=== PHILOSOPHY: DAO ===\n\n{dao_content}")

        # 7. Philosophy - strategy.md
        if self._should_include("strategy", node_id, tier_rules):
            strategy_path = self.kernel_root / "kernel" / "philosophy" / "strategy.md"
            strategy_content = self._read_file(strategy_path)
            sections.append(f"=== PHILOSOPHY: STRATEGY ===\n\n{strategy_content}")

        # 8. Skills loaded in state
        skills_loaded = state.get("context", {}).get("skills_loaded", [])
        if skills_loaded:
            skills_section = self._load_skills(skills_loaded, knowledge_store)
            sections.append(f"=== LOADED SKILLS ===\n\n{skills_section}")

        # 9. Output format contract (always included)
        contract_path = self.kernel_root / "kernel" / "contracts" / "output_format.md"
        contract_content = self._read_file(contract_path)
        if not contract_content.startswith("(file not found"):
            sections.append(
                f"=== OUTPUT FORMAT CONTRACT ===\n\n{contract_content}"
            )

        # 10. Evolution history
        if self._should_include("evolution_history", node_id, tier_rules):
            evolution_history = self._load_evolution_history(count=5)
            if evolution_history:
                sections.append(
                    f"=== EVOLUTION HISTORY ===\n\n{evolution_history}"
                )

        # 11. Recent reflections
        if self._should_include("recent_reflections", node_id, tier_rules):
            recent_reflections = self._load_recent_reflections(count=3)
            if recent_reflections:
                sections.append(
                    f"=== RECENT REFLECTIONS ===\n\n{recent_reflections}"
                )

        # Apply token budgeting: trimmable sections in removal order
        # (least important first: decisions, workspace, plan, progress)
        trimmable = [decisions_section, workspace_section,
                     plan_section, progress_section]

        # Start with all trimmable sections included
        active_trimmable = [s for s in trimmable if s]

        # Build full text and check budget
        def _build_text(core: list, extra: list) -> str:
            all_parts = []
            # Insert extra sections after core sections (after section 4)
            # Core sections end at index where NODE PROMPT starts
            node_prompt_idx = None
            for i, s in enumerate(core):
                if s.startswith("=== NODE PROMPT"):
                    node_prompt_idx = i
                    break
            if node_prompt_idx is not None:
                all_parts = core[:node_prompt_idx] + extra + core[node_prompt_idx:]
            else:
                all_parts = core + extra
            return "\n\n".join(all_parts)

        full_text = _build_text(sections, active_trimmable)
        estimated_tokens = len(full_text) // 4

        # Remove sections from least important until within budget
        while estimated_tokens > token_budget and active_trimmable:
            # Remove the first item (least important remaining)
            active_trimmable.pop(0)
            full_text = _build_text(sections, active_trimmable)
            estimated_tokens = len(full_text) // 4

        # Check total context size and warn if over recommended limit
        all_sections = sections + active_trimmable
        self._estimate_total_context_size(all_sections)

        return full_text

    def assemble_incremental(self, state: dict, node: dict, graph_executor: Any,
                             knowledge_store: Any) -> str:
        """Assemble a reduced incremental context for repeated same-node execution.

        Used when the same node is executing consecutively after a successful
        iteration. Only includes: output_format, node prompt, state summary,
        and a delta section.

        Args:
            state: Current state dict.
            node: Current node dict.
            graph_executor: GraphExecutor instance.
            knowledge_store: KnowledgeStore instance.

        Returns:
            A reduced context string, or empty string if incremental is not applicable.
        """
        node_id = node.get("id")

        # Only use incremental if same node as last time and last was successful
        if node_id != self._last_node_id or not self._last_successful:
            # Reset and signal caller to use full context
            self._last_node_id = node_id
            self._last_successful = False
            return ""

        sections = []

        # Always include state summary
        state_summary = self._format_state(state)
        sections.append(
            "=== INCREMENTAL UPDATE ===\n\n"
            "This is a continuation on the same node. "
            "Only changed context is shown below."
        )
        sections.append(f"=== CURRENT STATE ===\n\n{state_summary}")

        # Always include current task
        current_task = self._load_current_task()
        if current_task:
            sections.append(f"=== CURRENT TASK ===\n\n{current_task}")

        # Always include node prompt
        prompt_file = graph_executor.get_prompt_for_node(node_id)
        if prompt_file:
            prompt_path = self.kernel_root / "kernel" / prompt_file
            prompt_content = self._read_file(prompt_path)
        else:
            prompt_content = "(no prompt file configured for this node)"
        sections.append(f"=== NODE PROMPT ({node_id}) ===\n\n{prompt_content}")

        # Always include output format
        contract_path = self.kernel_root / "kernel" / "contracts" / "output_format.md"
        contract_content = self._read_file(contract_path)
        if not contract_content.startswith("(file not found"):
            sections.append(f"=== OUTPUT FORMAT CONTRACT ===\n\n{contract_content}")

        return "\n\n".join(sections)

    def mark_iteration_success(self, node_id: str) -> None:
        """Mark that the last iteration on this node was successful.

        Args:
            node_id: The node ID that succeeded.
        """
        self._last_node_id = node_id
        self._last_successful = True
        self._last_iteration_count += 1

    def mark_iteration_failure(self) -> None:
        """Mark that the last iteration failed, resetting incremental state."""
        self._last_successful = False

    def _load_progress(self) -> str:
        """Load progress information from memory/progress.yaml.

        Returns:
            Formatted progress string, or empty string if file doesn't exist.
        """
        progress_path = self.kernel_root / "memory" / "progress.yaml"
        if not progress_path.exists():
            return ""
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data or not isinstance(data, dict):
                return ""
            iteration = data.get("iteration", 0)
            tasks_done = data.get("tasks_done", 0)
            tasks_total = data.get("tasks_total", 0)
            status = data.get("status", "unknown")
            return (
                f"Iteration: {iteration}, Tasks: "
                f"{tasks_done}/{tasks_total} done, Status: {status}"
            )
        except (yaml.YAMLError, OSError):
            return ""

    def _load_recent_decisions(self, count: int = 5) -> str:
        """Load the last N decisions from memory/decisions.jsonl.

        Args:
            count: Number of recent decisions to load.

        Returns:
            Formatted string of recent decisions, or empty string.
        """
        import json

        decisions_path = self.kernel_root / "memory" / "decisions.jsonl"
        if not decisions_path.exists():
            return ""

        records: list[dict] = []
        with open(decisions_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        if not records:
            return ""

        recent = records[-count:]
        lines = []
        for entry in recent:
            timestamp = entry.get("timestamp", "")
            decision_type = entry.get("type", "unknown")
            summary = entry.get("summary", "")
            lines.append(f"- [{timestamp}] {decision_type}: {summary}")
        return "\n".join(lines)

    def _load_workspace_manifest(self, workspace_path: str,
                                 max_entries: int = 100) -> str:
        """List files in the workspace directory recursively.

        Args:
            workspace_path: Path to the workspace directory.
            max_entries: Maximum number of file entries to include.

        Returns:
            Tree-like file listing, or empty string if path doesn't exist.
        """
        if not workspace_path:
            return ""
        wp = Path(workspace_path)
        if not wp.exists() or not wp.is_dir():
            return ""

        entries: list[str] = []
        try:
            for item in sorted(wp.rglob("*")):
                if len(entries) >= max_entries:
                    entries.append(f"... (truncated at {max_entries} entries)")
                    break
                rel = item.relative_to(wp)
                if item.is_dir():
                    entries.append(f"{rel}/")
                else:
                    entries.append(str(rel))
        except OSError:
            return ""

        return "\n".join(entries)

    def _load_plan(self) -> str:
        """Load plan content from memory/plan.md.

        Returns:
            Plan content, or empty string if file doesn't exist or is empty.
        """
        plan_path = self.kernel_root / "memory" / "plan.md"
        if not plan_path.exists():
            return ""
        try:
            content = plan_path.read_text(encoding="utf-8").strip()
            return content
        except OSError:
            return ""

    def _load_current_task(self) -> str:
        """Load the current task from memory/tasks.yaml.

        Uses TaskManager for consistent task selection logic. Finds the
        in_progress task first, or the first eligible pending task
        (whose dependencies are all done).

        Returns:
            Formatted task string, or empty string if no task is available.
        """
        from kernel.task_manager import TaskManager

        memory_dir = str(self.kernel_root / "memory")
        task_mgr = TaskManager(memory_dir)
        tasks = task_mgr.load_tasks()
        if not tasks:
            return ""

        # First check for in_progress task
        current = None
        for task in tasks:
            if task.get("status") == "in_progress":
                current = task
                break

        # If none in progress, get next eligible pending
        if current is None:
            current = task_mgr.get_next_task()

        if current is None:
            return ""

        lines = []
        lines.append(f"ID: {current['id']}")
        lines.append(f"Title: {current.get('title', '(no title)')}")
        lines.append(f"Status: {current.get('status', 'pending')}")
        lines.append(f"Description: {current.get('description', '(no description)')}")
        criteria = current.get("acceptance_criteria", [])
        if criteria:
            lines.append("Acceptance Criteria:")
            for criterion in criteria:
                lines.append(f"  - {criterion}")
        deps = current.get("dependencies", [])
        if deps:
            lines.append(f"Dependencies: {', '.join(deps)}")
        lines.append(f"Complexity: {current.get('complexity', 'medium')}")
        return "\n".join(lines)

    def _read_file(self, path: Path) -> str:
        """Read a file, returning placeholder if not found.

        Args:
            path: Path to the file.

        Returns:
            File content or a not-found message.
        """
        if path.exists():
            return path.read_text(encoding="utf-8")
        return f"(file not found: {path.name})"

    def _format_state(self, state: dict) -> str:
        """Format state dict as a readable summary.

        Args:
            state: The state dictionary.

        Returns:
            Formatted string representation of state.
        """
        lines = []
        lines.append(f"Goal: {state.get('goal', '(none)')}")
        lines.append(f"Current Node: {state.get('current_node', 'unknown')}")
        lines.append(f"Iteration: {state.get('iteration_count', 0)}")
        lines.append(f"Max Iterations: {state.get('max_iterations', 30)}")
        lines.append(f"Status: {state.get('status', 'unknown')}")
        workspace_path = state.get("workspace_path", "")
        if workspace_path:
            lines.append(f"Workspace: {workspace_path}")
        errors = state.get("errors", [])
        if errors:
            lines.append(f"Errors: {errors}")
        context = state.get("context", {})
        if context.get("current_task"):
            lines.append(f"Current Task: {context['current_task']}")
        if context.get("phase"):
            lines.append(f"Phase: {context['phase']}")
        return "\n".join(lines)

    def _load_skills(self, skill_names: list, knowledge_store: Any) -> str:
        """Load skill content for all listed skills using SkillComposer.

        Attempts to load actual SKILL.md content via SkillComposer. Falls back
        to descriptions if compose fails. Truncates if total content exceeds
        max_skill_content_chars * len(skill_names).

        Args:
            skill_names: List of skill names to load.
            knowledge_store: KnowledgeStore instance.

        Returns:
            Combined skill content or descriptions.
        """
        from knowledge.skill_composer import SkillComposer

        composer = SkillComposer(knowledge_store)
        try:
            content = composer.compose(skill_names, max_tokens=4000)
        except (ValueError, FileNotFoundError):
            # Fallback to descriptions if compose fails
            parts = []
            for name in skill_names:
                try:
                    skill = knowledge_store.get_skill(name)
                    parts.append(f"- {name}: {skill.get('description', '(no description)')}")
                except KeyError:
                    parts.append(f"- {name}: (skill not found)")
            content = "\n".join(parts)

        # Apply total skill content limit
        max_total = self.max_skill_content_chars * len(skill_names)
        if len(content) > max_total:
            content = self._truncate_skill_content(content, max_total)

        return content

    def _truncate_skill_content(self, content: str, max_chars: int) -> str:
        """Truncate skill content that exceeds max_chars.

        Attempts summary mode first: keeps intro + first section (before the
        second ## heading). If that's still too long or no heading found,
        hard-truncates at max_chars.

        Args:
            content: The skill content string.
            max_chars: Maximum allowed characters.

        Returns:
            Truncated content with appropriate marker.
        """
        if len(content) <= max_chars:
            return content

        # Try summary mode: find the second ## heading
        lines = content.split("\n")
        heading_positions = []
        for i, line in enumerate(lines):
            if line.startswith("## "):
                heading_positions.append(i)

        if len(heading_positions) >= 2:
            # Keep everything before the second ## heading
            summary = "\n".join(lines[:heading_positions[1]])
            if len(summary) <= max_chars:
                return summary + "\n\n[TRUNCATED - see individual skill files for full content]"

        # Hard truncate at last newline before max_chars to avoid splitting mid-line
        cut_point = content.rfind("\n", 0, max_chars)
        if cut_point <= 0:
            cut_point = max_chars  # No newline found, hard cut
        return content[:cut_point] + "\n...[TRUNCATED]"

    def _estimate_total_context_size(self, sections: list[str]) -> int:
        """Compute total character count from all sections.

        Emits a warning to stderr if total exceeds 100000 chars.

        Args:
            sections: List of section strings.

        Returns:
            Total character count.
        """
        total = sum(len(s) for s in sections)
        if total > 100000:
            print(
                f"[WARNING] Context size ({total} chars) exceeds recommended "
                f"limit. Skills may be over-loaded.",
                file=sys.stderr,
            )
        return total

    def _load_evolution_history(self, count: int = 5) -> str:
        """Load the last N entries from evolution/history.jsonl.

        Args:
            count: Number of recent history entries to load.

        Returns:
            Formatted string of recent evolution history, or empty string.
        """
        import json

        history_path = self.kernel_root / "kernel" / "evolution" / "history.jsonl"
        if not history_path.exists():
            return ""

        records: list[dict] = []
        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        recent = records[-count:]
        if not recent:
            return ""

        lines = []
        for entry in recent:
            status = entry.get("status", "unknown")
            change_type = entry.get("type", "unknown")
            reason = entry.get("reason", "")
            timestamp = entry.get("timestamp", "")
            lines.append(f"- [{status}] {change_type}: {reason} ({timestamp})")
        return "\n".join(lines)

    def _load_recent_reflections(self, count: int = 3) -> str:
        """Load the last N reflections from memory/reflections.jsonl.

        Args:
            count: Number of recent reflections to load.

        Returns:
            Formatted string of recent reflections, or empty string.
        """
        import json

        reflections_path = self.kernel_root / "memory" / "reflections.jsonl"
        if not reflections_path.exists():
            return ""

        records: list[dict] = []
        with open(reflections_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        recent = records[-count:]
        if not recent:
            return ""

        lines = []
        for entry in recent:
            node = entry.get("node", "unknown")
            success = entry.get("success", False)
            learnings = entry.get("learnings", [])
            issues = entry.get("issues", [])
            result_str = "success" if success else "failure"
            lines.append(f"- Node '{node}' ({result_str})")
            for learning in learnings:
                lines.append(f"  Learning: {learning}")
            for issue in issues:
                lines.append(f"  Issue: {issue}")
        return "\n".join(lines)
