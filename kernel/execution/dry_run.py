"""Mode 1 dry-run/scaffolding execution.

This module contains the DryRunExecutor class which handles the
scaffolding execution loop where transitions are taken without
AI evaluation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace
    from logging import Logger

    from kernel.graph_executor import GraphExecutor
    from memory.state_manager import StateManager


class DryRunExecutor:
    """Executor for Mode 1: dry-run scaffolding.

    Encapsulates the Mode 1 scaffolding loop including graph traversal
    with automatic transition selection, stuck detection, progress
    tracking, and summary generation.
    """

    def __init__(
        self,
        state_mgr: StateManager,
        graph: GraphExecutor,
        args: Namespace,
        max_retries_map: dict[str, int],
        complexity: str,
        logger: Logger,
        kernel_root: Path,
    ) -> None:
        self.state_mgr = state_mgr
        self.graph = graph
        self.args = args
        self.max_retries_map = max_retries_map
        self.complexity = complexity
        self.logger = logger
        self.kernel_root = kernel_root

    def run(self) -> None:
        """Execute the Mode 1 dry-run iteration loop."""
        for i in range(self.args.max_iterations):
            state = self.state_mgr.get_state()

            if self.state_mgr.is_complete():
                break

            try:
                node = self.graph.get_current_node(state)
            except KeyError as e:
                self.state_mgr.state["status"] = "error"
                self.state_mgr.state.setdefault("errors", []).append(str(e))
                break

            prompt_path = self.graph.get_prompt_for_node(node["id"])

            if self.args.dry_run:
                print(f"[DRY RUN] Iteration {state.get('iteration_count', 0) + 1}:")
                print(f"  Node: {node['id']}")
                print(f"  Description: {node.get('description', 'N/A')}")
                print(f"  Prompt file: {prompt_path}")

                # Load prompt to show length
                full_prompt_path = self.kernel_root / "kernel" / prompt_path
                if full_prompt_path.exists():
                    prompt_content = full_prompt_path.read_text(encoding="utf-8")
                    print(f"  Prompt length: {len(prompt_content)} chars")
                else:
                    print("  Prompt file: [not found]")

            self.state_mgr.increment_iteration()

            # SCAFFOLDING: In this mode (Mode 1), the runner always picks the first
            # available transition without evaluating conditions. This is intentional:
            # the runner does not call an LLM and cannot evaluate conditions like
            # "tests_pass" or "plan_ready". For actual condition evaluation, an AI
            # agent should read BOOT.md directly (Mode 2) and decide transitions itself.

            # Track visit BEFORE advancing so stuck detection works on failed loops
            self.state_mgr.track_node_visit(node["id"])
            is_stuck, stuck_node, visits = self.state_mgr.check_stuck(self.max_retries_map)
            if is_stuck:
                assert stuck_node is not None  # guaranteed when is_stuck=True
                # Check for stuck_handler
                try:
                    stuck_node_def = self.graph.get_node(stuck_node)
                    handler = stuck_node_def.get("stuck_handler")
                except KeyError:
                    handler = None
                if handler:
                    if self.args.dry_run:
                        print(
                            f"  STUCK: Node '{stuck_node}' exceeded max_retries "
                            f"(visited {visits} times, "
                            f"max {self.max_retries_map.get(stuck_node)})"
                        )
                        print(f"  Redirecting to stuck_handler: {handler}")
                        print()
                    self.state_mgr.set_current_node(handler)
                else:
                    if self.args.dry_run:
                        print(
                            f"  STUCK: Node '{stuck_node}' exceeded max_retries "
                            f"(visited {visits} times, "
                            f"max {self.max_retries_map.get(stuck_node)})"
                        )
                        print()
                    self.state_mgr.state["status"] = "stuck"
                    self.state_mgr.state.setdefault("errors", []).append(
                        f"Node '{stuck_node}' exceeded max_retries "
                        f"(visited {visits} times, max {self.max_retries_map.get(stuck_node)})"
                    )
                    break
                continue

            transitions = self.graph.get_available_transitions(node["id"])
            if transitions:
                next_node_id = transitions[0]["to"]

                # Medium complexity: skip reflect/evolve in scaffolding mode
                if self.complexity == "medium" and next_node_id in ("reflect", "evolve"):
                    next_node_id = "plan"
                self.state_mgr.set_current_node(next_node_id)

                if self.args.dry_run:
                    print(f"  Next node: {next_node_id}")
                    print()
            else:
                self.state_mgr.state["status"] = "complete"
                if self.args.dry_run:
                    print("  Next node: END")
                    print()
                break
