# Output Format Contract

> Every AI response in the kernel MUST conform to this specification.
> The runner validates output against this contract before advancing state.

## Required Lines

### TRANSITION (Required)

Every output MUST include exactly one `TRANSITION:` line indicating the
condition that determines the next workflow node.

```
TRANSITION: <condition>
```

Valid conditions depend on the current node (see graph.yaml):

| Node         | Valid Transitions                          |
|--------------|-------------------------------------------|
| init         | goal_loaded                               |
| plan         | plan_ready, plan_needs_revision           |
| code         | code_written, code_needs_retry            |
| test         | tests_pass, tests_fail                    |
| review       | review_pass, review_needs_changes         |
| reflect      | evolution_proposed, no_evolution_needed    |
| evolve       | evolution_applied                         |

### STATUS (Required)

Every output MUST include a `STATUS:` line indicating overall result:

```
STATUS: success
STATUS: failure
```

### FILES_WRITTEN (Optional)

If files were created or modified, report them:

```
FILES_WRITTEN: path/to/file1.py, path/to/file2.py
```

Multiple files are comma-separated. Omit this line if no files were written.

### ERROR (Optional)

If errors occurred, report each on its own line:

```
ERROR: Description of what went wrong
ERROR: Another error if multiple occurred
```

## Complete Examples

### Planner (success)

```
I have analyzed the goal and broken it into 3 tasks.
See memory/plan.md for the full plan.

FILES_WRITTEN: memory/plan.md, memory/progress.yaml
STATUS: success
TRANSITION: plan_ready
```

### Planner (needs revision)

```
The goal is ambiguous. I need clarification on the scope.

ERROR: Goal does not specify target language or framework
STATUS: failure
TRANSITION: plan_needs_revision
```

### Coder (success)

```
Implemented the REST API endpoint for user creation.
All tests written and passing locally.

FILES_WRITTEN: src/api/users.py, tests/test_users.py
STATUS: success
TRANSITION: code_written
```

### Coder (retry needed)

```
Hit a dependency conflict that prevents implementation.

ERROR: Package X conflicts with package Y at version 2.0
STATUS: failure
TRANSITION: code_needs_retry
```

### Tester (pass)

```
All 42 tests pass. Coverage is at 94%.

STATUS: success
TRANSITION: tests_pass
```

### Tester (fail)

```
3 tests failing in test_api.py.

ERROR: test_create_user fails with ValidationError
ERROR: test_delete_user fails with 404
ERROR: test_list_users missing assertion
STATUS: failure
TRANSITION: tests_fail
```

### Reviewer (pass)

```
Code quality is acceptable. Patterns are followed correctly.

STATUS: success
TRANSITION: review_pass
```

### Reviewer (needs changes)

```
Found issues that need fixing before merge.

ERROR: Missing input validation in users.py line 42
ERROR: Hardcoded database URL should be configurable
STATUS: failure
TRANSITION: review_needs_changes
```

### Reflector (evolution proposed)

```
Identified a recurring pattern that should be codified.

FILES_WRITTEN: memory/reflections.jsonl
STATUS: success
TRANSITION: evolution_proposed
```

### Reflector (no evolution)

```
Iteration went smoothly. No kernel changes needed.

FILES_WRITTEN: memory/reflections.jsonl
STATUS: success
TRANSITION: no_evolution_needed
```

### Orchestrator (goal loaded)

```
Goal loaded and context initialized.

STATUS: success
TRANSITION: goal_loaded
```

## Validation Rules

1. Output MUST contain exactly one `TRANSITION:` line
2. Output MUST contain exactly one `STATUS:` line
3. TRANSITION value MUST be valid for the current node (per graph.yaml)
4. STATUS value MUST be either `success` or `failure`
5. FILES_WRITTEN paths must be comma-separated if multiple
6. ERROR lines are optional but recommended when STATUS is failure

