# AI-Coding-Guidance-Skills

> A self-evolving AI development kernel that orchestrates coding workflows, learns from experience, and adapts its own behavior.

![Tests](https://img.shields.io/badge/tests-passing-green)
![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)

## What Is This?

This is a kernel that runs AI-driven development workflows through a directed graph of nodes. It selects skills from an extensible inventory, assembles rich context for each phase, executes via AI commands, reflects on results, and evolves its own prompts and structure over time. The kernel bridges Eastern philosophy (Dao De Jing, Art of War) with software engineering to guide strategic decision-making, knowing when to push forward, when to retreat, and when to let things emerge naturally.

## Architecture

The kernel operates as a state machine traversing this graph:

```
[init] --> [plan] --> [code] --> [test] --> [review] --> [reflect] --> [evolve]
   ^                    ^                      |             |            |
   |                    |                      |             |            |
   |                    +---- (tests fail) ----+             |            |
   |                    |                                    |            |
   |                    +---- (needs changes) ---------------+            |
   |                                                                     |
   +--- (no evolution needed) --- [reflect]                              |
   |                                                                     |
   +----------------------- (evolution applied) -------------------------+
```

Each node loads a specialized prompt, assembles context from skills and memory, invokes the AI, and transitions based on output signals.

## Quick Start

```bash
# 1. Clone and enter
git clone <repo-url> && cd AI-Coding-Guidance-Skills

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Initialize runtime files
python3.12 runner.py --init

# 4. Dry run to verify graph structure
python3.12 runner.py --goal "Build a REST API" --dry-run

# 5. Real execution with AI
python3.12 runner.py --goal "Build a REST API" --ai-command "claude --print"
```

## Three Execution Modes

| Mode | Command | Use Case |
|------|---------|----------|
| Dry Run | `runner.py --goal "..." --dry-run` | Verify graph structure without modifying state |
| BOOT.md | AI reads `BOOT.md` directly | Agent manages its own state transitions |
| Autonomous | `runner.py --goal "..." --ai-command "claude --print"` | Full autonomous loop with AI subprocess |

## Features

- Self-evolving prompts and graph structure via reflection and evolution nodes
- Skill auto-selection based on goal analysis and phase matching
- Philosophy-guided decisions (strategic retreat, terrain awareness, natural flow)
- Composable skill system with 26+ skills across 5 phases
- Token-budget-aware context assembly with workspace and decision history
- Concurrency-safe file operations with advisory locking
- Append-only JSONL evolution history with auto-pruning
- Configurable retry strategies (continue, skip, backoff)
- Resume from saved state for interrupted sessions
- Ralph mode for autonomous coding with PRD export

## Skill Inventory

| Skill | Phase | Description |
|-------|-------|-------------|
| grill-me | idea | Challenge and clarify ideas through rigorous questioning |
| grill-with-docs | idea | Challenge ideas using documentation and ADR format |
| prd | requirements | Generate Product Requirements Documents with structured output |
| to-prd | requirements | Convert ideas into Product Requirements Documents |
| to-issues | requirements | Convert PRDs/plans into actionable issues |
| ralph | execution | Autonomous coding agent that implements user stories |
| tdd | execution | Test-driven development with deep modules and interface design |
| prototype | execution | Rapid prototyping with logic and UI templates |
| diagnose | quality | Debug and diagnose issues with HITL loop |
| improve-codebase-architecture | quality | Refactoring and architecture improvement |
| ui-ux-pro-max | design | UI/UX design with 50+ styles, 161 palettes, 57 font pairings |
| ui-styling | design | Tailwind CSS and shadcn/ui component styling |
| design-system | design | Design tokens, component specs, and slide generation |
| design | design | Comprehensive design - logos, CIP, icons, slides |
| brand | design | Brand identity management - guidelines, voice, visual identity |
| banner-design | design | Banner creation with size and style references |
| slides | design | HTML presentation creation with layout patterns |
| handoff | lifecycle | Session end handover documentation |
| triage | lifecycle | Triage and prioritize issues and tasks |
| zoom-out | lifecycle | Take a high-level view of the project state |
| web-scraper | data | Web scraping with extraction patterns and transforms |
| xhs_collector | data | XiaoHongShu content collection with scheduling |
| write-a-skill | meta | Meta-skill for creating new skills |
| caveman | style | Simplified communication style |
| ai-product | strategy | AI product development guidance |
| ai-code-guidance | guidance | AI coding guidance and best practices |

## How It Works

1. **Goal Setting** - Provide a development goal via `--goal`. The kernel initializes context and loads relevant state.
2. **Skill Auto-Selection** - The skill selector analyzes the goal, matches it against skill tags, and loads the best-fit skills for the current phase.
3. **Graph Traversal** - The executor walks the graph from `init` through `plan`, `code`, `test`, `review`, `reflect`, and optionally `evolve`, following transition conditions emitted by AI output.
4. **Context Assembly** - Each node assembles a prompt combining the node template, selected skill content, memory state, progress history, and workspace context within a token budget.
5. **AI Execution** - The assembled prompt is piped to the AI command (Mode 3) or presented for manual execution (Mode 2). Output is parsed for transition signals.
6. **Reflection and Evolution** - The reflector analyzes iteration outcomes, extracts learnings, and proposes structural changes. The evolution engine applies approved mutations to prompts, graph structure, or skill configurations.

## Philosophy

The kernel draws on two philosophical traditions to guide its behavior:

- **Dao De Jing** - Simplicity over complexity. Know when to stop. Let solutions emerge naturally rather than forcing them. The kernel avoids over-engineering and respects the natural rhythm of development.
- **Art of War** - Strategic retreat when stuck (stuck_handler nodes). Terrain awareness (context assembly maps the current state). Adaptability through evolution. The kernel treats each iteration as a campaign, not a battle.

## CLI Reference

| Flag | Description |
|------|-------------|
| `--goal` | The development goal to work toward |
| `--init` | Initialize runtime files and exit |
| `--dry-run` | Print what would be done without modifying state |
| `--ai-command` | AI CLI command for autonomous execution (e.g., `"claude --print"`) |
| `--check` | Run setup checks and exit |
| `--status` | Print current status and exit |
| `--resume` | Continue from saved state instead of starting fresh |
| `--max-iterations` | Maximum iterations (default: 30) |
| `--skills` | Comma-separated skill names to load (overrides auto-selection) |
| `--execution-mode` | `kernel` (default) or `ralph` (exports prd.json after planning) |
| `--retry-strategy` | `continue`, `skip`, or `backoff` on failure |
| `--timeout` | Timeout per iteration in seconds (default: 300) |
| `--verbose` | Show iteration-by-iteration progress |
| `--generate-prompt` | Output assembled prompt to stdout and exit |
| `--workspace` | Manual workspace project name override |

## Contributing

### Adding a New Skill

1. Create a directory under `skills/` with a `SKILL.md` file describing the skill behavior and prompts.
2. Register it in `skills/_index.yaml` with name, path, description, tags, and composable_with fields.
3. Use the `write-a-skill` meta-skill to scaffold the structure: run with `--skills write-a-skill`.

### Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ --cov --cov-fail-under=90 -q
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
