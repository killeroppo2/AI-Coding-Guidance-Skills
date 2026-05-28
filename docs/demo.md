# Kernel Demo: Full Process Documentation

This document explains the complete execution flow of the AI development kernel,
using the URL shortener CLI demo as a concrete example.

## Overview

The kernel is a graph-based workflow executor that drives AI-assisted development
through a series of phases: initialization, planning, coding, testing, reviewing,
reflecting, and evolving. Each phase is a node in a directed graph with defined
transitions between them.

## 1. Goal Setting

When you run the kernel with a `--goal` argument, the orchestrator:

1. Parses the CLI arguments via `kernel/cli.py`
2. Stores the goal text in the kernel state (`kernel/state.yaml`)
3. Derives a workspace project name from the goal (sanitized for filesystem use)
4. Sets the initial node to `init`

Example:
```bash
python runner.py --goal "Build a URL shortener CLI with SQLite backend" --dry-run
```

The goal is stored as-is in state and used throughout execution for context assembly.

## 2. Skill Auto-Selection

Before the main loop begins, the kernel selects relevant skills from the
knowledge store (`skills/` directory indexed by `skills/_index.yaml`).

The selection algorithm in `kernel/skill_selector.py`:

1. Tokenizes the goal into lowercase words
2. For each available skill, computes a relevance score:
   - Tag matches: each matching tag scores 3 points
   - Description word matches: each matching word scores 1 point
3. Sorts skills by score (descending), then by name for stable ordering
4. Returns the top 5 skills (configurable via `max_skills`)

For the URL shortener goal, skills with tags like "cli", "database", "backend",
or descriptions containing those words would score highest.

The selected skills are stored in `state.context.skills_loaded` and used by the
context assembler to include relevant skill guidance in prompts.

## 3. Planning Phase

The `plan` node uses `prompts/planner.md` to instruct the LLM to:

- Break the goal into discrete, ordered tasks
- Create an execution plan stored in `memory/tasks.yaml`
- Determine dependencies between tasks
- Estimate complexity

In dry-run mode, the prompt file is loaded but not sent to any LLM. The kernel
reports the prompt length (2546 chars for the planner) and advances to the next
node via the first available transition.

## 4. Execution Flow

The core execution cycle is: `plan -> code -> test -> review -> plan`

### Code Node
- Uses `prompts/coder.md` (2177 chars)
- In real execution: picks the next pending task and generates implementation
- Produces source files in the workspace directory

### Test Node
- Uses `prompts/tester.md` (1806 chars)
- In real execution: runs the project's test suite
- Reports coverage metrics and failure details

### Review Node
- Uses `prompts/reviewer.md` (1817 chars)
- In real execution: reviews code for quality, patterns, and correctness
- Can flag issues that send execution back to the code node

The cycle repeats until all tasks are complete or max iterations is reached.

## 5. Reflection and Evolution

After the main execution cycle, the kernel can enter reflection and evolution
phases (when graph transitions lead there):

### Reflect Node
- Analyzes what worked and what did not across iterations
- Stores insights in `memory/reflections.jsonl`
- Feeds into the philosophy module's "should_stop_iterating" check

### Evolve Node
- Uses reflection data to improve the kernel itself
- Can modify prompts, adjust graph transitions, or update skill definitions
- Driven by the `EvolutionEngine` in `kernel/evolution/`

In the dry-run demo, the graph follows `review -> plan` (first available
transition), so reflect/evolve are not directly visited. They activate in
Mode 3 execution when the LLM provides specific transition conditions.

## 6. Dry-Run Output Example

Below is the actual output from running the demo showcase:

```
=== Running Demo Showcase scenario (dry-run) ===
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

[DRY RUN] Iteration 6:
  Node: plan
  ...
  (cycle repeats: plan -> code -> test -> review -> plan)

[DRY RUN] Final status: complete
[DRY RUN] Total iterations: 15
=== Demo Showcase scenario completed ===
```

## Key Takeaways

- The kernel uses a **directed graph** to define workflow phases
- In dry-run mode, it always follows the **first available transition** from each node
- The cycle `plan -> code -> test -> review` represents one complete development iteration
- Skills are auto-selected based on keyword matching against the goal text
- Each node has a dedicated prompt file that would be assembled with full context in real execution
- The `--max-iterations` flag controls how many graph traversals occur before stopping
