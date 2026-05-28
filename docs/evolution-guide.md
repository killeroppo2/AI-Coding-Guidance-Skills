# Evolution Guide: How Self-Evolution Works

## Overview

The kernel's self-evolution mechanism allows it to improve its own workflow
based on empirical execution data. Rather than requiring manual tuning, the
kernel observes its own performance, identifies patterns of failure, and
automatically applies targeted improvements -- all within strict constitutional
constraints that prevent it from compromising its own integrity.

## Reflection Phase

After every iteration in Mode 3, the FeedbackLoop collects:

- **Node ID**: Which workflow node was executed (init, plan, code, test, review, reflect, evolve).
- **Result**: Success or failure.
- **Errors**: Any error messages produced.
- **Duration**: How long the iteration took.
- **Iteration count**: The current iteration number.

The Reflector analyzes this data and produces a reflection record containing:
- Whether the iteration succeeded
- Learnings (patterns observed during success)
- Issues (specific problems encountered during failure)
- Philosophy signals (e.g., should the kernel stop iterating due to diminishing returns)

Each reflection is appended to `memory/reflections.jsonl` as an immutable record.

## Pattern Detection

The Reflector reads the last 10 reflections and looks for patterns:

- **Repeated node failures**: If the same node fails 3+ times, it indicates a
  systematic problem rather than a transient error.
- **Consistent success**: If a node succeeds 5+ times, the pattern is worth
  preserving as a rule.
- **Failure categorization**: Each failure is classified as timeout, test_failure,
  code_error, dependency_issue, or unknown.

Pattern detection uses frequency analysis and categorization consistency to
determine whether a pattern is actionable.

## Proposal Generation

When patterns are detected, the Reflector generates evolution proposals. Each
proposal includes:

- **Type**: modify_prompt, add_node, remove_node, reorder, add_skill, add_rule.
- **Details**: Specifics about what to change (node ID, prompt file, content).
- **Reason**: Human-readable explanation.
- **Confidence score**: 0.0 to 1.0, computed from two factors:
  - Data factor: min(1.0, data_points / 10) -- more data means higher confidence.
  - Consistency factor: 1.0 if all failures share the same category, 0.7 if
    mixed, 0.5 if insufficient data.
- **Failure category**: The dominant failure type driving this proposal.

The philosophy module also contributes proposals when appropriate. The Dao De
Jing principle of simplification triggers when failure counts are high,
suggesting that complex nodes should be split into simpler sub-tasks.

## Validation

Before any proposal is applied, the EvolutionEngine validates it against
constitutional constraints:

- **Immutable files**: kernel/BOOT.md, kernel/constitution.md, and runner.py can
  never be modified. This preserves the kernel's bootstrap mechanism and core
  execution logic.
- **Valid change types**: Only the six defined types are permitted.
- **Path traversal**: Prompt file modifications cannot escape the kernel/ directory.
- **User-owned files**: Files marked as user-owned (externally modified) are
  protected from evolution.
- **Confidence threshold**: Only proposals with confidence > 0.7 are auto-applied.

If validation fails, the proposal is logged as "rejected" with a reason.

## Application

Validated proposals are applied with safeguards:

- **Max applies per cycle**: Only 1 proposal per feedback cycle is applied by
  default. This limits cascading changes and makes it easy to identify which
  change caused an improvement or regression.
- **Original content backup**: For prompt modifications, the original content is
  saved in the change record to enable rollback.
- **Node backup**: For node removals, the full node definition is preserved.
- **History logging**: Every change (applied, rejected, or failed) is logged to
  `kernel/evolution/history.jsonl` with a unique UUID.

## Metrics Tracking

The EvolutionMetrics system tracks per-node performance using a sliding window
(default size: 10 iterations per node):

- **Success rate**: Percentage of recent iterations that succeeded.
- **Average retries**: How many retries are typically needed.
- **Average duration**: Time taken per iteration.
- **Overall health**: Weighted average of all node success rates.

The sliding window ensures that metrics reflect recent performance, not
historical artifacts. Old data naturally falls off as new iterations are recorded.

The `compare_periods()` method splits the window in half to detect whether
recent changes improved or degraded performance.

## Automatic Revert

The `revert_if_worse()` mechanism provides a safety net:

1. Before applying a change, snapshot the current metrics for the affected node.
2. After the change has been active for several iterations, compare new metrics.
3. If the success rate dropped by more than the threshold (default: 10%), the
   change is automatically rolled back.
4. A rollback record is logged to history.jsonl referencing the original change ID.

This creates a "try and revert" pattern where the kernel can experiment safely.

## Historian: Auto-Pruning and Effectiveness Analysis

The EvolutionHistorian manages long-term history:

- **Auto-pruning**: When history.jsonl exceeds 500 entries, older entries are
  moved to `kernel/evolution/archive/archive_YYYYMMDD_HHMMSS.jsonl`. Only the
  most recent 500 entries are kept in the active file.
- **Effectiveness analysis**: Tracks which change types tend to "stick" vs get
  reverted. This feeds back into proposal confidence scoring -- if a particular
  type of change has a low stick rate (< 30%), its confidence is penalized by 0.3.
- **Evolution velocity**: Measures changes applied per window of iterations,
  indicating how actively the kernel is evolving.
- **Summary statistics**: Total changes, applied/rejected/failed counts, most
  modified nodes, and change type distribution.

## Core Moat: SkillAccumulator and ProjectHistory

The kernel's competitive advantage grows over time through two mechanisms:

- **SkillAccumulator** (kernel/skill_accumulator.py): After each completed project,
  extracts patterns that made it successful, creates new skills or updates
  existing ones, and tracks effectiveness scores. Skills that repeatedly
  contribute to success get higher scores and are preferentially selected.
- **ProjectHistory** (kernel/project_history.py): Maintains a record of completed
  projects in `memory/projects_completed.jsonl`. The `get_similar_past_projects()`
  method finds relevant historical projects by keyword matching, allowing the
  kernel to leverage past experience when tackling similar goals.

Together, these components create a flywheel effect: more projects completed
means more skills accumulated, which means better performance on future projects,
which means more successful completions.

## Configuration

Key parameters that control evolution behavior:

- **Confidence threshold**: 0.7 (proposals below this are not auto-applied)
- **Max applies per cycle**: 1 (limits cascading changes)
- **Metrics window size**: 10 (sliding window for per-node tracking)
- **History prune threshold**: 500 entries (older entries archived)
- **Revert threshold**: 0.1 (10% success rate drop triggers rollback)
- **Stuck detection**: Per-node max_retries defined in graph.yaml
- **Error trim**: Maximum 10 errors in active state
- **Progress history cap**: 20 entries for convergence detection
