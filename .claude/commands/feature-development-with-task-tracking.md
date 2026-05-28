---
name: feature-development-with-task-tracking
description: Workflow command scaffold for feature-development-with-task-tracking in AI-Coding-Guidance-Skills.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /feature-development-with-task-tracking

Use this workflow when working on **feature-development-with-task-tracking** in `AI-Coding-Guidance-Skills`.

## Goal

Implements a new feature or major capability, tracks it in the .agents/tasks system, and marks it as completed upon delivery.

## Common Files

- `kernel/**/*.py`
- `knowledge/skills/**`
- `tests/**/*.py`
- `.agents/tasks/task-self-evolving-kernel/features/FEAT-*.json`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create or update implementation files (e.g., kernel modules, knowledge skills, scripts, etc.)
- Add or update corresponding feature file in .agents/tasks/task-self-evolving-kernel/features/FEAT-XXX.json
- Update or create tests to cover the new feature
- Mark the feature as completed by updating the FEAT-XXX.json file (status or metadata)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.