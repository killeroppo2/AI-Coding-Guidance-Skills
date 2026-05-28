# Demo Script: Step-by-Step Walkthrough

This guide walks through running the kernel demo from scratch, explaining
what happens at each step.

## Prerequisites

```bash
# Install the project in development mode
pip install -e ".[dev]"

# Initialize runtime files (creates state.yaml, graph.yaml, etc.)
python runner.py --init
```

## Step 1: Set a Goal

The kernel needs a development goal to work toward. Goals should be specific
enough to break into tasks but broad enough to require multiple iterations.

Example goal: "Build a URL shortener CLI with SQLite backend"

This goal works well because it involves:
- CLI argument parsing (matches CLI-related skills)
- Database operations (matches database/backend skills)
- Multiple distinct features (shorten, lookup, list, delete)

## Step 2: Run Dry-Run

Execute the kernel in dry-run mode to see the graph traversal without
calling any LLM:

```bash
python runner.py \
    --goal "Build a URL shortener CLI with SQLite backend" \
    --dry-run \
    --verbose \
    --max-iterations 15
```

Expected output:
```
[DRY RUN] Goal: Build a URL shortener CLI with SQLite backend
[DRY RUN] Max iterations: 15
[DRY RUN] Starting node: init

[DRY RUN] Iteration 1:
  Node: init
  Description: Initialize context, load goal, assess current state
  Prompt file: prompts/orchestrator.md
  Prompt length: 2115 chars
  Next node: plan

[DRY RUN] Iteration 2:
  Node: plan
  Description: Break goal into tasks, create execution plan
  Prompt file: prompts/planner.md
  Prompt length: 2546 chars
  Next node: code

[DRY RUN] Iteration 3:
  Node: code
  Description: Implement next task from plan
  Prompt file: prompts/coder.md
  Prompt length: 2177 chars
  Next node: test

[DRY RUN] Iteration 4:
  Node: test
  Description: Run tests, verify coverage
  Prompt file: prompts/tester.md
  Prompt length: 1806 chars
  Next node: review

[DRY RUN] Iteration 5:
  Node: review
  Description: Code review for quality and patterns
  Prompt file: prompts/reviewer.md
  Prompt length: 1817 chars
  Next node: plan
```

The pattern then repeats: `plan -> code -> test -> review -> plan -> ...`

## Step 3: Understand the Output

Each iteration shows:

- **Node**: The current workflow phase (init, plan, code, test, review)
- **Description**: What that phase does in real execution
- **Prompt file**: The template used to instruct the LLM for this phase
- **Prompt length**: Size of the prompt in characters (useful for token estimation)
- **Next node**: Where the graph transitions to next

The "Final status: complete" line confirms the kernel finished all iterations
without getting stuck on any node.

### Why the Cycle Repeats

In dry-run mode, the kernel always picks the **first transition** from each
node. The graph is structured so that `review` transitions back to `plan`,
creating the development loop. In real execution (Mode 3), the LLM evaluates
conditions like "all tasks done" to break out of the loop.

## Step 4: Run with --generate-prompt

To see what the assembled context looks like for the current state:

```bash
python runner.py \
    --goal "Build a URL shortener CLI with SQLite backend" \
    --generate-prompt
```

This outputs the full prompt that would be sent to an LLM, including:
- The current goal and state
- Selected skill guidance
- Graph position and available transitions
- Task status from memory

This is useful for debugging prompt assembly or understanding what
context the LLM receives.

## Step 5: Explore with --status

Check the current kernel state at any time:

```bash
python runner.py --status
```

This shows:
- Current goal (if set)
- Execution status (idle, running, complete, stuck)
- Current graph node
- Iteration count
- Task progress (if tasks.yaml exists)

After a dry-run, the status will show the state as it was left by the
traversal. Use `python runner.py --init` to reset back to initial state.

## Summary

| Command | Purpose |
|---------|---------|
| `--init` | Reset/initialize runtime state |
| `--goal "..." --dry-run` | See graph traversal without LLM |
| `--goal "..." --generate-prompt` | See assembled prompt context |
| `--status` | Check current kernel state |
| `--goal "..." --dry-run --verbose` | Same as dry-run (verbose adds detail in Mode 3) |
