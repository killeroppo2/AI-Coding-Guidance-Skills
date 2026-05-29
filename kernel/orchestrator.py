"""Main execution loop for the kernel runner.

This module contains the core orchestration logic extracted from runner.py.
It handles Mode 1 (dry-run/scaffolding), Mode 2 (AI reads BOOT.md), and
Mode 3 (real AI execution via subprocess).
"""

import atexit
import json
import os
import signal
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from kernel.adapters.ralph_adapter import RalphAdapter
from kernel.bootstrap import BootstrapGenerator
from kernel.capability_assessment import CapabilityAssessor
from kernel.cli import parse_args
from kernel.complexity_assessor import assess_complexity
from kernel.context_assembler import ContextAssembler
from kernel.context_budget import ContextBudgetTracker
from kernel.contracts import OutputContractValidator
from kernel.event_detector import EventDetector
from kernel.evolution.engine import EvolutionEngine
from kernel.evolution.metrics import EvolutionMetrics
from kernel.execution.autonomous import AutonomousExecutor
from kernel.execution.dry_run import DryRunExecutor
from kernel.execution.protocol import (
    MAX_PROGRESS_HISTORY_ENTRIES as MAX_PROGRESS_HISTORY_ENTRIES,
)
from kernel.feedback_loop import FeedbackLoop
from kernel.graph_executor import GraphExecutor
from kernel.intent_analyzer import IntentAnalyzer
from kernel.lifecycle_guard import LifecycleGuard
from kernel.logging_config import setup_logging
from kernel.phase_router import PhaseRouter
from kernel.providers.subprocess_provider import SubprocessProvider
from kernel.reporter import Reporter
from kernel.skill_feedback import SkillFeedbackStore
from kernel.skill_selector import select_skills_for_goal
from kernel.skill_triggers import SkillTriggerEngine
from kernel.task_manager import TaskManager
from kernel.validators import _sanitize_project_name
from knowledge.store import KnowledgeStore
from memory.state_manager import StateManager

KERNEL_ROOT = Path(__file__).resolve().parent.parent

# Timeout in seconds for graceful subprocess termination before kill
SUBPROCESS_TERMINATE_TIMEOUT = 5


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

    # Auto-reset when a new goal is provided and not resuming
    if args.goal and not args.resume and not args.dry_run:
        stored_goal = state_mgr.state.get("goal", "")
        stored_status = state_mgr.state.get("status", "idle")
        if stored_status in ("complete", "stuck", "error") or (
            stored_goal and stored_goal != args.goal
        ):
            state_mgr.reset()
            # Clean up memory files for fresh start
            for cleanup_file in ["tasks.yaml", "progress.yaml", "assessment.yaml"]:
                cleanup_path = Path(memory_dir) / cleanup_file
                if cleanup_path.exists():
                    cleanup_path.unlink()
            logger.info("[系统] 检测到新目标，已自动重置状态")

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
    elif project_name and args.dry_run:
        state_mgr.state["workspace_path"] = f"./workspace/{project_name}/"

    # Startup banner for Mode 3 / scaffolding (not in dry-run or generate-prompt)
    if not args.dry_run and not args.generate_prompt:
        workspace_display = state_mgr.state.get("workspace_path", "./workspace/")
        print("\n\U0001f680 AI \u5f00\u53d1\u5185\u6838\u542f\u52a8")
        print(f"   \u76ee\u6807: {state_mgr.state.get('goal', '')}")
        print(f"   \u5de5\u4f5c\u533a: {workspace_display}\n")

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
                    f"[警告] 技能覆盖率低 ({confidence:.0%})。"
                    f"内核缺少以下技能: {', '.join(gaps[:5])}。"
                    f"考虑使用 'write-a-skill' 创建技能。"
                )
            elif confidence < 0.7 and gaps:
                logger.info(
                    f"[提示] 部分技能覆盖 ({confidence:.0%})。"
                    f"某些领域可能需要新技能: {', '.join(gaps[:5])}"
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
        provider = SubprocessProvider(command=args.ai_command, timeout=args.timeout)

        def _shutdown_handler(signum, frame):
            if provider._active_subprocess is not None:
                try:
                    provider._active_subprocess.terminate()
                    provider._active_subprocess.wait(timeout=SUBPROCESS_TERMINATE_TIMEOUT)
                except Exception:
                    try:
                        provider._active_subprocess.kill()
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
        print(f"[试运行] 目标: {args.goal}")
        print(f"[试运行] 最大迭代: {args.max_iterations}")
        print(f"[试运行] 起始节点: {state_mgr.state.get('current_node', 'init')}")
        print()

    if mode3:
        budget_tracker = ContextBudgetTracker() if not args.dry_run else None
        assembler = ContextAssembler(KERNEL_ROOT, budget_tracker=budget_tracker)
        validator = OutputContractValidator(str(KERNEL_ROOT / "kernel" / "graph.yaml"))
        from kernel.reflector import Reflector

        reflector = Reflector(memory_dir, knowledge)
        evolution_engine = EvolutionEngine(str(KERNEL_ROOT / "kernel"), graph)
        evolution_metrics = EvolutionMetrics()
        feedback_loop = FeedbackLoop(memory_dir, reflector, evolution_engine, evolution_metrics)
        event_detector = EventDetector(KERNEL_ROOT)
        trigger_engine = SkillTriggerEngine()
        feedback_store = SkillFeedbackStore(memory_dir)

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

    # Delegate to appropriate executor
    if mode3:
        executor = AutonomousExecutor(
            state_mgr=state_mgr,
            graph=graph,
            knowledge=knowledge,
            assembler=assembler,
            validator=validator,
            reflector=reflector,
            evolution_engine=evolution_engine,
            evolution_metrics=evolution_metrics,
            feedback_loop=feedback_loop,
            event_detector=event_detector,
            trigger_engine=trigger_engine,
            feedback_store=feedback_store,
            session_tracker=session_tracker,
            phase_router=phase_router,
            intent_result=intent_result,
            args=args,
            logger=logger,
            provider=provider,
            budget_tracker=budget_tracker,
            lifecycle_guard=lifecycle_guard,
            max_retries_map=max_retries_map,
            tracking_enabled=_tracking_enabled,
            memory_dir=memory_dir,
            complexity=complexity,
        )
        executor.run()
    else:
        executor = DryRunExecutor(
            state_mgr=state_mgr,
            graph=graph,
            args=args,
            max_retries_map=max_retries_map,
            complexity=complexity,
            logger=logger,
            kernel_root=KERNEL_ROOT,
        )
        executor.run()

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
        reporter = Reporter()
        tasks_path_file = Path(memory_dir) / "tasks.yaml"
        if tasks_path_file.exists():
            tm = TaskManager(memory_dir)
            tasks_list = tm.load_tasks()
        else:
            tasks_list = []
        if args.verbose:
            print(reporter.report_completion(state_mgr.get_state(), tasks_list))
        else:
            print(reporter.report_completion_clean(state_mgr.get_state(), tasks_list))

        if budget_tracker is not None:
            budget_report = budget_tracker.get_efficiency_report()
            if "尚未记录上下文组装数据" not in budget_report:
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
        print(f"[试运行] 最终状态: {state_mgr.state.get('status')}")
        print(f"[试运行] 总迭代次数: {state_mgr.state.get('iteration_count', 0)}")

    return state_mgr.get_state()
