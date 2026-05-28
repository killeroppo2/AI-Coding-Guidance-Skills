"""User-friendly error messages with recovery suggestions.

Maps error types to human-readable messages with what/why/fix structure.
"""

import re

# Error message templates with what/why/fix structure
ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "stuck_node": {
        "what": "The system got stuck on node '{node}'",
        "why": "It visited this node {visits} times without making progress (max: {max_retries})",
        "fix": (
            "Try: simplify your goal, add relevant skills,"
            " or increase max_retries with --max-iterations"
        ),
    },
    "command_not_found": {
        "what": "AI command '{cmd}' not found",
        "why": "The command is not installed or not in your PATH",
        "fix": "Install it with: pip install {cmd} (or check your shell's PATH configuration)",
    },
    "timeout": {
        "what": "Iteration timed out after {seconds}s on node '{node}'",
        "why": "The AI subprocess took too long to respond",
        "fix": (
            "Try: increase --timeout value, simplify current task,"
            " or check if AI service is responding"
        ),
    },
    "skill_not_found": {
        "what": "Skill '{name}' not found in knowledge store",
        "why": "The skill is referenced but not installed in skills/",
        "fix": "Run: python3.12 setup_check.py --check to validate skill installation",
    },
    "contract_violation": {
        "what": "AI output did not match expected format on node '{node}'",
        "why": "Missing or invalid TRANSITION/STATUS line in AI response",
        "fix": (
            "This usually means the AI prompt needs adjustment."
            " Try --retry-strategy continue to retry"
        ),
    },
    "state_corrupted": {
        "what": "State file could not be parsed",
        "why": "The state.yaml file contains invalid YAML or is empty",
        "fix": "Delete kernel/state.yaml and restart (state will be recreated with defaults)",
    },
}


def format_error(error_type: str, **kwargs) -> str:
    """Format an error message with recovery suggestions.

    Args:
        error_type: One of the keys in ERROR_MESSAGES.
        **kwargs: Template variables to substitute.

    Returns:
        Multi-line formatted error string with what/why/fix.
        Returns a generic message for unknown error types.
    """
    template = ERROR_MESSAGES.get(error_type)
    if template is None:
        # Generic fallback
        detail = kwargs.get("detail", error_type)
        return (
            f"  What happened: An error occurred ({detail})\n"
            f"  Why it matters: The kernel cannot continue the current operation\n"
            f"  What to do: Check the error details above and retry"
        )

    try:
        what = template["what"].format(**kwargs)
        why = template["why"].format(**kwargs)
        fix = template["fix"].format(**kwargs)
    except (KeyError, IndexError):
        # If template variables are missing, use raw templates
        what = template["what"]
        why = template["why"]
        fix = template["fix"]

    return f"  What happened: {what}\n  Why it matters: {why}\n  What to do: {fix}"


def classify_error(raw_error: str) -> tuple[str, dict]:
    """Classify a raw error string into a known error type.

    Parses the error message to determine type and extract kwargs.

    Args:
        raw_error: Raw error string from the runner.

    Returns:
        Tuple of (error_type, kwargs_dict).
        Returns ("unknown", {"detail": raw_error}) if cannot classify.
    """
    # Check for command not found
    cmd_match = re.search(r"command not found:\s*(\S+)", raw_error, re.IGNORECASE)
    if cmd_match:
        return ("command_not_found", {"cmd": cmd_match.group(1)})

    # Check for timeout
    timeout_match = re.search(r"timeout after (\d+)s on node (\S+)", raw_error, re.IGNORECASE)
    if timeout_match:
        return ("timeout", {"seconds": timeout_match.group(1), "node": timeout_match.group(2)})

    # Check for stuck node
    stuck_match = re.search(
        r"node '(\S+)' exceeded max_retries.*visited (\d+) times.*max (\d+)",
        raw_error,
        re.IGNORECASE,
    )
    if stuck_match:
        return ("stuck_node", {
            "node": stuck_match.group(1),
            "visits": stuck_match.group(2),
            "max_retries": stuck_match.group(3),
        })

    # Check for contract violations
    if "contract violation" in raw_error.lower():
        return ("contract_violation", {"node": "unknown"})

    # Check for skill not found
    skill_match = re.search(r"skill not found:\s*(\S+)", raw_error, re.IGNORECASE)
    if skill_match:
        return ("skill_not_found", {"name": skill_match.group(1)})

    # Unknown
    return ("unknown", {"detail": raw_error})
