#!/usr/bin/env python3
"""Mock AI server for end-to-end testing.

Reads assembled prompt from stdin, analyzes it to determine current node,
generates realistic AI-like responses with proper contract format.

The context assembler includes a "Current Node: <node_id>" line which we
use as the primary signal for determining which node response to generate.

Usage: echo "prompt text" | python tests/e2e/mock_ai_server.py
"""
import os
import sys


def _detect_node(prompt: str) -> str:
    """Detect the current node from the assembled prompt.

    Primary: look for 'Current Node: <id>' line from context assembler.
    Fallback: keyword matching on prompt content.
    """
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("Current Node:"):
            node_id = stripped[len("Current Node:"):].strip()
            return node_id

    # Fallback: keyword matching
    prompt_lower = prompt.lower()
    if "reflect" in prompt_lower:
        return "reflect"
    if "reviewer" in prompt_lower:
        return "review"
    if "tester" in prompt_lower:
        return "test"
    if "coder" in prompt_lower:
        return "code"
    if "planner" in prompt_lower:
        return "plan"
    if "orchestrator" in prompt_lower:
        return "init"
    return "init"


def main():
    prompt = sys.stdin.read()
    node = _detect_node(prompt)

    if node == "init":
        print("I have loaded the goal and assessed the current state.")
        print("STATUS: success")
        print("TRANSITION: goal_loaded")
    elif node == "plan":
        print("## Plan")
        print("1. Create main module")
        print("2. Add calculator functions")
        print("3. Write tests")
        print("STATUS: success")
        print("TRANSITION: plan_ready")
    elif node == "code":
        workspace = _extract_workspace(prompt)
        if workspace:
            os.makedirs(workspace, exist_ok=True)
            with open(os.path.join(workspace, "calculator.py"), "w") as f:
                f.write("def add(a, b): return a + b\ndef subtract(a, b): return a - b\n")
        print("I have written the calculator module.")
        print("FILES_WRITTEN: calculator.py")
        print("STATUS: success")
        print("TRANSITION: code_written")
    elif node == "test":
        print("All tests passing: 3 passed in 0.5s")
        print("STATUS: success")
        print("TRANSITION: tests_pass")
    elif node == "review":
        print("Code looks good. No issues found.")
        print("STATUS: success")
        print("TRANSITION: review_pass")
    elif node in ("reflect", "evolve"):
        print("Reflection: execution went smoothly. No evolution needed.")
        print("STATUS: success")
        print("TRANSITION: no_evolution_needed")
    else:
        # Default fallback
        print("STATUS: success")
        print("TRANSITION: goal_loaded")


def _extract_workspace(prompt: str) -> str:
    """Extract workspace path from prompt."""
    for line in prompt.split("\n"):
        if "workspace" in line.lower() and "/" in line:
            parts = line.split()
            for part in parts:
                if "/" in part and "workspace" in part.lower():
                    return part.strip("'\"")
    return ""


if __name__ == "__main__":
    main()
