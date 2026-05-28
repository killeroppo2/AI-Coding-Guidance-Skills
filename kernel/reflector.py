"""Reflector for analyzing iteration results and proposing evolution.

This module analyzes what worked and what failed during kernel execution,
proposes evolutionary changes, and extracts learned rules from experience.
"""

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from kernel.philosophy.principles import should_simplify


class Reflector:
    """Analyzes iteration results and proposes kernel evolution.

    The reflector examines iteration data to identify patterns of success
    and failure, then proposes changes to improve the kernel's workflow.
    """

    def __init__(self, memory_dir: str, knowledge_store: Any, graph_advisor: Any = None) -> None:
        """Initialize the reflector.

        Args:
            memory_dir: Path to the memory/ directory.
            knowledge_store: A KnowledgeStore instance.
            graph_advisor: Optional GraphAdvisor for structural graph proposals.
        """
        self.memory_dir = memory_dir
        self.knowledge_store = knowledge_store
        self.graph_advisor = graph_advisor

    def suggest_graph_evolution(
        self, goal: str, skills_loaded: list[str], history: list[dict]
    ) -> list[dict]:
        """Get structural graph change proposals from the graph advisor.

        Returns empty list if no graph_advisor is configured.
        """
        if self.graph_advisor is None:
            return []
        result: list[dict] = self.graph_advisor.suggest_graph_changes(goal, skills_loaded, history)
        return result

    def analyze_iteration(self, iteration_data: dict) -> dict:
        """Analyze iteration data and produce a reflection dict.

        Args:
            iteration_data: Dict with keys: node, result, duration, errors.

        Returns:
            Reflection dict with: iteration, node, success, learnings, issues, timestamp.
        """
        errors = iteration_data.get("errors", [])
        result = iteration_data.get("result", "")
        success = len(errors) == 0 and result != "failed"

        learnings = []
        issues = []

        if success:
            learnings.append(
                f"Node '{iteration_data.get('node', 'unknown')}' completed successfully"
            )
            duration = iteration_data.get("duration", 0)
            if duration and duration > 0:
                learnings.append(f"Execution took {duration}s")
        else:
            for error in errors:
                issues.append(f"Error: {error}")
            if result == "failed":
                issues.append(f"Node '{iteration_data.get('node', 'unknown')}' returned failure")

        return {
            "iteration": iteration_data.get("iteration", 0),
            "node": iteration_data.get("node", "unknown"),
            "success": success,
            "learnings": learnings,
            "issues": issues,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "philosophy_signals": {"stop_suggested": False},
        }

    def categorize_failure(self, errors: list, result: str = "") -> str:
        """Categorize a failure based on error messages and result.

        Categories:
        - 'timeout': timeout-related errors
        - 'test_failure': test execution failures
        - 'code_error': syntax/runtime code errors
        - 'dependency_issue': import/dependency problems
        - 'unknown': cannot categorize

        Args:
            errors: List of error message strings.
            result: The result string from iteration.

        Returns:
            One of the category strings above.
        """
        all_text = " ".join(errors).lower() + " " + result.lower()

        if "timeout" in all_text or "timed out" in all_text:
            return "timeout"
        if "import" in all_text or "dependency" in all_text or "module not found" in all_text:
            return "dependency_issue"
        if "test" in all_text and ("fail" in all_text or "error" in all_text):
            return "test_failure"
        if (
            "syntax" in all_text
            or "nameerror" in all_text
            or "typeerror" in all_text
            or "attributeerror" in all_text
        ):
            return "code_error"
        if "error" in all_text or "exception" in all_text or "fail" in all_text:
            return "code_error"
        return "unknown"

    def propose_evolution(self, reflections: list) -> list:
        """Analyze recent reflections and propose changes.

        Rules:
        - If same node fails 3+ times, propose removing or modifying it.
        - If a pattern of success emerges, propose adding it as a rule.

        Each proposal includes a confidence_score and failure_category.

        Args:
            reflections: List of reflection dicts.

        Returns:
            List of change proposal dicts.
        """
        proposals = []

        # Count failures per node and collect error info
        failure_counts: Counter = Counter()
        success_counts: Counter = Counter()
        node_errors: dict[str, list] = {}
        node_results: dict[str, list] = {}
        for reflection in reflections:
            node = reflection.get("node", "unknown")
            if not reflection.get("success", True):
                failure_counts[node] += 1
                if node not in node_errors:
                    node_errors[node] = []
                    node_results[node] = []
                node_errors[node].extend(reflection.get("issues", []))
                node_results[node].append(reflection.get("result", ""))
            else:
                success_counts[node] += 1

        # Propose modifications for repeatedly failing nodes
        for node, count in failure_counts.items():
            if count >= 3:
                # Determine failure category from collected errors
                errors = node_errors.get(node, [])
                results = node_results.get(node, [])
                # Categorize each failure and find most common
                categories = []
                for i in range(count):
                    err_subset = errors[i : i + 1] if i < len(errors) else []
                    res = results[i] if i < len(results) else ""
                    categories.append(self.categorize_failure(err_subset, res))

                category_counts = Counter(categories)
                most_common_category = (
                    category_counts.most_common(1)[0][0] if categories else "unknown"
                )

                # Calculate confidence score
                data_points = count
                data_factor = min(1.0, data_points / 10)
                # Consistency: all same category = 1.0, mixed = 0.7, few data points = 0.5
                if data_points <= 2:
                    consistency_factor = 0.5
                elif len(category_counts) == 1:
                    consistency_factor = 1.0
                else:
                    consistency_factor = 0.7
                confidence_score = data_factor * consistency_factor

                proposals.append(
                    {
                        "type": "modify_prompt",
                        "details": {
                            "node_id": node,
                            "prompt_file": f"prompts/{node}.md",
                        },
                        "reason": (
                            f"Node '{node}' has failed {count} times"
                            " - prompt may need revision"
                        ),
                        "confidence_score": confidence_score,
                        "failure_category": most_common_category,
                    }
                )

                # Philosophy: suggest simplification for high failure counts
                if should_simplify(count):
                    proposals.append(
                        {
                            "type": "modify_prompt",
                            "details": {
                                "node_id": node,
                                "prompt_file": f"prompts/{node}.md",
                            },
                            "reason": (
                                f"\u5927\u9053\u81f3\u7b80: consider splitting this task"
                                f" - node '{node}' has failed {count} times"
                            ),
                            "confidence_score": min(1.0, count / 10) * 0.8,
                            "failure_category": "complexity",
                        }
                    )

        # Propose rules for consistently successful patterns
        for node, count in success_counts.items():
            if count >= 5:
                proposals.append(
                    {
                        "type": "add_rule",
                        "details": {
                            "name": f"success_pattern_{node}",
                            "description": f"Node '{node}' succeeds consistently ({count} times)",
                            "tags": ["learned", "success-pattern"],
                        },
                        "reason": (
                            f"Node '{node}' has succeeded {count} times - pattern worth preserving"
                        ),
                        "confidence_score": min(1.0, count / 10),
                        "failure_category": None,
                    }
                )

        return proposals

    def extract_rules(self, reflections: list) -> list:
        """Extract learned rules from patterns in reflections.

        Args:
            reflections: List of reflection dicts.

        Returns:
            List of rule dicts suitable for KnowledgeStore.add_rule().
        """
        rules = []

        # Group learnings by node
        node_learnings: dict[str, list[str]] = {}
        for reflection in reflections:
            node = reflection.get("node", "unknown")
            if node not in node_learnings:
                node_learnings[node] = []
            node_learnings[node].extend(reflection.get("learnings", []))

        # Extract rules from repeated learnings
        for node, learnings in node_learnings.items():
            if len(learnings) >= 3:
                rules.append(
                    {
                        "name": f"learned_from_{node}",
                        "description": f"Patterns observed from node '{node}' execution",
                        "content": "\n".join(set(learnings)),
                        "tags": ["learned", node],
                        "source": "reflector",
                    }
                )

        return rules

    def summarize_progress(self, state: dict) -> str:
        """Return human-readable progress summary.

        Args:
            state: The current state dict.

        Returns:
            Human-readable progress summary string.
        """
        goal = state.get("goal", "No goal set")
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 30)
        status = state.get("status", "unknown")
        current_node = state.get("current_node", "unknown")
        errors = state.get("errors", [])

        lines = [
            f"Goal: {goal}",
            f"Status: {status}",
            f"Progress: iteration {iteration}/{max_iter}",
            f"Current node: {current_node}",
        ]

        if errors:
            lines.append(f"Errors ({len(errors)}): {errors[-1]}")

        return "\n".join(lines)
