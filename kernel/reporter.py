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
            "=== 执行摘要 ===",
            f"目标: {goal}",
            f"状态: {status}",
            f"迭代次数: {iteration}/{max_iter}",
            f"任务: {done_tasks}/{total_tasks} 已完成",
            f"遇到错误: {error_count}",
        ]
        if errors:
            lines.append(f"最近错误: {errors[-1]}")

        return "\n".join(lines)

    def report_completion_clean(self, state: dict, tasks: list[dict]) -> str:
        """Compact user-friendly completion summary with emoji indicators.

        Args:
            state: Final state dict.
            tasks: List of task dicts from TaskManager.

        Returns:
            Multi-line compact summary string.
        """
        status = state.get("status", "unknown")
        iteration = state.get("iteration_count", 0)
        workspace = state.get("workspace_path", "./workspace/")
        total_tasks = len(tasks)
        done_tasks = sum(1 for t in tasks if t.get("status") == "done")
        errors = state.get("errors", [])

        if status == "complete":
            lines = [
                "\u2705 \u5b8c\u6210\uff01",
                f"   \u4efb\u52a1: {done_tasks}/{total_tasks} \u5df2\u5b8c\u6210",
                f"   \u6587\u4ef6: {workspace}",
                f"   \u8017\u65f6: {iteration} \u6b21\u8fed\u4ee3",
            ]
        else:
            last_error = errors[-1] if errors else "\u672a\u77e5\u9519\u8bef"
            # Truncate long error for display
            if len(last_error) > 60:
                last_error = last_error[:60] + "..."
            lines = [
                "\u274c \u672a\u5b8c\u6210",
                f"   \u5b8c\u6210: {done_tasks}/{total_tasks} \u4efb\u52a1",
                f"   \u95ee\u9898: {last_error}",
                (
                    "   \u5efa\u8bae: \u5c1d\u8bd5\u7b80\u5316\u76ee\u6807"
                    "\uff0c\u6216\u8fd0\u884c python runner.py --goal"
                    ' "\u66f4\u7b80\u5355\u7684\u76ee\u6807" --ai-command "..."'
                ),
            ]
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
        lines = [f"卡住: 节点 '{node}' 没有进展"]

        recent_errors = errors[-3:] if errors else []
        if recent_errors:
            lines.append("错误:")
            for err in recent_errors:
                lines.append(f"  - {err}")
        else:
            lines.append("错误: (无记录)")

        if "code" in node:
            suggestion = "检查任务是否太复杂，尝试拆分任务。"
        elif "test" in node:
            suggestion = "测试持续失败，请检查测试预期。"
        else:
            suggestion = "考虑使用 --retry-strategy skip 跳过该节点。"

        lines.append(f"建议: {suggestion}")

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
            "=== 内核状态 ===",
            f"目标: {goal}",
            f"状态: {status}",
            f"进度: 迭代 {iteration}/{max_iter}",
            f"当前节点: {current_node}",
            f"执行模式: {execution_mode}",
            f"任务: {done_tasks}/{total_tasks} 已完成",
        ]

        if errors:
            last_error = errors[-1]
            # Truncate long error messages for preview
            preview = last_error[:60] + "..." if len(last_error) > 60 else last_error
            lines.append(f"错误: {error_count} ({preview})")
        else:
            lines.append(f"错误: {error_count}")

        return "\n".join(lines)
