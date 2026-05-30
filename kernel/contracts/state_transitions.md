# State Transitions

> All valid state transitions in the kernel workflow graph.
> Each transition maps a source node to a target node via a named condition.

## Transition Table

| Source Node | Target Node | Condition | Description |
|-------------|-------------|-----------|-------------|
| init | plan | goal_loaded | Goal has been loaded and context initialized |
| plan | code | plan_ready | Plan is complete and ready for implementation |
| plan | plan | plan_needs_revision | Plan needs revision before proceeding |
| code | test | code_written | Code implementation is complete |
| code | code | code_needs_retry | Code needs another attempt |
| test | review | tests_pass | All tests pass with sufficient coverage |
| test | code | tests_fail | Tests are failing, code needs fixes |
| review | reflect | review_pass | Code review passed quality checks |
| review | code | review_needs_changes | Review found issues requiring changes |
| reflect | evolve | evolution_proposed | Reflection identified kernel evolution opportunity |
| reflect | code | tasks_remaining | No evolution needed, pending tasks in plan. Skip re-plan, go to code |
| reflect | plan | all_tasks_done | No evolution needed, all tasks completed. Ready for next goal |
| evolve | plan | evolution_applied | Evolution changes have been applied |

## Pre-conditions and Post-conditions

### init -> plan (goal_loaded)

- **Pre-conditions:** Goal is set in `kernel/state.yaml`, constitution and graph are loaded
- **Post-conditions:** Context is initialized, `current_node` set to `plan`

### plan -> code (plan_ready)

- **Pre-conditions:** Plan exists in `memory/plan.md`, tasks defined in `memory/tasks.yaml`
- **Post-conditions:** Plan is validated, next task is identified, `current_node` set to `code`

### plan -> plan (plan_needs_revision)

- **Pre-conditions:** Plan was attempted but found insufficient or unclear
- **Post-conditions:** Revision feedback recorded, `current_node` remains `plan`

### code -> test (code_written)

- **Pre-conditions:** Current task code is implemented, files written to workspace
- **Post-conditions:** Code changes saved, `current_node` set to `test`

### code -> code (code_needs_retry)

- **Pre-conditions:** Code attempt failed (compilation error, missing dependency)
- **Post-conditions:** Error recorded, retry counter incremented, `current_node` remains `code`

### test -> review (tests_pass)

- **Pre-conditions:** Test suite executed, all tests pass, coverage threshold met
- **Post-conditions:** Test results recorded, `current_node` set to `review`

### test -> code (tests_fail)

- **Pre-conditions:** Test suite executed, one or more tests failing
- **Post-conditions:** Failure details recorded, `current_node` set to `code`

### review -> reflect (review_pass)

- **Pre-conditions:** Code review completed, no blocking issues found
- **Post-conditions:** Review approval recorded, `current_node` set to `reflect`

### review -> code (review_needs_changes)

- **Pre-conditions:** Code review found issues that must be fixed
- **Post-conditions:** Review feedback recorded, `current_node` set to `code`

### reflect -> evolve (evolution_proposed)

- **Pre-conditions:** Reflection identified a pattern or improvement for the kernel
- **Post-conditions:** Evolution proposal recorded in `memory/reflections.jsonl`, `current_node` set to `evolve`

### reflect -> code (tasks_remaining)

- **Pre-conditions:** Reflection completed, no kernel changes warranted, pending tasks exist in tasks.yaml
- **Post-conditions:** Reflection logged, `current_node` set to `code` (skips re-plan overhead)

### reflect -> plan (all_tasks_done)

- **Pre-conditions:** All tasks in tasks.yaml have status `done`, no kernel evolution needed
- **Post-conditions:** Reflection logged, goal marked complete, `current_node` set to `plan` for next goal

### evolve -> plan (evolution_applied)

- **Pre-conditions:** Evolution changes reviewed and applied to kernel files
- **Post-conditions:** Kernel updated, `current_node` set to `plan`

## Fields Updated on Transition

When any transition occurs, the following fields in `kernel/state.yaml` must be updated:

| Field | Update Rule |
|-------|-------------|
| `current_node` | Set to the target node of the transition |
| `iteration_count` | Increment by 1 |
| `last_updated` | Set to current ISO 8601 timestamp |
| `node_visits` | Increment count for the target node |
