# System Architecture

## Overview and Philosophy

The AI Coding Guidance Kernel is a self-evolving development system inspired by
two philosophical traditions: the Dao De Jing's principle of simplicity
(doing less to achieve more), and the Art of War's strategic adaptability
(knowing when to advance, retreat, and evolve). The kernel operates as an
autonomous loop that plans, codes, tests, reviews, reflects, and evolves --
continuously improving its own workflow based on empirical results.

The system is designed for stateless AI agent execution. All state lives on the
filesystem (YAML for structured data, JSONL for append-only logs), allowing any
AI agent to pick up where another left off by simply reading the current state.

## Component Diagram

```
                         +---------------+
                         |   runner.py   |
                         | (entry point) |
                         +-------+-------+
                                 |
                    +------------+------------+
                    |                         |
            +-------+-------+       +--------+--------+
            | GraphExecutor |       | ContextAssembler|
            | (graph.yaml)  |       | (builds prompt) |
            +-------+-------+       +--------+--------+
                    |                         |
         +----------+----------+             |
         |          |          |             |
    +----+---+ +---+----+ +---+----+        |
    |  init  | |  plan  | |  code  |   +----+----+
    |  node  | |  node  | |  node  |   |   AI    |
    +--------+ +--------+ +--------+   | Command |
    | test   | | review | | reflect|   +---------+
    |  node  | |  node  | |  node  |
    +--------+ +--------+ +--------+
                    |
            +-------+-------+
            | FeedbackLoop  |
            +-------+-------+
                    |
         +----------+----------+
         |                     |
    +----+-----+        +------+------+
    | Reflector|        |  Evolution  |
    | (analyze)|        |  Engine     |
    +----------+        +------+------+
                               |
                    +----------+----------+
                    |          |          |
              +-----+--+ +----+---+ +----+----+
              |Historian| |Metrics | |  Graph  |
              |(prune)  | |(track) | | Advisor |
              +---------+ +--------+ +---------+
```

## State Management

The `StateManager` (memory/state_manager.py) is the single source of truth for
execution state. It persists:

- **state.yaml**: Current node, iteration count, goal, workspace path, errors,
  node visit counts, progress history, execution mode.
- **decisions.jsonl**: Append-only log of all decisions made during execution.
- **reflections.jsonl**: Append-only log of iteration analysis results.
- **progress.yaml**: Task completion tracking (total vs done).

State transitions are deterministic: the GraphExecutor reads graph.yaml and
determines valid transitions from each node. In dry-run mode (Mode 1), the
runner always takes the first available transition. In AI mode (Mode 3), the
AI subprocess outputs a `TRANSITION:` line that the runner matches against
available transitions.

Bounded growth is enforced: errors are trimmed to 10 entries (archived to
error_history.jsonl), progress_history is capped at 20 entries, and evolution
history is auto-pruned at 500 entries by the Historian.

## Evolution Pipeline

The evolution pipeline runs after every iteration in Mode 3:

1. **FeedbackLoop.run_cycle()** receives iteration data (node, result, errors).
2. **Reflector.analyze_iteration()** produces a reflection with learnings/issues.
3. The reflection is appended to reflections.jsonl.
4. **Reflector.propose_evolution()** reads recent reflections for pattern detection.
5. Proposals are scored by confidence (data factor x consistency factor).
6. **EvolutionEngine.apply_if_confident()** applies proposals above threshold (0.7).
7. **EvolutionMetrics** records success/failure per node in a sliding window.
8. **EvolutionHistorian** auto-prunes history beyond 500 entries.
9. **revert_if_worse()** rolls back changes if metrics degrade beyond threshold.

Constitutional constraints (kernel/constitution.md) ensure that BOOT.md,
constitution.md, and runner.py can never be modified by the evolution engine.

## Skill System

The skill system provides reusable knowledge:

- **KnowledgeStore** (knowledge/store.py): Manages rules, patterns, and skills.
- **SkillSelector** (kernel/skill_selector.py): Auto-selects relevant skills
  based on goal text keyword matching.
- **SkillFactory** (kernel/skill_factory.py): Creates new skills from learned
  patterns during evolution.
- **SkillAccumulator** (kernel/skill_accumulator.py): Core moat component that
  learns from completed projects, extracting reusable patterns and updating
  skill effectiveness scores.

Skills are stored as YAML files in skills/ with metadata in _index.yaml.
Each skill has tags, a description, and content that gets injected into
the context prompt when selected.

## Memory System

All memory is filesystem-based for stateless agent compatibility:

- **decisions.jsonl**: Every decision with timestamp and rationale.
- **reflections.jsonl**: Per-iteration analysis (success, learnings, issues).
- **progress.yaml**: Current task completion state.
- **projects_completed.jsonl**: Historical project records for the core moat.
- **error_history.jsonl**: Archived errors (trimmed from active state).
- **evolution/history.jsonl**: All evolution changes with apply/reject status.
- **evolution/archive/**: Pruned history entries for long-term reference.

## Web Dashboard

The web dashboard (web/app.py) provides real-time monitoring via FastAPI:

- **SSE** (Server-Sent Events) at GET /api/logs for streaming log output.
- **WebSocket** at /ws for bidirectional real-time state updates.
- **REST API** for state queries, goal setting, and execution control.
- **Chart.js** visualizations for success rates, iteration distribution,
  and evolution velocity.
- **Security**: CORS middleware, rate limiting (60 req/min per IP),
  input sanitization, and workspace boundary validation.
