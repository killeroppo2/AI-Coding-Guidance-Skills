---
name: test-suite-expansion-and-coverage-increase
description: Workflow command scaffold for test-suite-expansion-and-coverage-increase in AI-Coding-Guidance-Skills.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /test-suite-expansion-and-coverage-increase

Use this workflow when working on **test-suite-expansion-and-coverage-increase** in `AI-Coding-Guidance-Skills`.

## Goal

Adds new tests to increase code coverage, often targeting previously uncovered code paths or edge cases.

## Common Files

- `tests/**/*.py`
- `.agents/tasks/task-self-evolving-kernel/features/FEAT-*.json`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Identify coverage gaps or missing test cases
- Add new test files or update existing ones in tests/
- Optionally update related feature tracking files for coverage goals
- Commit with coverage statistics and summary

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.