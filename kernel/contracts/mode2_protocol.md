# Mode 2 Protocol

> Instructions for AI agents operating in Mode 2 (standalone, without runner.py).
> In Mode 2, the AI reads BOOT.md directly and manages all state transitions itself.

## Files to Read

Before each iteration, read these files to understand current state:

| File | Purpose |
|------|---------|
| `kernel/state.yaml` | Current node, iteration count, goal, errors |
| `memory/tasks.yaml` | Task list with statuses and dependencies |
| `kernel/graph.yaml` | Valid transitions between workflow nodes |
| `memory/decisions.jsonl` | Append-only log of decisions made |
| `memory/reflections.jsonl` | Append-only log of reflections |

## File Formats

- **YAML** for `kernel/state.yaml` and `memory/tasks.yaml`
- **JSONL** (one JSON object per line) for `memory/decisions.jsonl` and `memory/reflections.jsonl`

## Common Operations

### Picking the Next Task

Read `memory/tasks.yaml` and find the first task with `status: pending` whose
dependencies are all `status: done`.

```yaml
# memory/tasks.yaml
tasks:
  - id: task-1
    description: "Set up project structure"
    status: done
    deps: []
  - id: task-2
    description: "Implement core module"
    status: pending
    deps: [task-1]
  - id: task-3
    description: "Write tests"
    status: pending
    deps: [task-2]
```

In this example, `task-2` is the next task because its only dependency (`task-1`)
has `status: done`.

### Marking a Task Done

Update the task entry in `memory/tasks.yaml` by setting `status: done`:

```yaml
# memory/tasks.yaml (after completing task-2)
tasks:
  - id: task-1
    description: "Set up project structure"
    status: done
    deps: []
  - id: task-2
    description: "Implement core module"
    status: done
    deps: [task-1]
  - id: task-3
    description: "Write tests"
    status: pending
    deps: [task-2]
```

### Advancing the Node

After completing work for the current node, update `current_node` in
`kernel/state.yaml` based on the transition condition from `kernel/graph.yaml`:

```yaml
# kernel/state.yaml (advancing from plan to code)
current_node: code
iteration_count: 3
last_updated: "2025-01-27T12:00:00Z"
goal: "Build authentication module"
status: running
node_visits:
  init: 1
  plan: 2
  code: 1
errors: []
context:
  skills_loaded: []
  current_task: "task-2"
  phase: "implementation"
```

### Recording a Decision

Append a single JSON line to `memory/decisions.jsonl`:

```yaml
# Append this JSON line to memory/decisions.jsonl
{"timestamp": "2025-01-27T12:00:00Z", "node": "plan", "decision": "Split auth into login and register tasks", "reasoning": "Separation of concerns makes testing easier"}
```

### Tracking a Node Transition

When transitioning between nodes, update `node_visits` in `kernel/state.yaml`
to track how many times each node has been visited:

```yaml
# kernel/state.yaml (after transitioning from code to test)
current_node: test
iteration_count: 4
last_updated: "2025-01-27T12:30:00Z"
goal: "Build authentication module"
status: running
node_visits:
  init: 1
  plan: 2
  code: 2
  test: 1
errors: []
context:
  skills_loaded: []
  current_task: "task-2"
  phase: "testing"
```

## State Update Checklist

On every transition, update these fields in `kernel/state.yaml`:

1. `current_node` - set to the target node
2. `iteration_count` - increment by 1
3. `last_updated` - set to current ISO 8601 timestamp
4. `node_visits` - increment the count for the target node

## Error Handling

If an error occurs during execution:

1. Append the error message to `errors` list in `kernel/state.yaml`
2. Record a decision in `memory/decisions.jsonl` explaining the error
3. Use the appropriate retry transition if available (e.g., `code_needs_retry`)
4. If max retries exceeded, use `stuck_handler` node if defined in graph.yaml
