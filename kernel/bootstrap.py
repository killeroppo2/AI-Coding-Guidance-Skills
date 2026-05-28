"""Bootstrap generator for consolidated prompt assembly.

Generates a single unified prompt from all kernel components for use
in Mode 3 (AI subprocess) or --generate-prompt output.
"""

from pathlib import Path

import yaml


class BootstrapGenerator:
    """Generates a consolidated prompt from all kernel components.

    Assembles BOOT.md, constitution, state, current prompt, philosophy,
    and relevant skills into a single prompt string.
    """

    def __init__(self, kernel_root: Path):
        """Initialize with kernel root directory.

        Args:
            kernel_root: Path to the project root (parent of kernel/).
        """
        self.kernel_root = kernel_root

    def generate(
        self,
        state_path: str | None = None,
        graph_path: str | None = None,
        knowledge_dir: str | None = None,
    ) -> str:
        """Generate the full consolidated prompt.

        Reads all kernel components and assembles them into one string.

        Args:
            state_path: Path to state.yaml (defaults to kernel/state.yaml)
            graph_path: Path to graph.yaml (defaults to kernel/graph.yaml)
            knowledge_dir: Path to knowledge/ directory (defaults to knowledge/)

        Returns:
            Complete consolidated prompt string.
        """
        # Use defaults if not provided
        if state_path is None:
            state_path = str(self.kernel_root / "kernel" / "state.yaml")
        if graph_path is None:
            graph_path = str(self.kernel_root / "kernel" / "graph.yaml")
        if knowledge_dir is None:
            knowledge_dir = str(self.kernel_root / "knowledge")

        sections = []

        # 1. BOOT.md
        boot_path = self.kernel_root / "kernel" / "BOOT.md"
        if boot_path.exists():
            sections.append(("BOOT SEQUENCE", boot_path.read_text(encoding="utf-8")))

        # 2. Constitution
        const_path = self.kernel_root / "kernel" / "constitution.md"
        if const_path.exists():
            sections.append(("CONSTITUTION (IMMUTABLE)", const_path.read_text(encoding="utf-8")))

        # 3. Current state
        state_file = Path(state_path)
        if state_file.exists():
            with open(state_file, "r", encoding="utf-8") as f:
                state = yaml.safe_load(f) or {}
            state_summary = self._format_state(state)
            sections.append(("CURRENT STATE", state_summary))
        else:
            state = {}

        # 4. Current node's prompt
        graph_file = Path(graph_path)
        if graph_file.exists():
            with open(graph_file, "r", encoding="utf-8") as f:
                graph = yaml.safe_load(f) or {}
            current_node = state.get("current_node", graph.get("default_start", "init"))
            nodes = graph.get("nodes", [])
            prompt_file = ""
            for node in nodes:
                if node.get("id") == current_node:
                    prompt_file = node.get("prompt_file", "")
                    break
            if prompt_file:
                full_prompt_path = self.kernel_root / "kernel" / prompt_file
                if full_prompt_path.exists():
                    content = full_prompt_path.read_text(encoding="utf-8")
                    sections.append(("CURRENT ROLE PROMPT", content))

        # 5. Philosophy
        dao_path = self.kernel_root / "kernel" / "philosophy" / "dao.md"
        if dao_path.exists():
            sections.append(("PHILOSOPHY: DAO", dao_path.read_text(encoding="utf-8")))

        strategy_path = self.kernel_root / "kernel" / "philosophy" / "strategy.md"
        if strategy_path.exists():
            sections.append(("PHILOSOPHY: STRATEGY", strategy_path.read_text(encoding="utf-8")))

        # Format output
        output_parts = []
        for title, content in sections:
            output_parts.append(f"{'=' * 60}")
            output_parts.append(f"=== {title} ===")
            output_parts.append(f"{'=' * 60}")
            output_parts.append("")
            output_parts.append(content.strip())
            output_parts.append("")

        return "\n".join(output_parts)

    def _format_state(self, state: dict) -> str:
        """Format state dict as readable text."""
        lines = []
        lines.append(f"Goal: {state.get('goal', 'No goal set')}")
        lines.append(f"Current Node: {state.get('current_node', 'init')}")
        lines.append(f"Status: {state.get('status', 'idle')}")
        iter_count = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 30)
        lines.append(f"Iteration: {iter_count} / {max_iter}")
        errors = state.get("errors", [])
        if errors:
            lines.append(f"Last Error: {errors[-1]}")
        return "\n".join(lines)
