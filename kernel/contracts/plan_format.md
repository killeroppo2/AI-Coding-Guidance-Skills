# Plan Format Contract

This document defines the exact YAML structure for `memory/tasks.yaml`.
All planner output MUST conform to this schema.

## Schema

```yaml
tasks:
  - id: "T-001"
    title: "Task title"
    description: "Detailed description of what needs to be done"
    status: "pending"  # pending | in_progress | done | blocked
    acceptance_criteria:
      - "Criterion 1"
      - "Criterion 2"
    dependencies: []  # list of task ids, e.g. ["T-001", "T-002"]
    complexity: "medium"  # low | medium | high
```

## Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique task identifier in format T-NNN (e.g. T-001, T-012) |
| title | string | Yes | Short descriptive title |
| description | string | Yes | Detailed description of what needs to be done |
| status | string | Yes | One of: pending, in_progress, done, blocked |
| acceptance_criteria | list[string] | Yes | List of criteria that must be met for task completion |
| dependencies | list[string] | Yes | List of task IDs that must be done before this task can start |
| complexity | string | Yes | One of: low, medium, high |

## Status Values

- **pending**: Task has not been started yet.
- **in_progress**: Task is currently being worked on.
- **done**: Task is complete and acceptance criteria are met.
- **blocked**: Task cannot proceed. When blocked, a `blocked_reason` field is added.

## Rules

1. Task IDs are sequential: T-001, T-002, T-003, etc.
2. Dependencies MUST reference valid task IDs that exist in the file.
3. No circular dependencies are allowed.
4. A task can only be set to `in_progress` if all its dependencies have status `done`.
5. The file is located at `memory/tasks.yaml` relative to the project root.
