"""Human-readable progress reporting for kernel execution."""


class Reporter:
    """Generates human-readable reports about kernel execution state."""

    def report_iteration(self, state: dict, node: dict, result: str) -> str:
        """One-line progress update for a completed iteration.

        Format: "[{iteration}/{max}] {node_id}: {result}"
        Example: "[3/30] code: success"
        Example: "[7/30] test: failed - tests_fail"

        Args:
            state: Current state dict (has iteration_count, max_iterations)
            node: Node dict (has 'id', 'description')
            result: Result string ('success', 'failed', etc.)

        Returns:
            One-line progress string.
        """
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 30)
        node_id = node.get("id", "unknown")
        return f"[{iteration}/{max_iter}] {node_id}: {result}"

    def report_completion(self, state: dict, tasks: list[dict]) -> str:
        """Final summary after execution completes.

        Multi-line report:
        - Goal
        - Status (complete/stuck/error)
        - Iterations used: X/Y
        - Tasks: done/total
        - Errors encountered: N
        - Last error (if any)

        Args:
            state: Final state dict
            tasks: List of task dicts from TaskManager

        Returns:
            Multi-line summary string.
        """
        goal = state.get("goal", "(no goal set)")
        status = state.get("status", "unknown")
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 30)
        errors = state.get("errors", [])
        error_count = len(errors)

        total_tasks = len(tasks)
        done_tasks = sum(1 for t in tasks if t.get("status") == "done")

        lines = [
            "=== Execution Summary ===",
            f"Goal: {goal}",
            f"Status: {status}",
            f"Iterations used: {iteration}/{max_iter}",
            f"Tasks: {done_tasks}/{total_tasks} complete",
            f"Errors encountered: {error_count}",
        ]
        if errors:
            lines.append(f"Last error: {errors[-1]}")

        return "\n".join(lines)

    def report_stuck(self, state: dict, node: str, errors: list[str]) -> str:
        """Report when execution is stuck on a node.

        Format:
        STUCK: Node '{node}' is not making progress
        Errors: [last 3 errors]
        Suggestion: [contextual advice]

        Suggestions based on node type:
        - 'code' node: "Check if the task is too complex. Try splitting it."
        - 'test' node: "Tests keep failing. Review test expectations."
        - other: "Consider using --retry-strategy skip to advance past this node."

        Args:
            state: Current state dict
            node: The stuck node ID string
            errors: Recent error messages

        Returns:
            Multi-line stuck report string.
        """
        lines = [f"STUCK: Node '{node}' is not making progress"]

        recent_errors = errors[-3:] if errors else []
        if recent_errors:
            lines.append("Errors:")
            for err in recent_errors:
                lines.append(f"  - {err}")
        else:
            lines.append("Errors: (none recorded)")

        if "code" in node:
            suggestion = "Check if the task is too complex. Try splitting it."
        elif "test" in node:
            suggestion = "Tests keep failing. Review test expectations."
        else:
            suggestion = "Consider using --retry-strategy skip to advance past this node."

        lines.append(f"Suggestion: {suggestion}")

        return "\n".join(lines)

    def format_status(self, state: dict, tasks: list[dict]) -> str:
        """Human-readable current status (for --status flag, no execution).

        Multi-line output:
        === Kernel Status ===
        Goal: {goal}
        Status: {status}
        Progress: iteration {N}/{max}
        Current node: {node}
        Execution mode: {mode}
        Tasks: {done}/{total} complete
        Errors: {count} ({last error preview if any})

        Args:
            state: Current state dict
            tasks: List of task dicts

        Returns:
            Formatted status string.
        """
        goal = state.get("goal", "(no goal set)")
        status = state.get("status", "idle")
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 30)
        current_node = state.get("current_node", "init")
        execution_mode = state.get("execution_mode", "kernel")
        errors = state.get("errors", [])
        error_count = len(errors)

        total_tasks = len(tasks)
        done_tasks = sum(1 for t in tasks if t.get("status") == "done")

        lines = [
            "=== Kernel Status ===",
            f"Goal: {goal}",
            f"Status: {status}",
            f"Progress: iteration {iteration}/{max_iter}",
            f"Current node: {current_node}",
            f"Execution mode: {execution_mode}",
            f"Tasks: {done_tasks}/{total_tasks} complete",
        ]

        if errors:
            last_error = errors[-1]
            # Truncate long error messages for preview
            preview = last_error[:60] + "..." if len(last_error) > 60 else last_error
            lines.append(f"Errors: {error_count} ({preview})")
        else:
            lines.append(f"Errors: {error_count}")

        return "\n".join(lines)
