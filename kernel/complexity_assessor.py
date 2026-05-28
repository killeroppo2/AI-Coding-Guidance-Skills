"""Task complexity assessment for routing optimization."""

_LOW_KEYWORDS = [
    "hello world",
    "single file",
    "config",
    "fix",
    "repair",
    "simple",
    "\u7b80\u5355",
    "\u4fee\u590d",
    "\u914d\u7f6e",
    "\u5355\u6587\u4ef6",
]

_HIGH_KEYWORDS = [
    "architecture",
    "system",
    "multi-module",
    "microservice",
    "distributed",
    "refactor entire",
    "\u67b6\u6784",
    "\u7cfb\u7edf",
    "\u591a\u6a21\u5757",
    "\u91cd\u6784\u6574\u4e2a",
]


def assess_complexity(goal: str) -> str:
    """Assess the complexity of a development goal.

    Keyword matches take priority over length checks. If both low and high
    keywords are present, high takes priority.

    Args:
        goal: The development goal string.

    Returns:
        'low', 'medium', or 'high'
    """
    goal_lower = goal.lower()

    has_high = any(kw in goal_lower for kw in _HIGH_KEYWORDS)
    has_low = any(kw in goal_lower for kw in _LOW_KEYWORDS)

    # High keywords always take priority
    if has_high:
        return "high"

    if has_low:
        return "low"

    # Length-based checks (secondary to keyword checks)
    stripped_len = len(goal.strip())
    if stripped_len < 20:
        return "low"
    if stripped_len > 100:
        return "high"

    return "medium"
