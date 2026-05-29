"""Rule-based intent analyzer for extracting goal semantics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class IntentResult:
    """Structured representation of an analyzed user goal."""

    goal_type: str = "build"
    output_form: str = "unknown"
    tech_hints: list[str] = field(default_factory=list)
    language: str = "en"
    is_vague: bool = False


_GOAL_TYPE_RULES: list[tuple[list[str], str]] = [
    (
        ["fix", "bug", "repair", "\u4fee\u590d", "\u4fee", "\u62a5\u9519"],
        "fix",
    ),
    (
        ["optimize", "perf", "performance", "\u6027\u80fd", "\u4f18\u5316"],
        "optimize",
    ),
    (
        ["review", "audit", "check", "\u68c0\u67e5", "\u5ba1\u67e5"],
        "audit",
    ),
    (
        ["explore", "try", "prototype", "\u8bd5\u8bd5", "\u63a2\u7d22"],
        "explore",
    ),
    (
        ["document", "doc", "write", "\u6587\u6863", "\u5199\u6587\u6863"],
        "document",
    ),
    (
        ["build", "create", "make", "\u642d\u5efa", "\u505a", "\u5efa"],
        "build",
    ),
]

_OUTPUT_FORM_RULES: list[tuple[list[str], str]] = [
    (["api", "rest", "graphql"], "api"),
    (["cli", "command"], "cli"),
    (["app", "web", "site", "\u7f51\u7ad9"], "app"),
    (["lib", "package", "sdk"], "library"),
    (["script"], "script"),
]

_TECH_HINTS_RULES: list[tuple[list[str], str]] = [
    (["python", "flask", "django", "fastapi"], "python"),
    (["react", "vue", "next", "nextjs", "next.js"], "react"),
    (["go", "golang"], "go"),
    (["rust", "cargo"], "rust"),
    (["node", "express", "nodejs", "node.js"], "node"),
    (["java", "spring", "springboot"], "java"),
    (["typescript", "ts"], "typescript"),
]

_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


class IntentAnalyzer:
    """Analyze a goal string to extract structured intent information."""

    def analyze(self, goal: str) -> IntentResult:
        """Analyze goal text and return structured intent.

        Args:
            goal: The user-provided goal string.

        Returns:
            IntentResult with extracted fields.
        """
        goal_type = self._detect_goal_type(goal)
        output_form = self._detect_output_form(goal)
        tech_hints = self._detect_tech_hints(goal)
        language = self._detect_language(goal)
        is_vague = self._detect_vague(goal, goal_type)

        return IntentResult(
            goal_type=goal_type,
            output_form=output_form,
            tech_hints=tech_hints,
            language=language,
            is_vague=is_vague,
        )

    def _detect_goal_type(self, goal: str) -> str:
        """Match verbs to determine the goal type."""
        goal_lower = goal.lower()
        for keywords, gtype in _GOAL_TYPE_RULES:
            for kw in keywords:
                if kw in goal_lower:
                    return gtype
        return "build"

    def _detect_output_form(self, goal: str) -> str:
        """Match nouns to determine the output form."""
        goal_lower = goal.lower()
        for keywords, form in _OUTPUT_FORM_RULES:
            for kw in keywords:
                # Use word boundary for short ASCII keywords to avoid false matches
                if len(kw) <= 3 and kw.isascii():
                    if re.search(r"\b" + re.escape(kw) + r"\b", goal_lower):
                        return form
                elif kw in goal_lower:
                    return form
        return "unknown"

    def _detect_tech_hints(self, goal: str) -> list[str]:
        """Detect technology mentions in the goal."""
        goal_lower = goal.lower()
        detected: list[str] = []
        for keywords, tech in _TECH_HINTS_RULES:
            for kw in keywords:
                if len(kw) <= 2:
                    if re.search(r"\b" + re.escape(kw) + r"\b", goal_lower):
                        detected.append(tech)
                        break
                elif kw in goal_lower:
                    detected.append(tech)
                    break
        return detected

    def _detect_language(self, goal: str) -> str:
        """Detect whether the goal is in English, Chinese, or mixed."""
        has_chinese = bool(_CHINESE_CHAR_RE.search(goal))
        has_ascii_alpha = bool(re.search(r"[a-zA-Z]", goal))

        if has_chinese and has_ascii_alpha:
            return "mixed"
        if has_chinese:
            return "zh"
        return "en"

    def _detect_vague(self, goal: str, goal_type: str) -> bool:
        """Determine if the goal is too vague to act on.

        A goal is vague if it has fewer than 5 words AND no verb match was found
        (i.e., goal_type fell through to the default 'build').
        """
        words = goal.split()
        has_verb_match = goal_type != "build" or self._has_explicit_build_verb(goal)
        return len(words) < 5 and not has_verb_match

    def _has_explicit_build_verb(self, goal: str) -> bool:
        """Check if the goal explicitly contains a build-type verb."""
        goal_lower = goal.lower()
        # Build verbs are the last entry in _GOAL_TYPE_RULES
        build_keywords = _GOAL_TYPE_RULES[-1][0]
        return any(kw in goal_lower for kw in build_keywords)
