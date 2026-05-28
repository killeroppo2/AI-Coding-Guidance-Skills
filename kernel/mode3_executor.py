"""Mode 3 subprocess execution logic for the kernel runner.

Contains signal handling, subprocess management, AI output parsing,
and the lightweight retry mechanism for Mode 3 (real AI execution).
"""

import atexit
import shlex
import signal
import subprocess
import sys
import time
from typing import Any

from kernel.contracts import OutputContractValidator
from kernel.context_assembler import ContextAssembler
from kernel.error_messages import format_error
from kernel.feedback_loop import FeedbackLoop
from kernel.graph_executor import GraphExecutor
from kernel.reporter import Reporter
from kernel.validators import _validate_workspace_paths
from memory.state_manager import StateManager


# Module-level reference to the active subprocess for signal handler cleanup
_active_subprocess = None  # type: subprocess.Popen | None


def _parse_transition(output: str) -> str | None:
    """Parse AI output for a TRANSITION line.

    Args:
        output: The AI subprocess stdout.

    Returns:
        The transition condition string, or None if not found.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("TRANSITION:"):
            return stripped[len("TRANSITION:"):].strip()
    return None


def setup_signal_handlers(state_mgr: StateManager) -> None:
    """Register signal and atexit handlers for graceful shutdown in Mode 3.

    Args:
        state_mgr: The state manager instance to save state on shutdown.
    """
    global _active_subprocess

    def _shutdown_handler(signum, frame):
        global _active_subprocess
        if _active_subprocess is not None:
            try:
                _active_subprocess.terminate()
                _active_subprocess.wait(timeout=5)
            except Exception:
                try:
                    _active_subprocess.kill()
                except Exception:
                    pass
        state_mgr.state["status"] = "interrupted"
        state_mgr.state.setdefault("errors", []).append(
            "Execution interrupted by signal"
        )
        state_mgr.save_state()
        sys.exit(130)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    def _atexit_save():
        if state_mgr.state.get("status") == "running":
            state_mgr.state["status"] = "interrupted"
            state_mgr.save_state()

    atexit.register(_atexit_save)


def run_mode3_iteration(
    *,
    node: dict[str, Any],
    args: Any,
    state_mgr: StateManager,
    graph: GraphExecutor,
    assembler: ContextAssembler,
    validator: OutputContractValidator,
    feedback_loop: FeedbackLoop,
    retry_lightweight: bool,
    last_was_lightweight: bool,
    complexity: str,
) -> dict[str, Any]:
    """Execute a single Mode 3 iteration.

    Args:
        node: The current graph node dict.
        args: The parsed CLI arguments namespace.
        state_mgr: State manager instance.
        graph: Graph executor instance.
        assembler: Context assembler instance.
        validator: Output contract validator instance.
        feedback_loop: Feedback loop instance.
        retry_lightweight: Whether to use lightweight retry prompt.
        last_was_lightweight: Whether last iteration was lightweight.
        complexity: Current complexity level.

    Returns:
        A dict with keys:
        - 'action': one of 'continue', 'break', 'advanced'
        - 'retry_lightweight': updated retry flag
        - 'last_was_lightweight': updated lightweight flag
        - 'error': optional error string
    """
    global _active_subprocess
    from knowledge.store import KnowledgeStore

    result = {
        "action": "continue",
        "retry_lightweight": False,
        "last_was_lightweight": last_was_lightweight,
    }

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
        result["last_was_lightweight"] = True
    else:
        # Try incremental context for same-node repeats
        knowledge = KnowledgeStore(str(assembler.kernel_root / "knowledge"))
        state = state_mgr.get_state()
        context_prompt = assembler.assemble_incremental(
            state, node, graph, knowledge
        )
        if not context_prompt:
            # Full context needed
            context_prompt = assembler.assemble(state, node, graph, knowledge)
        result["last_was_lightweight"] = False

    try:
        proc = subprocess.Popen(
            shlex.split(args.ai_command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _active_subprocess = proc
        try:
            stdout, stderr = proc.communicate(
                input=context_prompt, timeout=args.timeout
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            _active_subprocess = None
            timeout_detail = f"Timeout after {args.timeout}s on node {node['id']}"
            if stdout:
                timeout_detail += f" | partial stdout: {stdout[:200]}"
            if stderr:
                timeout_detail += f" | stderr: {stderr[:200]}"
            state_mgr.state.setdefault("errors", []).append(timeout_detail)
            state_mgr.trim_errors()
            print(
                format_error(
                    "timeout",
                    seconds=str(args.timeout),
                    node=node["id"],
                ),
                file=sys.stderr,
            )
            # Invalidate incremental context on failure
            assembler.mark_iteration_failure()
            result["action"] = "continue"
            return result
        _active_subprocess = None
        result_returncode = proc.returncode
        result_stdout = stdout
        result_stderr = stderr
        if result_returncode != 0:
            print(
                f"[ERROR] AI command exited with code {result_returncode}: "
                f"{result_stderr.strip()}",
                file=sys.stderr,
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
                result["action"] = "continue"
                return result
            elif args.retry_strategy == "backoff":
                visit_count = state_mgr.state.get("node_visits", {}).get(node["id"], 1)
                delay = min(2 ** (visit_count - 1), 60)
                time.sleep(delay)
                result["action"] = "continue"
                return result
            else:  # "continue"
                result["action"] = "continue"
                return result
        ai_output = result_stdout
        transition_condition = _parse_transition(ai_output)
    except FileNotFoundError:
        print(
            f"Error: AI command not found: '{shlex.split(args.ai_command)[0]}'. "
            f"Please verify the command is installed and in your PATH.",
            file=sys.stderr,
        )
        print(
            format_error(
                "command_not_found",
                cmd=shlex.split(args.ai_command)[0],
            ),
            file=sys.stderr,
        )
        state_mgr.state["status"] = "error"
        state_mgr.state.setdefault("errors", []).append(
            f"Command not found: {shlex.split(args.ai_command)[0]}"
        )
        result["action"] = "break"
        return result

    # Validate output against contract
    contract_result = validator.validate_output(ai_output, node["id"])
    if not contract_result.valid:
        for violation in contract_result.violations:
            print(
                f"[CONTRACT VIOLATION] {violation}",
                file=sys.stderr,
            )
        state_mgr.state.setdefault("errors", []).append(
            f"Contract violations on node {node['id']}: "
            f"{contract_result.violations}"
        )
        state_mgr.trim_errors()
        # Check if violations are about missing format lines
        has_format_violation = any(
            "Missing required TRANSITION" in v
            or "Missing required STATUS" in v
            for v in contract_result.violations
        )
        if has_format_violation and not result["last_was_lightweight"]:
            result["retry_lightweight"] = True
        # Invalidate incremental context on failure
        assembler.mark_iteration_failure()
        # Stay on same node - do not advance
        result["action"] = "continue"
        return result

    # Validate workspace boundary for files_written
    workspace_path = state_mgr.state.get("workspace_path", "")
    if workspace_path and contract_result.files_written:
        ws_violations = _validate_workspace_paths(
            contract_result.files_written, workspace_path
        )
        for v in ws_violations:
            print(
                f"[WARNING] Workspace boundary: {v}",
                file=sys.stderr,
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
                print(
                    f"[WARNING] TRANSITION condition '{transition_condition}' "
                    f"does not match any available transition, "
                    f"falling back to first transition: {next_node_id}",
                    file=sys.stderr,
                )
        else:
            # No TRANSITION line - fallback to first transition
            next_node_id = transitions[0]["to"]
            print(
                f"[WARNING] No TRANSITION line found in AI output, "
                f"falling back to first transition: {next_node_id}",
                file=sys.stderr,
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

        result["action"] = "advanced"
    else:
        state_mgr.state["status"] = "complete"
        result["action"] = "break"

    return result
