"""Main execution loop for the kernel runner.

This module contains the core orchestration logic extracted from runner.py.
It handles Mode 1 (dry-run/scaffolding), Mode 2 (AI reads BOOT.md), and
Mode 3 (real AI execution via subprocess).
"""

import atexit
import json
import shlex
import signal
import subprocess
import sys
import time
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
from kernel.contracts import OutputContractValidator
from kernel.error_messages import format_error
from kernel.event_detector import EventDetector
from kernel.evolution.engine import EvolutionEngine
from kernel.evolution.metrics import EvolutionMetrics
from kernel.feedback_loop import FeedbackLoop
from kernel.graph_executor import GraphExecutor
from kernel.logging_config import setup_logging
from kernel.mode3_executor import _parse_transition
from kernel.philosophy.principles import should_retreat, should_stop_iterating
from kernel.reflector import Reflector
from kernel.reporter import Reporter
from kernel.skill_selector import select_skills_for_goal
from kernel.task_manager import TaskManager
from kernel.lifecycle_guard import LifecycleGuard
from kernel.security_policy import SecurityPolicy
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
        snapshot = tracker.build_resume_snapshot()
        print("Session Events:")
        print(f"  Total events: {tracker.get_event_count()}")
        print(f"  Status: {snapshot.get('status', 'unknown')}")
        if snapshot.get("last_node"):
            print(f"  Last node: {snapshot['last_node']}")
        if snapshot.get("node_path"):
            print(f"  Recent path: {' -> '.join(snapshot['node_path'])}")
        if snapshot.get("recent_errors"):
            print(f"  Recent errors: {len(snapshot['recent_errors'])}")
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

    # Reset node_visits on resume so stale counts don't trigger false stuck detection
    if args.resume:
        state_mgr.state["node_visits"] = {}
        # If previous run was interrupted, reset status to running so execution continues
        if state_mgr.state.get("status") == "interrupted":
            state_mgr.state["status"] = "running"

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
            state_mgr.state.setdefault("errors", []).append(
                "Parent process died - orphan detected"
            )
            state_mgr.save_state()
            sys.exit(1)

        lifecycle_guard = LifecycleGuard(on_shutdown=_orphan_shutdown)
        lifecycle_guard.start()

    if args.dry_run:
        print(f"[DRY RUN] Goal: {args.goal}")
        print(f"[DRY RUN] Max iterations: {args.max_iterations}")
        print(f"[DRY RUN] Starting node: {state_mgr.state.get('current_node', 'init')}")
        print()

    if mode3:
        assembler = ContextAssembler(KERNEL_ROOT)
        validator = OutputContractValidator(str(KERNEL_ROOT / "kernel" / "graph.yaml"))
        reflector = Reflector(memory_dir, knowledge)
        evolution_engine = EvolutionEngine(str(KERNEL_ROOT / "kernel"), graph)
        evolution_metrics = EvolutionMetrics()
        feedback_loop = FeedbackLoop(memory_dir, reflector, evolution_engine, evolution_metrics)
        event_detector = EventDetector(KERNEL_ROOT)
        retry_lightweight = False
        _last_was_lightweight = False

        from kernel.session_tracker import SessionTracker

        session_tracker = SessionTracker(memory_dir)
        session_tracker.track_event("session_start", {"goal": args.goal, "mode": "mode3"})

    # Build max_retries_map from graph nodes
    max_retries_map = {
        node["id"]: node.get("max_retries", 10) for node in graph.graph.get("nodes", [])
    }

    for i in range(args.max_iterations):
        state = state_mgr.get_state()

        if state_mgr.is_complete():
            break

        try:
            node = graph.get_current_node(state)
        except KeyError as e:
            state_mgr.state["status"] = "error"
            state_mgr.state.setdefault("errors", []).append(str(e))
            break

        prompt_path = graph.get_prompt_for_node(node["id"])

        if args.dry_run:
            print(f"[DRY RUN] Iteration {state.get('iteration_count', 0) + 1}:")
            print(f"  Node: {node['id']}")
            print(f"  Description: {node.get('description', 'N/A')}")
            print(f"  Prompt file: {prompt_path}")

            # Load prompt to show length
            full_prompt_path = KERNEL_ROOT / "kernel" / prompt_path
            if full_prompt_path.exists():
                prompt_content = full_prompt_path.read_text(encoding="utf-8")
                print(f"  Prompt length: {len(prompt_content)} chars")
            else:
                print("  Prompt file: [not found]")

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
                        logger.warning(
                            f"[SECURITY] Denied file write: {fpath}"
                        )

            # Determine next node
            transitions = graph.get_available_transitions(node["id"])
            if transitions:
                if transition_condition:
                    # Try to match the AI-provided condition
                    matched = False
                    for t in transitions:
                        if t.get("condition") == transition_condition:
                            next_node_id = t["to"]
                            matched = True
                            break
                    if not matched:
                        # Fallback to first transition
                        next_node_id = transitions[0]["to"]
                        logger.warning(
                            f"[WARNING] TRANSITION condition '{transition_condition}' "
                            f"does not match any available transition, "
                            f"falling back to first transition: {next_node_id}"
                        )
                else:
                    # No TRANSITION line - fallback to first transition
                    next_node_id = transitions[0]["to"]
                    logger.warning(
                        f"[WARNING] No TRANSITION line found in AI output, "
                        f"falling back to first transition: {next_node_id}"
                    )
                    state_mgr.state.setdefault("errors", []).append(
                        f"No TRANSITION line in AI output on node {node['id']}, "
                        f"fell back to: {next_node_id}"
                    )
                # Medium complexity: skip reflect/evolve
                if complexity == "medium" and next_node_id in ("reflect", "evolve"):
                    next_node_id = "plan"
                state_mgr.set_current_node(next_node_id)

                # Mark iteration success for incremental context
                assembler.mark_iteration_success(node["id"])

                # Track successful iteration transition
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

                # Populate progress_history for stall detection
                tasks_path_progress = Path(memory_dir) / "tasks.yaml"
                if tasks_path_progress.exists():
                    tm_progress = TaskManager(memory_dir)
                    _total, tasks_done_count = tm_progress.get_progress()
                    if _total > 0:
                        progress_history = state_mgr.state.setdefault("progress_history", [])
                        progress_history.append(tasks_done_count)
                        # Cap at 20 entries to prevent unbounded growth
                        if len(progress_history) > MAX_PROGRESS_HISTORY_ENTRIES:
                            state_mgr.state["progress_history"] = progress_history[
                                -MAX_PROGRESS_HISTORY_ENTRIES:
                            ]

                # Philosophy check: should_stop_iterating
                reflections_path = Path(memory_dir) / "reflections.jsonl"
                recent_reflections = []
                if reflections_path.exists():
                    lines = reflections_path.read_text(encoding="utf-8").strip().splitlines()
                    for line in lines[-RECENT_REFLECTIONS_WINDOW:]:
                        try:
                            recent_reflections.append(json.loads(line))
                        except (json.JSONDecodeError, ValueError):
                            pass
                if should_stop_iterating(state_mgr.state, recent_reflections):
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
                    print(f"  Next node: {next_node_id}")
                    print()
            else:
                state_mgr.state["status"] = "complete"
                if args.dry_run:
                    print("  Next node: END")
                    print()
                break

    # Mark as complete if we finished the loop
    if state_mgr.state.get("status") == "running":
        state_mgr.state["status"] = "complete"

    # Stop lifecycle guard if running
    if mode3:
        lifecycle_guard.stop()

    # Print completion report after Mode 3 execution
    if mode3:
        reporter = Reporter()
        tasks_path_file = Path(memory_dir) / "tasks.yaml"
        if tasks_path_file.exists():
            tm = TaskManager(memory_dir)
            tasks_list = tm.load_tasks()
        else:
            tasks_list = []
        print(reporter.report_completion(state_mgr.get_state(), tasks_list))

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
        print(f"[DRY RUN] Final status: {state_mgr.state.get('status')}")
        print(f"[DRY RUN] Total iterations: {state_mgr.state.get('iteration_count', 0)}")

    return state_mgr.get_state()
