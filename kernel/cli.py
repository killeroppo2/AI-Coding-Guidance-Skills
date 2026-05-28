"""Command-line interface argument parsing for the kernel runner."""

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Self-evolving AI development kernel runner",
        prog="runner",
    )
    parser.add_argument(
        "--goal",
        type=str,
        default=None,
        help="The development goal to work toward",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize runtime files and exit",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run setup checks and exit",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show iteration-by-iteration progress",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print current status and exit",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=30,
        help="Maximum number of iterations (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without modifying state",
    )
    parser.add_argument(
        "--ai-command",
        type=str,
        default=None,
        help="AI CLI command for Mode 3 execution (e.g., 'claude --print')",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per iteration in seconds for Mode 3 (default: 300)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue from saved state instead of starting fresh",
    )
    parser.add_argument(
        "--generate-prompt",
        action="store_true",
        help="Output assembled prompt to stdout and exit",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Manual workspace project name override (default: derived from goal)",
    )
    parser.add_argument(
        "--skills",
        type=str,
        default=None,
        help="Comma-separated list of skill names to load (overrides auto-selection)",
    )
    parser.add_argument(
        "--retry-strategy",
        type=str,
        choices=["continue", "skip", "backoff"],
        default="continue",
        help="Retry strategy on failure: continue (retry same), skip (advance to next), backoff (exponential wait)",
    )
    parser.add_argument(
        "--execution-mode",
        type=str,
        choices=["kernel", "ralph"],
        default="kernel",
        help="Execution mode: kernel (default) or ralph (exports prd.json after planning)",
    )
    parser.add_argument(
        "--complexity",
        type=str,
        choices=["auto", "low", "medium", "high"],
        default="auto",
        help="Task complexity level for routing (default: auto-detect from goal)",
    )
    return parser.parse_args(argv)
