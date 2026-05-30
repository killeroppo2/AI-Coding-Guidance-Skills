"""Main execution loop for the kernel runner.

This module contains the core orchestration logic extracted from runner.py.
It handles Mode 1 (dry-run/scaffolding), Mode 2 (AI reads BOOT.md), and
Mode 3 (real AI execution via subprocess).
"""

import atexit
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

import kernel.mode3_executor as _mode3_mod
from kernel.adapters.ralph_adapter import RalphAdapter
from kernel.bootstrap import BootstrapGenerator
from kernel.capability_assessment import CapabilityAssessor
from kernel.cli import parse_args
from kernel.complexity_assessor import assess_complexity
from kernel.context_assembler import ContextAssembler
from kernel.context_budget import ContextBudgetTracker
from kernel.contracts import OutputContractValidator
from kernel.error_messages import format_error
from kernel.event_detector import EventDetector
from kernel.evolution.engine import EvolutionEngine
from kernel.evolution.metrics import EvolutionMetrics
from kernel.execution.protocol import (
    check_should_stop,
    resolve_transition,
    update_progress_history,
)
from kernel.feedback_loop import FeedbackLoop
from kernel.graph_executor import GraphExecutor
from kernel.intent_analyzer import IntentAnalyzer
from kernel.lifecycle_guard import LifecycleGuard
from kernel.logging_config import setup_logging
from kernel.mode3_executor import _parse_transition
from kernel.phase_router import PhaseRouter
from kernel.philosophy.guards import bing_gui_shen_su, shui_guard, wu_wei_guard
from kernel.philosophy.principles import should_retreat
from kernel.reflector import Reflector
from kernel.reporter import Reporter
from kernel.security_policy import SecurityPolicy
from kernel.skill_feedback import SkillFeedbackStore
from kernel.skill_selector import select_skills_for_goal
from kernel.skill_triggers import SkillTriggerEngine
from kernel.task_manager import TaskManager
from kernel.validators import _sanitize_project_name, _validate_workspace_paths
from knowledge.store import KnowledgeStore
from memory.state_manager import StateManager

KERNEL_ROOT = Path(__file__).resolve().parent.parent

# Maximum delay in seconds for exponential backoff retry strategy
MAX_BACKOFF_DELAY_SECONDS = 60

# Maximum number of progress history entries to retain
MAX_PROGRESS_HISTORY_ENTRIES = 20

# Number of recent reflections to check for stop-iterating philosophy
RECENT_REFLECTIONS_WINDOW = 10

# Timeout in seconds for graceful subprocess termination before kill
SUBPROCESS_TERMINATE_TIMEOUT = 5

# Maximum characters to capture from partial output in timeout messages
PARTIAL_OUTPUT_PREVIEW_LENGTH = 200


def _run_post_iteration(
    feedback_store: SkillFeedbackStore,
    trigger_engine: SkillTriggerEngine,
    state_mgr: "StateManager",
    node_id: str,
    outcome: str,
    goal_type: str,
    logger,
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
                    f"[TRIGGER] {_trig.trigger_name}: "
                    f"activating {_trig.skill} for {_trig.target_node}"
                )
        state_mgr.state["context"]["skills_loaded"] = _current_skills

    # Record skill feedback AFTER triggers (captures triggered skills)
    feedback_store.record(
        node_id=node_id,
        skills_used=state_mgr.state.get("context", {}).get("skills_loaded", []),
        outcome=outcome,
        goal_type=goal_type,
    )


def main(argv: list[str] | None = None, kernel_root: Path | None = None) -> dict[str, Any]:
    """Main entry point for the kernel runner.

    Args:
        argv: Optional argument list for testing (defaults to sys.argv[1:]).
        kernel_root: Optional project root path. If provided, overrides the
            module-level KERNEL_ROOT.

    Returns:
        The final state dict after execution completes.
    """
    global KERNEL_ROOT
    if kernel_root is not None:
        KERNEL_ROOT = kernel_root
    args = parse_args(argv)

    # Configure logging early
    logger = setup_logging(verbose=args.verbose)

    # Handle --check: run setup checks and exit early
    if args.check:
        from setup_check import SetupChecker

        checker = SetupChecker(str(KERNEL_ROOT))
        results = checker.run_all_checks()
        exit_code = checker.print_results(results)
        sys.exit(exit_code)

    # Handle --init: create runtime files and exit early
    if args.init:
        from kernel.init import init_runtime_files

        init_runtime_files(KERNEL_ROOT)
        from kernel.migrations import run_pending_migrations

        applied = run_pending_migrations(KERNEL_ROOT)
        if applied:
            print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
        sys.exit(0)

    # Handle --migrate: run pending migrations and exit early
    if args.migrate:
        from kernel.migrations import run_pending_migrations

        applied = run_pending_migrations(KERNEL_ROOT)
        if applied:
            print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
        else:
            print("No pending migrations.")
        sys.exit(0)

    # Handle --status: print current status and exit early
    if args.status:
        reporter = Reporter()
        state_path = str(KERNEL_ROOT / "kernel" / "state.yaml")
        memory_dir = str(KERNEL_ROOT / "memory")
        state_mgr = StateManager(state_path, memory_dir)
        tasks_path = Path(memory_dir) / "tasks.yaml"
        if tasks_path.exists():
            tm = TaskManager(memory_dir)
            tasks_list = tm.load_tasks()
        else:
            tasks_list = []
        print(reporter.format_status(state_mgr.get_state(), tasks_list))
        return state_mgr.get_state()

    # Handle --session-stats: print session statistics and exit early
    if args.session_stats:
        from kernel.session_tracker import SessionTracker

        memory_dir = str(KERNEL_ROOT / "memory")
        state_path = str(KERNEL_ROOT / "kernel" / "state.yaml")
        state_mgr = StateManager(state_path, memory_dir)
        tracker = SessionTracker(memory_dir)
        event_count = tracker.get_event_count()
        snapshot = tracker.build_resume_snapshot()
        print("=== Session Statistics ===")
        print(f"Events: {event_count}")
        print(f"Status: {snapshot.get('status', 'unknown')}")
        if event_count == 0:
            print("Last node: none")
            print("Recent path: no events")
            print("No session events recorded")
        else:
            print(f"Last node: {snapshot.get('last_node') or 'none'}")
            if snapshot.get("node_path"):
                print(f"Recent path: {' -> '.join(snapshot['node_path'])}")
            else:
                print("Recent path: no events")
            if snapshot.get("recent_errors"):
                print(f"Recent errors: {len(snapshot['recent_errors'])}")
        return state_mgr.get_state()

    # Validate that --goal is required unless --check or --status is used
    if not args.goal:
        print(
            "error: the following arguments are required: --goal\n"
            'usage: runner --goal "<your development goal>" [--dry-run] [--max-iterations N]\n'
            "       runner --init | --check | --status",
            file=sys.stderr,
        )
        sys.exit(2)

    # Validate --max-iterations is positive
    if args.max_iterations < 1:
        print(
            f"error: --max-iterations must be a positive integer, got {args.max_iterations}",
            file=sys.stderr,
        )
        sys.exit(2)

    state_path = str(KERNEL_ROOT / "kernel" / "state.yaml")
    memory_dir = str(KERNEL_ROOT / "memory")
    graph_path = str(KERNEL_ROOT / "kernel" / "graph.yaml")
    knowledge_dir = str(KERNEL_ROOT / "knowledge")

    state_mgr = StateManager(state_path, memory_dir)
    graph = GraphExecutor(graph_path)
    knowledge = KnowledgeStore(knowledge_dir)

    # Auto-reset when a new goal is provided and previous run completed/failed
    if args.goal and not args.resume:
        stored_goal = state_mgr.state.get("goal", "")
        stored_status = state_mgr.state.get("status", "idle")
        if stored_status in ("complete", "stuck", "error") or (
            stored_goal and stored_goal != args.goal
        ):
            if args.dry_run:
                # Reset in-memory only for dry-run
                state_mgr.state["current_node"] = "init"
                state_mgr.state["iteration_count"] = 0
                state_mgr.state["status"] = "idle"
                state_mgr.state["errors"] = []
                state_mgr.state["node_visits"] = {}
                state_mgr.state["progress_history"] = []
            else:
                state_mgr.reset()
                # Clean up stale memory files
                for cleanup_file in ["tasks.yaml", "progress.yaml", "assessment.yaml"]:
                    cleanup_path = Path(memory_dir) / cleanup_file
                    if cleanup_path.exists():
                        cleanup_path.unlink()

    if args.goal:
        if args.resume and state_mgr.state.get("goal"):
            # When resuming, do not overwrite existing goal
            pass
        elif args.dry_run:
            state_mgr.state["goal"] = args.goal
        else:
            state_mgr.set_goal(args.goal)

    # Initialize workspace
    if args.workspace:
        project_name = args.workspace
    else:
        goal = state_mgr.state.get("goal", "")
        project_name = _sanitize_project_name(goal) if goal else ""
    if project_name and not args.dry_run:
        state_mgr.set_workspace(project_name)
        # Generate CLAUDE.md for workspace
        from kernel.workspace_bootstrap import generate_claude_md

        workspace_path = state_mgr.state.get("workspace_path", "")
        if workspace_path:
            tasks_file = Path(memory_dir) / "tasks.yaml"
            bootstrap_tasks = None
            if tasks_file.exists():
                bootstrap_tm = TaskManager(memory_dir)
                bootstrap_tasks = bootstrap_tm.load_tasks()
            generate_claude_md(
                workspace_path, state_mgr.state.get("goal", ""), tasks=bootstrap_tasks
            )
    elif project_name and args.dry_run:
        state_mgr.state["workspace_path"] = f"./workspace/{project_name}/"

    # Reset node_visits on resume so stale counts don't trigger false stuck detection
    if args.resume:
        state_mgr.state["node_visits"] = {}
        # If previous run was interrupted, reset status to running so execution continues
        if state_mgr.state.get("status") == "interrupted":
            state_mgr.state["status"] = "running"

    # Resume snapshot: build session context for context assembler
    if args.resume and not args.dry_run:
        from kernel.session_tracker import SessionTracker as _ResumeTracker

        _resume_tracker = _ResumeTracker(memory_dir)
        snapshot = _resume_tracker.build_resume_snapshot()
        state_mgr.state.setdefault("context", {})["resume_snapshot"] = snapshot

    # Skill auto-selection
    if hasattr(args, "skills") and args.skills is not None:
        # Manual override: use provided skill list
        selected_skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    else:
        # Auto-select skills based on goal
        available_skills = knowledge.list_skills()
        goal_text = state_mgr.state.get("goal", "")
        selected_skills = select_skills_for_goal(goal_text, available_skills)
    state_mgr.state.setdefault("context", {})["skills_loaded"] = selected_skills

    # Intent analysis and PhaseRouter setup for dynamic per-node skill selection
    intent_analyzer = IntentAnalyzer()
    goal_text_for_intent = state_mgr.state.get("goal", "")
    intent_result = intent_analyzer.analyze(goal_text_for_intent)
    state_mgr.state.setdefault("context", {})["intent_result"] = asdict(intent_result)

    # Load skills index and workflow for PhaseRouter
    skills_index_path = KERNEL_ROOT / "skills" / "_index.yaml"
    if skills_index_path.exists():
        with open(skills_index_path, "r", encoding="utf-8") as _idx_f:
            _skills_index_data = yaml.safe_load(_idx_f) or {}
    else:
        _skills_index_data = {}
    _skills_index_for_router = {
        "core_items": _skills_index_data.get("core_items", []),
        "community_items": _skills_index_data.get("community_items", []),
    }
    _workflow_for_router = _skills_index_data.get("core_workflow", {})
    phase_router = PhaseRouter(_skills_index_for_router, _workflow_for_router)

    # Capability assessment
    if not args.dry_run and args.goal:
        assessment_path = Path(memory_dir) / "assessment.yaml"
        # Skip assessment on resume if assessment.yaml already exists
        if args.resume and assessment_path.exists():
            pass
        else:
            assessor = CapabilityAssessor()
            available_skills = knowledge.list_skills()
            assessment = assessor.assess_capabilities(args.goal, available_skills)
            confidence = assessment.get("confidence", 0.0)
            gaps = assessment.get("gaps", [])

            if confidence < 0.3 and gaps:
                logger.warning(
                    f"[WARNING] Low skill coverage ({confidence:.0%}). "
                    f"The kernel lacks skills for: {', '.join(gaps[:5])}. "
                    f"Consider creating skills with 'write-a-skill'."
                )
            elif confidence < 0.7 and gaps:
                logger.info(
                    f"[NOTE] Partial skill coverage ({confidence:.0%}). "
                    f"Some areas may need new skills: {', '.join(gaps[:5])}"
                )

            assessor.write_assessment(assessment, args.goal, memory_dir)

    state_mgr.state["max_iterations"] = args.max_iterations
    state_mgr.state["status"] = "running"

    # Set execution mode
    state_mgr.set_execution_mode(args.execution_mode)

    # Complexity assessment and routing
    if args.complexity == "auto":
        complexity = assess_complexity(state_mgr.state.get("goal", ""))
    else:
        complexity = args.complexity
    state_mgr.state["complexity"] = complexity

    # Low complexity: skip init/plan, jump straight to code
    if complexity == "low" and not args.dry_run and not args.generate_prompt:
        tasks_file = Path(memory_dir) / "tasks.yaml"
        if not tasks_file.exists() or not yaml.safe_load(tasks_file.read_text(encoding="utf-8")):
            task_data = {
                "tasks": [
                    {
                        "id": "T-001",
                        "title": state_mgr.state.get("goal", ""),
                        "status": "pending",
                        "description": state_mgr.state.get("goal", ""),
                        "complexity": "low",
                    }
                ]
            }
            with open(tasks_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(task_data, f)
        state_mgr.state["current_node"] = "code"

    # Handle --generate-prompt: assemble and print context, then exit
    if args.generate_prompt:
        gen = BootstrapGenerator(KERNEL_ROOT)
        prompt = gen.generate(state_path, graph_path, knowledge_dir)
        print(prompt)
        return state_mgr.get_state()

    # Determine execution mode
    mode3 = args.ai_command is not None and not args.dry_run

    _tracking_enabled = False  # Default: no tracking outside Mode 3

    # Register signal and atexit handlers for graceful shutdown in Mode 3
    if mode3:

        def _shutdown_handler(signum, frame):
            if _mode3_mod._active_subprocess is not None:
                try:
                    _mode3_mod._active_subprocess.terminate()
                    _mode3_mod._active_subprocess.wait(timeout=SUBPROCESS_TERMINATE_TIMEOUT)
                except Exception:
                    try:
                        _mode3_mod._active_subprocess.kill()
                    except Exception:
                        pass
            state_mgr.state["status"] = "interrupted"
            state_mgr.state.setdefault("errors", []).append("Execution interrupted by signal")
            state_mgr.save_state()
            sys.exit(130)

        signal.signal(signal.SIGINT, _shutdown_handler)
        signal.signal(signal.SIGTERM, _shutdown_handler)

        def _atexit_save():
            if state_mgr.state.get("status") == "running":
                state_mgr.state["status"] = "interrupted"
                state_mgr.save_state()

        atexit.register(_atexit_save)

        # Lifecycle guard: detect orphan process and trigger graceful shutdown
        def _orphan_shutdown():
            state_mgr.state["status"] = "interrupted"
            state_mgr.state.setdefault("errors", []).append("Parent process died - orphan detected")
            state_mgr.save_state()
            sys.exit(1)

        lifecycle_guard = LifecycleGuard(on_shutdown=_orphan_shutdown)
        lifecycle_guard.start()

    if args.dry_run:
        print(f"[预演] 目标: {args.goal}")
        print(f"[预演] 最大迭代次数: {args.max_iterations}")
        print(f"[预演] 起始节点: {state_mgr.state.get('current_node', 'init')}")
        print()

    if mode3:
        budget_tracker = ContextBudgetTracker() if not args.dry_run else None
        assembler = ContextAssembler(KERNEL_ROOT, budget_tracker=budget_tracker)
        validator = OutputContractValidator(str(KERNEL_ROOT / "kernel" / "graph.yaml"))
        reflector = Reflector(memory_dir, knowledge)
        evolution_engine = EvolutionEngine(str(KERNEL_ROOT / "kernel"), graph)
        evolution_metrics = EvolutionMetrics()
        feedback_loop = FeedbackLoop(memory_dir, reflector, evolution_engine, evolution_metrics)
        event_detector = EventDetector(KERNEL_ROOT)
        trigger_engine = SkillTriggerEngine()
        feedback_store = SkillFeedbackStore(memory_dir)
        retry_lightweight = False
        _last_was_lightweight = False

        from kernel.session_tracker import SessionTracker

        session_tracker = SessionTracker(memory_dir)

        # Performance guard: skip event tracking in dry-run or high LOG_LEVEL
        _tracking_enabled = not args.dry_run and os.environ.get(
            "LOG_LEVEL", ""
        ).upper() not in ("ERROR", "CRITICAL")

        if _tracking_enabled:
            session_tracker.track_event("session_start", {"goal": args.goal, "mode": "mode3"})

    # Build max_retries_map from graph nodes
    max_retries_map = {
        node["id"]: node.get("max_retries", 10) for node in graph.graph.get("nodes", [])
    }

    # Dry-run cycle detection
    _dry_run_visited: set[str] = set()

    # Chinese startup banner for mode3
    if mode3:
        _startup_workspace = state_mgr.state.get("workspace_path", "")
        _startup_goal = state_mgr.state.get("goal", "")
        print(
            f"\U0001f680 AI \u5f00\u53d1\u5185\u6838\u542f\u52a8\n"
            f"   \u76ee\u6807: {_startup_goal}\n"
            f"   \u5de5\u4f5c\u533a: {_startup_workspace}"
        )

    for i in range(args.max_iterations):
        state = state_mgr.get_state()

        if state_mgr.is_complete():
            break

        if mode3:
            if not wu_wei_guard(state, "iterate"):
                logger.info(
                    "[PHILOSOPHY] \u65e0\u4e3a\u800c\u6cbb: No progress detected, stopping."
                )
                state_mgr.state["status"] = "complete"
                break

        try:
            node = graph.get_current_node(state)
        except KeyError as e:
            state_mgr.state["status"] = "error"
            state_mgr.state.setdefault("errors", []).append(str(e))
            break

        if args.dry_run:
            if node["id"] in _dry_run_visited:
                print("\n[预演] 已遍历所有节点。实际执行时根据AI输出决定流转。")
                state_mgr.state["status"] = "complete"
                break
            _dry_run_visited.add(node["id"])
            print(f"  {node['id']} - {node.get('description', '')}")

        if mode3:
            # Check external events at start of execution
            if i == 0:
                external_events = event_detector.detect_external_changes(
                    state_mgr.state.get("last_updated", "")
                )
                if external_events:
                    for event in external_events:
                        if event["type"] == "prompt_modified":
                            event_detector.mark_user_owned(state_mgr.state, event["path"])
                    if args.verbose:
                        logger.debug(f"[INFO] Detected {len(external_events)} external change(s)")

            # Mode 3: Track visit BEFORE execution so failures count
            state_mgr.track_node_visit(node["id"])
            if _tracking_enabled:
                session_tracker.track_event("node_enter", {"node": node["id"], "iteration": i})
            is_stuck, stuck_node, visits = state_mgr.check_stuck(max_retries_map)
            if is_stuck:
                assert stuck_node is not None  # guaranteed when is_stuck=True
                # Check for stuck_handler
                try:
                    stuck_node_def = graph.get_node(stuck_node)
                    handler = stuck_node_def.get("stuck_handler")
                except KeyError:
                    handler = None
                if handler:
                    state_mgr.set_current_node(handler)
                else:
                    # Philosophy: should_retreat check
                    if should_retreat(stuck_node, visits, max_retries_map.get(stuck_node, 5)):
                        logger.info(
                            "[PHILOSOPHY] \u4e09\u5341\u516d\u8ba1\u8d70\u4e3a\u4e0a:"
                            f" Retreating from node '{stuck_node}'"
                        )
                    state_mgr.state["status"] = "stuck"
                    state_mgr.state.setdefault("errors", []).append(
                        f"Node '{stuck_node}' exceeded max_retries "
                        f"(visited {visits} times, max {max_retries_map.get(stuck_node)})"
                    )
                    # Report stuck to stderr
                    reporter = Reporter()
                    logger.error(
                        reporter.report_stuck(
                            state_mgr.state, stuck_node, state_mgr.state.get("errors", [])
                        )
                    )
                    logger.error(
                        format_error(
                            "stuck_node",
                            node=stuck_node,
                            visits=visits,
                            max_retries=max_retries_map.get(stuck_node, 5),
                        )
                    )
                    break
                continue

        state_mgr.increment_iteration()

        if mode3:
            # Dynamic skill routing: update skills per node (skip if --skills was set)
            if not (hasattr(args, "skills") and args.skills is not None):
                _feedback_recs = feedback_store.get_recommendations(
                    node["id"], intent_result.goal_type
                )
                _routing_selection = phase_router.route(
                    node["id"], intent_result, complexity,
                    recommendations=_feedback_recs,
                )
                state_mgr.state["context"]["skills_loaded"] = (
                    _routing_selection.primary + _routing_selection.auxiliary
                )

            # Philosophy guard: filter out high-failure skills
            _current_skills = state_mgr.state["context"]["skills_loaded"]
            _current_skills = shui_guard(
                _current_skills, feedback_store, node["id"], intent_result.goal_type
            )
            state_mgr.state["context"]["skills_loaded"] = _current_skills

            # Mode 3: Real AI execution via subprocess
            if retry_lightweight:
                # Build minimal prompt for format-only retry
                transitions = graph.get_available_transitions(node["id"])
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
                retry_lightweight = False
                _last_was_lightweight = True
            else:
                # Try incremental context for same-node repeats
                context_prompt = assembler.assemble_incremental(state, node, graph, knowledge)
                if not context_prompt:
                    # Full context needed
                    context_prompt = assembler.assemble(state, node, graph, knowledge)
                _last_was_lightweight = False
            try:
                proc = subprocess.Popen(
                    shlex.split(args.ai_command),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                _mode3_mod._active_subprocess = proc
                try:
                    stdout, stderr = proc.communicate(input=context_prompt, timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                    timeout_detail = f"Timeout after {args.timeout}s on node {node['id']}"
                    if stdout:
                        preview = stdout[:PARTIAL_OUTPUT_PREVIEW_LENGTH]
                        timeout_detail += f" | partial stdout: {preview}"
                    if stderr:
                        preview = stderr[:PARTIAL_OUTPUT_PREVIEW_LENGTH]
                        timeout_detail += f" | stderr: {preview}"
                    state_mgr.state.setdefault("errors", []).append(timeout_detail)
                    state_mgr.trim_errors()
                    logger.error(
                        format_error(
                            "timeout",
                            seconds=str(args.timeout),
                            node=node["id"],
                        )
                    )
                    # Invalidate incremental context on failure
                    assembler.mark_iteration_failure()
                    # Stay on same node - do not advance
                    continue
                finally:
                    _mode3_mod._active_subprocess = None
                result_returncode = proc.returncode
                result_stdout = stdout
                result_stderr = stderr
                if result_returncode != 0:
                    logger.error(
                        f"[ERROR] AI command exited with code {result_returncode}: "
                        f"{result_stderr.strip()}"
                    )
                    state_mgr.state.setdefault("errors", []).append(
                        f"AI command exited with code {result_returncode} on node {node['id']}"
                    )
                    # Track failed iteration
                    if _tracking_enabled:
                        session_tracker.track_event(
                            "iteration_complete",
                            {"node": node["id"], "result": "failed", "reason": "ai_error"},
                        )
                    # Verbose: report failed iteration
                    if args.verbose:
                        reporter = Reporter()
                        print(reporter.report_iteration(state_mgr.get_state(), node, "failed"))
                    # Run feedback loop on failure
                    iteration_data = {
                        "node": node["id"],
                        "result": "failed",
                        "errors": [f"AI command exited with code {result_returncode}"],
                        "iteration": state_mgr.state.get("iteration_count", 0),
                    }
                    feedback_loop.run_cycle(iteration_data)
                    state_mgr.trim_errors()
                    # Invalidate incremental context on failure
                    assembler.mark_iteration_failure()

                    # Run triggers and record feedback (以战养战)
                    _run_post_iteration(
                        feedback_store, trigger_engine, state_mgr,
                        node["id"], "failed",
                        intent_result.goal_type, logger,
                    )

                    # Apply retry strategy
                    if args.retry_strategy == "skip":
                        transitions = graph.get_available_transitions(node["id"])
                        if transitions:
                            next_node_id = transitions[0]["to"]
                            state_mgr.set_current_node(next_node_id)
                        continue
                    elif args.retry_strategy == "backoff":
                        visit_count = state_mgr.state.get("node_visits", {}).get(node["id"], 1)
                        delay = min(2 ** (visit_count - 1), MAX_BACKOFF_DELAY_SECONDS)
                        time.sleep(delay)
                        continue
                    else:  # "continue"
                        continue
                ai_output = result_stdout
                transition_condition = _parse_transition(ai_output)
            except FileNotFoundError:
                logger.error(
                    f"Error: AI command not found: '{shlex.split(args.ai_command)[0]}'. "
                    f"Please verify the command is installed and in your PATH."
                )
                logger.error(
                    format_error(
                        "command_not_found",
                        cmd=shlex.split(args.ai_command)[0],
                    )
                )
                state_mgr.state["status"] = "error"
                state_mgr.state.setdefault("errors", []).append(
                    f"Command not found: {shlex.split(args.ai_command)[0]}"
                )
                break

            # Validate output against contract
            contract_result = validator.validate_output(ai_output, node["id"])
            if not contract_result.valid:
                for violation in contract_result.violations:
                    logger.warning(f"[CONTRACT VIOLATION] {violation}")
                state_mgr.state.setdefault("errors", []).append(
                    f"Contract violations on node {node['id']}: {contract_result.violations}"
                )
                state_mgr.trim_errors()
                # Track failed iteration due to contract violation
                if _tracking_enabled:
                    session_tracker.track_event(
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
                if has_format_violation and not _last_was_lightweight:
                    retry_lightweight = True
                # Invalidate incremental context on failure
                assembler.mark_iteration_failure()
                # Stay on same node - do not advance
                continue

            # Validate workspace boundary for files_written
            workspace_path = state_mgr.state.get("workspace_path", "")
            if workspace_path and contract_result.files_written:
                ws_violations = _validate_workspace_paths(
                    contract_result.files_written, workspace_path
                )
                for v in ws_violations:
                    logger.warning(f"[WARNING] Workspace boundary: {v}")
                # Security policy check on written files
                security_policy = SecurityPolicy(workspace_path)
                for fpath in contract_result.files_written:
                    if security_policy.check_path(fpath) == "deny":
                        logger.warning(f"[SECURITY] Denied file write: {fpath}")

            # Determine next node
            transitions = graph.get_available_transitions(node["id"])
            if transitions:
                next_node_id, had_warning = resolve_transition(
                    transitions, transition_condition, complexity, logger
                )
                if had_warning and not transition_condition:
                    logger.warning(
                        f"[WARNING] No TRANSITION line found in AI output, "
                        f"falling back to first transition: {next_node_id}"
                    )
                    state_mgr.state.setdefault("errors", []).append(
                        f"No TRANSITION line in AI output on node {node['id']}, "
                        f"fell back to: {next_node_id}"
                    )
                state_mgr.set_current_node(next_node_id)

                # Mark iteration success for incremental context
                assembler.mark_iteration_success(node["id"])

                # Track successful iteration transition
                if _tracking_enabled:
                    session_tracker.track_event(
                        "iteration_complete", {"node": node["id"], "next_node": next_node_id}
                    )

                # Verbose: report successful iteration
                if args.verbose:
                    reporter = Reporter()
                    print(reporter.report_iteration(state_mgr.get_state(), node, "success"))

                # Run feedback loop on successful iteration
                iteration_data = {
                    "node": node["id"],
                    "result": "success",
                    "errors": [],
                    "iteration": state_mgr.state.get("iteration_count", 0),
                }
                feedback_loop.run_cycle(iteration_data)

                # Run triggers and record feedback (以战养战 + 道常无为而无不为)
                _run_post_iteration(
                    feedback_store, trigger_engine, state_mgr,
                    node["id"], "success",
                    intent_result.goal_type, logger,
                )

                # Populate progress_history for stall detection
                update_progress_history(state_mgr.state, memory_dir)

                # Philosophy guard: force complexity downgrade if stalling
                tasks_done_for_guard = (
                    state_mgr.state.get("progress_history", [0])[-1]
                    if state_mgr.state.get("progress_history")
                    else 0
                )
                speed_signal = bing_gui_shen_su(
                    state_mgr.state.get("iteration_count", 0), tasks_done_for_guard
                )
                if speed_signal == "low" and complexity != "low":
                    complexity = "low"
                    state_mgr.state["complexity"] = "low"
                    logger.info(
                        "[PHILOSOPHY] \u5175\u8d35\u795e\u901f:"
                        " Stalling detected, downgrading complexity."
                    )

                # Philosophy check: should_stop_iterating
                if check_should_stop(memory_dir, state_mgr.state):
                    logger.info(
                        "[PHILOSOPHY] \u77e5\u6b62\u4e0d\u6b86:"
                        " Diminishing returns detected, stopping."
                    )
                    state_mgr.state["status"] = "complete"
                    break
            else:
                state_mgr.state["status"] = "complete"
                break
            state_mgr.trim_errors()
        else:
            # SCAFFOLDING: In this mode (Mode 1), the runner always picks the first
            # available transition without evaluating conditions. This is intentional:
            # the runner does not call an LLM and cannot evaluate conditions like
            # "tests_pass" or "plan_ready". For actual condition evaluation, an AI
            # agent should read BOOT.md directly (Mode 2) and decide transitions itself.

            # Track visit BEFORE advancing so stuck detection works on failed loops
            state_mgr.track_node_visit(node["id"])
            is_stuck, stuck_node, visits = state_mgr.check_stuck(max_retries_map)
            if is_stuck:
                assert stuck_node is not None  # guaranteed when is_stuck=True
                # Check for stuck_handler
                try:
                    stuck_node_def = graph.get_node(stuck_node)
                    handler = stuck_node_def.get("stuck_handler")
                except KeyError:
                    handler = None
                if handler:
                    if args.dry_run:
                        print(
                            f"  STUCK: Node '{stuck_node}' exceeded max_retries "
                            f"(visited {visits} times, max {max_retries_map.get(stuck_node)})"
                        )
                        print(f"  Redirecting to stuck_handler: {handler}")
                        print()
                    state_mgr.set_current_node(handler)
                else:
                    if args.dry_run:
                        print(
                            f"  STUCK: Node '{stuck_node}' exceeded max_retries "
                            f"(visited {visits} times, max {max_retries_map.get(stuck_node)})"
                        )
                        print()
                    state_mgr.state["status"] = "stuck"
                    state_mgr.state.setdefault("errors", []).append(
                        f"Node '{stuck_node}' exceeded max_retries "
                        f"(visited {visits} times, max {max_retries_map.get(stuck_node)})"
                    )
                    break
                continue

            transitions = graph.get_available_transitions(node["id"])
            if transitions:
                next_node_id = transitions[0]["to"]

                # Medium complexity: skip reflect/evolve in scaffolding mode
                if complexity == "medium" and next_node_id in ("reflect", "evolve"):
                    next_node_id = "plan"
                state_mgr.set_current_node(next_node_id)

                if args.dry_run:
                    print(f"  → {next_node_id}")
                    print()
            else:
                state_mgr.state["status"] = "complete"
                if args.dry_run:
                    print("  → 结束")
                    print()
                break

    # Mark as complete if we finished the loop
    if state_mgr.state.get("status") == "running":
        state_mgr.state["status"] = "complete"

    # Stop lifecycle guard if running
    if mode3:
        lifecycle_guard.stop()

    # Track session_end event
    if mode3 and _tracking_enabled:
        session_tracker.track_event(
            "session_end",
            {
                "status": state_mgr.state.get("status"),
                "iterations": state_mgr.state.get("iteration_count", 0),
            },
        )

    # Print completion report after Mode 3 execution
    if mode3:
        tasks_path_file = Path(memory_dir) / "tasks.yaml"
        if tasks_path_file.exists():
            tm = TaskManager(memory_dir)
            tasks_list = tm.load_tasks()
        else:
            tasks_list = []

        _final_status = state_mgr.state.get("status", "unknown")
        _final_workspace = state_mgr.state.get("workspace_path", "")
        _final_iterations = state_mgr.state.get("iteration_count", 0)
        _total_tasks = len(tasks_list)
        _done_tasks = sum(1 for t in tasks_list if t.get("status") == "done")

        if _final_status == "complete":
            print(
                f"\u2705 \u5b8c\u6210\uff01\n"
                f"   \u4efb\u52a1: {_done_tasks}/{_total_tasks}\n"
                f"   \u6587\u4ef6: {_final_workspace}\n"
                f"   \u8017\u65f6: {_final_iterations} \u6b21\u8fed\u4ee3"
            )
        else:
            _last_error = ""
            _errors = state_mgr.state.get("errors", [])
            if _errors:
                _last_error = _errors[-1]
            print(
                f"\u274c \u672a\u5b8c\u6210\n"
                f"   \u95ee\u9898: {_last_error}\n"
                f"   \u5efa\u8bae: "
                f"\u5c1d\u8bd5\u7b80\u5316\u76ee\u6807\u6216\u67e5\u770b"
                f" --verbose \u8f93\u51fa"
            )

        if budget_tracker is not None:
            budget_report = budget_tracker.get_efficiency_report()
            if "No context assemblies" not in budget_report:
                print(budget_report)

    # Export to prd.json if execution mode is ralph
    if state_mgr.get_execution_mode() == "ralph" and not args.dry_run:
        adapter = RalphAdapter()
        tasks_path = state_mgr.get_tasks_path()
        if tasks_path.exists():
            with open(tasks_path, "r", encoding="utf-8") as f:
                tasks_data = yaml.safe_load(f) or {}
            tasks = tasks_data.get("tasks", [])
        else:
            tasks = []
        goal = state_mgr.state.get("goal", "")
        prd = adapter.export_to_prd_json(tasks, goal)
        prd_path = Path(memory_dir) / "prd.json"
        with open(prd_path, "w", encoding="utf-8") as f:
            json.dump(prd, f, indent=2)

    if not args.dry_run:
        state_mgr.save_state()

    if args.dry_run:
        print(f"[预演] 最终状态: {state_mgr.state.get('status')}")
        print(f"[预演] 遍历节点数: {len(_dry_run_visited)}")

    return state_mgr.get_state()
