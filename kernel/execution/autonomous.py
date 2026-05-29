"""Mode 3 autonomous execution via AI subprocess.

This module contains the AutonomousExecutor class which handles the
full AI-driven execution loop including context assembly, subprocess
invocation, contract validation, and feedback integration.
"""

from __future__ import annotations

import asyncio
import re
import shlex
import time
from typing import TYPE_CHECKING

from kernel.error_messages import format_error
from kernel.execution.protocol import (
    check_should_stop,
    resolve_transition,
    update_progress_history,
)
from kernel.philosophy.guards import bing_gui_shen_su, shui_guard, wu_wei_guard
from kernel.philosophy.principles import should_retreat
from kernel.reporter import Reporter
from kernel.security_policy import SecurityPolicy
from kernel.validators import _validate_workspace_paths

if TYPE_CHECKING:
    from argparse import Namespace
    from logging import Logger

    from kernel.context_assembler import ContextAssembler
    from kernel.context_budget import ContextBudgetTracker
    from kernel.contracts import OutputContractValidator
    from kernel.event_detector import EventDetector
    from kernel.evolution.engine import EvolutionEngine
    from kernel.evolution.metrics import EvolutionMetrics
    from kernel.feedback_loop import FeedbackLoop
    from kernel.graph_executor import GraphExecutor
    from kernel.intent_analyzer import IntentResult
    from kernel.lifecycle_guard import LifecycleGuard
    from kernel.phase_router import PhaseRouter
    from kernel.providers.subprocess_provider import SubprocessProvider
    from kernel.reflector import Reflector
    from kernel.session_tracker import SessionTracker
    from kernel.skill_feedback import SkillFeedbackStore
    from kernel.skill_triggers import SkillTriggerEngine
    from knowledge.store import KnowledgeStore
    from memory.state_manager import StateManager

# Maximum delay in seconds for exponential backoff retry strategy
MAX_BACKOFF_DELAY_SECONDS = 60

# Maximum characters to capture from partial output in timeout messages
PARTIAL_OUTPUT_PREVIEW_LENGTH = 200


def _run_post_iteration(
    feedback_store: SkillFeedbackStore,
    trigger_engine: SkillTriggerEngine,
    state_mgr: StateManager,
    node_id: str,
    outcome: str,
    goal_type: str,
    logger: Logger,
) -> None:
    """Run trigger evaluation and feedback recording after an iteration."""
    # Check auto-triggers first
    _triggers = trigger_engine.evaluate(state_mgr.state, node_id, outcome)
    if _triggers:
        _current_skills = state_mgr.state.get("context", {}).get("skills_loaded", [])
        for _trig in _triggers:
            if _trig.skill not in _current_skills:
                _current_skills.append(_trig.skill)
                logger.info(
                    f"[触发] {_trig.trigger_name}: "
                    f"为 {_trig.target_node} 激活 {_trig.skill}"
                )
        state_mgr.state["context"]["skills_loaded"] = _current_skills

    # Record skill feedback AFTER triggers (captures triggered skills)
    feedback_store.record(
        node_id=node_id,
        skills_used=state_mgr.state.get("context", {}).get("skills_loaded", []),
        outcome=outcome,
        goal_type=goal_type,
    )


class AutonomousExecutor:
    """Executor for Mode 3: AI subprocess-driven execution.

    Encapsulates the full Mode 3 execution loop including context assembly,
    AI subprocess invocation via SubprocessProvider, transition resolution,
    contract validation, philosophy guard checks, and feedback integration.
    """

    def __init__(
        self,
        state_mgr: StateManager,
        graph: GraphExecutor,
        knowledge: KnowledgeStore,
        assembler: ContextAssembler,
        validator: OutputContractValidator,
        reflector: Reflector,
        evolution_engine: EvolutionEngine,
        evolution_metrics: EvolutionMetrics,
        feedback_loop: FeedbackLoop,
        event_detector: EventDetector,
        trigger_engine: SkillTriggerEngine,
        feedback_store: SkillFeedbackStore,
        session_tracker: SessionTracker,
        phase_router: PhaseRouter,
        intent_result: IntentResult,
        args: Namespace,
        logger: Logger,
        provider: SubprocessProvider,
        budget_tracker: ContextBudgetTracker | None,
        lifecycle_guard: LifecycleGuard,
        max_retries_map: dict[str, int],
        tracking_enabled: bool,
        memory_dir: str,
        complexity: str,
    ) -> None:
        self.state_mgr = state_mgr
        self.graph = graph
        self.knowledge = knowledge
        self.assembler = assembler
        self.validator = validator
        self.reflector = reflector
        self.evolution_engine = evolution_engine
        self.evolution_metrics = evolution_metrics
        self.feedback_loop = feedback_loop
        self.event_detector = event_detector
        self.trigger_engine = trigger_engine
        self.feedback_store = feedback_store
        self.session_tracker = session_tracker
        self.phase_router = phase_router
        self.intent_result = intent_result
        self.args = args
        self.logger = logger
        self.provider = provider
        self.budget_tracker = budget_tracker
        self.lifecycle_guard = lifecycle_guard
        self.max_retries_map = max_retries_map
        self.tracking_enabled = tracking_enabled
        self.memory_dir = memory_dir
        self.complexity = complexity

        # Instance state for retry logic
        self.retry_lightweight = False
        self._last_was_lightweight = False

    def _bootstrap_workspace(self) -> None:
        """Generate CLAUDE.md in workspace if workspace_path is set."""
        workspace_path = self.state_mgr.state.get("workspace_path", "")
        if not workspace_path:
            return

        from kernel.workspace_bootstrap import generate_claude_md

        goal = self.state_mgr.state.get("goal", "")
        # Load tasks if available
        from pathlib import Path as _Path

        tasks_file = _Path(self.memory_dir) / "tasks.yaml"
        tasks = None
        if tasks_file.exists():
            import yaml as _yaml

            with open(tasks_file, "r", encoding="utf-8") as f:
                tasks_data = _yaml.safe_load(f) or {}
            tasks = tasks_data.get("tasks")

        generate_claude_md(workspace_path, goal, tasks)

    def run(self) -> None:
        """Execute the Mode 3 autonomous iteration loop."""
        # Bootstrap workspace CLAUDE.md for Claude Code compliance
        self._bootstrap_workspace()

        for i in range(self.args.max_iterations):
            state = self.state_mgr.get_state()

            if self.state_mgr.is_complete():
                break

            if not wu_wei_guard(state, "iterate"):
                self.logger.info(
                    "[哲学] \u65e0\u4e3a\u800c\u6cbb: 未检测到进展，停止执行。"
                )
                self.state_mgr.state["status"] = "complete"
                break

            try:
                node = self.graph.get_current_node(state)
            except KeyError as e:
                self.state_mgr.state["status"] = "error"
                self.state_mgr.state.setdefault("errors", []).append(str(e))
                break

            # Check external events at start of execution
            if i == 0:
                external_events = self.event_detector.detect_external_changes(
                    self.state_mgr.state.get("last_updated", "")
                )
                if external_events:
                    for event in external_events:
                        if event["type"] == "prompt_modified":
                            self.event_detector.mark_user_owned(
                                self.state_mgr.state, event["path"]
                            )
                    if self.args.verbose:
                        self.logger.debug(
                            f"[信息] 检测到 {len(external_events)} 个外部变更"
                        )

            # Track visit BEFORE execution so failures count
            self.state_mgr.track_node_visit(node["id"])
            if self.tracking_enabled:
                self.session_tracker.track_event(
                    "node_enter", {"node": node["id"], "iteration": i}
                )
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
                    self.state_mgr.set_current_node(handler)
                else:
                    # Philosophy: should_retreat check
                    if should_retreat(
                        stuck_node, visits, self.max_retries_map.get(stuck_node, 5)
                    ):
                        self.logger.info(
                            "[哲学] \u4e09\u5341\u516d\u8ba1\u8d70\u4e3a\u4e0a:"
                            f" 从节点 '{stuck_node}' 撤退"
                        )
                    self.state_mgr.state["status"] = "stuck"
                    self.state_mgr.state.setdefault("errors", []).append(
                        f"Node '{stuck_node}' exceeded max_retries "
                        f"(visited {visits} times, max {self.max_retries_map.get(stuck_node)})"
                    )
                    # Report stuck to stderr
                    reporter = Reporter()
                    self.logger.error(
                        reporter.report_stuck(
                            self.state_mgr.state,
                            stuck_node,
                            self.state_mgr.state.get("errors", []),
                        )
                    )
                    self.logger.error(
                        format_error(
                            "stuck_node",
                            node=stuck_node,
                            visits=visits,
                            max_retries=self.max_retries_map.get(stuck_node, 5),
                        )
                    )
                    break
                continue

            self.state_mgr.increment_iteration()

            # Dynamic skill routing: update skills per node (skip if --skills was set)
            if not (hasattr(self.args, "skills") and self.args.skills is not None):
                _feedback_recs = self.feedback_store.get_recommendations(
                    node["id"], self.intent_result.goal_type
                )
                _routing_selection = self.phase_router.route(
                    node["id"],
                    self.intent_result,
                    self.complexity,
                    recommendations=_feedback_recs,
                )
                self.state_mgr.state["context"]["skills_loaded"] = (
                    _routing_selection.primary + _routing_selection.auxiliary
                )

            # Philosophy guard: filter out high-failure skills
            _current_skills = self.state_mgr.state["context"]["skills_loaded"]
            _current_skills = shui_guard(
                _current_skills,
                self.feedback_store,
                node["id"],
                self.intent_result.goal_type,
            )
            self.state_mgr.state["context"]["skills_loaded"] = _current_skills

            # Mode 3: Real AI execution via subprocess provider
            if self.retry_lightweight:
                # Build minimal prompt for format-only retry
                transitions = self.graph.get_available_transitions(node["id"])
                valid_conditions = ", ".join(
                    t.get("condition", "") for t in transitions if t.get("condition")
                )
                context_prompt = (
                    "Your previous output was rejected because it is missing "
                    "required format lines.\n"
                    "Please output ONLY these two lines now:\n\n"
                    "STATUS: success\n"
                    f"TRANSITION: <condition>\n\n"
                    f"Current node: {node['id']}\n"
                    f"Valid TRANSITION values: {valid_conditions}\n"
                )
                self.retry_lightweight = False
                self._last_was_lightweight = True
            else:
                # Try incremental context for same-node repeats
                context_prompt = self.assembler.assemble_incremental(
                    state, node, self.graph, self.knowledge
                )
                if not context_prompt:
                    # Full context needed
                    context_prompt = self.assembler.assemble(
                        state, node, self.graph, self.knowledge
                    )
                self._last_was_lightweight = False

            try:
                response = asyncio.run(
                    self.provider.generate(context_prompt, timeout=self.args.timeout)
                )
                ai_output = response.text
                transition_condition = response.transition
            except TimeoutError as e:
                timeout_detail = f"Timeout after {self.args.timeout}s on node {node['id']}"
                # Include partial output context from the provider if available
                error_detail = str(e)
                parts = error_detail.split(" | ", 1)
                if len(parts) > 1:
                    timeout_detail += " | " + parts[1]
                self.state_mgr.state.setdefault("errors", []).append(timeout_detail)
                self.state_mgr.trim_errors()
                self.logger.error(
                    format_error(
                        "timeout",
                        seconds=str(self.args.timeout),
                        node=node["id"],
                    )
                )
                # Invalidate incremental context on failure
                self.assembler.mark_iteration_failure()
                # Stay on same node - do not advance
                continue
            except RuntimeError as e:
                error_msg = str(e)
                self.logger.error(f"[错误] {error_msg}")
                # Preserve original error format for state (exit code only, no stderr)
                code_match = re.search(r"exited with code (\d+)", error_msg)
                exit_code = code_match.group(1) if code_match else "unknown"
                self.state_mgr.state.setdefault("errors", []).append(
                    f"AI command exited with code {exit_code} on node {node['id']}"
                )
                # Track failed iteration
                if self.tracking_enabled:
                    self.session_tracker.track_event(
                        "iteration_complete",
                        {"node": node["id"], "result": "failed", "reason": "ai_error"},
                    )
                # Verbose: report failed iteration
                if self.args.verbose:
                    reporter = Reporter()
                    print(reporter.report_iteration(self.state_mgr.get_state(), node, "failed"))
                # Run feedback loop on failure
                iteration_data = {
                    "node": node["id"],
                    "result": "failed",
                    "errors": [error_msg],
                    "iteration": self.state_mgr.state.get("iteration_count", 0),
                }
                self.feedback_loop.run_cycle(iteration_data)
                self.state_mgr.trim_errors()
                # Invalidate incremental context on failure
                self.assembler.mark_iteration_failure()

                # Run triggers and record feedback
                _run_post_iteration(
                    self.feedback_store,
                    self.trigger_engine,
                    self.state_mgr,
                    node["id"],
                    "failed",
                    self.intent_result.goal_type,
                    self.logger,
                )

                # Apply retry strategy
                if self.args.retry_strategy == "skip":
                    transitions = self.graph.get_available_transitions(node["id"])
                    if transitions:
                        next_node_id = transitions[0]["to"]
                        self.state_mgr.set_current_node(next_node_id)
                    continue
                elif self.args.retry_strategy == "backoff":
                    visit_count = self.state_mgr.state.get("node_visits", {}).get(
                        node["id"], 1
                    )
                    delay = min(2 ** (visit_count - 1), MAX_BACKOFF_DELAY_SECONDS)
                    time.sleep(delay)
                    continue
                else:  # "continue"
                    continue
            except FileNotFoundError:
                self.logger.error(
                    f"Error: AI command not found: '{shlex.split(self.args.ai_command)[0]}'. "
                    f"Please verify the command is installed and in your PATH."
                )
                self.logger.error(
                    format_error(
                        "command_not_found",
                        cmd=shlex.split(self.args.ai_command)[0],
                    )
                )
                self.state_mgr.state["status"] = "error"
                self.state_mgr.state.setdefault("errors", []).append(
                    f"Command not found: {shlex.split(self.args.ai_command)[0]}"
                )
                break

            # Validate output against contract
            contract_result = self.validator.validate_output(ai_output, node["id"])
            if not contract_result.valid:
                for violation in contract_result.violations:
                    self.logger.warning(f"[合约违规] {violation}")
                self.state_mgr.state.setdefault("errors", []).append(
                    f"Contract violations on node {node['id']}: {contract_result.violations}"
                )
                self.state_mgr.trim_errors()
                # Track failed iteration due to contract violation
                if self.tracking_enabled:
                    self.session_tracker.track_event(
                        "iteration_complete",
                        {
                            "node": node["id"],
                            "result": "failed",
                            "reason": "contract_violation",
                        },
                    )
                # Check if violations are about missing format lines
                has_format_violation = any(
                    "Missing required TRANSITION" in v or "Missing required STATUS" in v
                    for v in contract_result.violations
                )
                if has_format_violation and not self._last_was_lightweight:
                    self.retry_lightweight = True
                # Invalidate incremental context on failure
                self.assembler.mark_iteration_failure()
                # Stay on same node - do not advance
                continue

            # Validate workspace boundary for files_written
            workspace_path = self.state_mgr.state.get("workspace_path", "")
            if workspace_path and contract_result.files_written:
                ws_violations = _validate_workspace_paths(
                    contract_result.files_written, workspace_path
                )
                for v in ws_violations:
                    self.logger.warning(f"[警告] 工作区边界: {v}")
                # Security policy check on written files
                security_policy = SecurityPolicy(workspace_path)
                for fpath in contract_result.files_written:
                    if security_policy.check_path(fpath) == "deny":
                        self.logger.warning(f"[安全] 拒绝文件写入: {fpath}")

            # Determine next node
            transitions = self.graph.get_available_transitions(node["id"])
            if transitions:
                next_node_id, had_warning = resolve_transition(
                    transitions, transition_condition, self.complexity, self.logger
                )
                if had_warning and not transition_condition:
                    self.logger.warning(
                        f"[警告] AI输出中未找到 TRANSITION 行，"
                        f"回退到第一个转换: {next_node_id}"
                    )
                    self.state_mgr.state.setdefault("errors", []).append(
                        f"No TRANSITION line in AI output on node {node['id']}, "
                        f"fell back to: {next_node_id}"
                    )
                self.state_mgr.set_current_node(next_node_id)

                # Mark iteration success for incremental context
                self.assembler.mark_iteration_success(node["id"])

                # Track successful iteration transition
                if self.tracking_enabled:
                    self.session_tracker.track_event(
                        "iteration_complete",
                        {"node": node["id"], "next_node": next_node_id},
                    )

                # Verbose: report successful iteration
                if self.args.verbose:
                    reporter = Reporter()
                    print(
                        reporter.report_iteration(self.state_mgr.get_state(), node, "success")
                    )

                # Run feedback loop on successful iteration
                iteration_data = {
                    "node": node["id"],
                    "result": "success",
                    "errors": [],
                    "iteration": self.state_mgr.state.get("iteration_count", 0),
                }
                self.feedback_loop.run_cycle(iteration_data)

                # Run triggers and record feedback
                _run_post_iteration(
                    self.feedback_store,
                    self.trigger_engine,
                    self.state_mgr,
                    node["id"],
                    "success",
                    self.intent_result.goal_type,
                    self.logger,
                )

                # Populate progress_history for stall detection
                update_progress_history(self.state_mgr.state, self.memory_dir)

                # Philosophy guard: force complexity downgrade if stalling
                tasks_done_for_guard = (
                    self.state_mgr.state.get("progress_history", [0])[-1]
                    if self.state_mgr.state.get("progress_history")
                    else 0
                )
                speed_signal = bing_gui_shen_su(
                    self.state_mgr.state.get("iteration_count", 0), tasks_done_for_guard
                )
                if speed_signal == "low" and self.complexity != "low":
                    self.complexity = "low"
                    self.state_mgr.state["complexity"] = "low"
                    self.logger.info(
                        "[哲学] \u5175\u8d35\u795e\u901f:"
                        " 检测到停滞，降低复杂度。"
                    )

                # Philosophy check: should_stop_iterating
                if check_should_stop(self.memory_dir, self.state_mgr.state):
                    self.logger.info(
                        "[哲学] \u77e5\u6b62\u4e0d\u6b86:"
                        " 检测到收益递减，停止执行。"
                    )
                    self.state_mgr.state["status"] = "complete"
                    break
            else:
                self.state_mgr.state["status"] = "complete"
                break
            self.state_mgr.trim_errors()
