# QUICKSTART - Self-Evolving AI Development Kernel

A self-evolving development kernel that guides AI agents through structured
workflows using a graph-based execution model, inspired by the Dao De Jing
and the Art of War.

## Philosophy

- **Dao De Jing**: Simplicity, non-forcing, natural flow. The kernel does not
  fight complexity; it dissolves it through structure.
- **Art of War**: Strategic planning, adaptation, knowing when to advance and
  when to reflect. The kernel evolves its own prompts and graph.

## Prerequisites

- Python 3.12+
- pyyaml (`pip install pyyaml`)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd AI-Coding-Guidance-Skills

# Install with pip (editable mode for development)
pip install -e ".[dev]"

# Verify your setup
python3.12 runner.py --check
```

## Three Execution Modes

### Mode 1: Dry-run traversal

Walks through the graph mechanically without calling an AI. Useful for
verifying graph structure and prompt loading.

```bash
python3.12 runner.py --goal "Build a REST API" --dry-run
```

### Mode 2: AI reads BOOT.md directly

For AI agents that can read files. Point the AI at `kernel/BOOT.md` and
let it self-direct through the boot sequence. The AI manages state itself.

### Mode 3: Real AI execution via subprocess

The runner assembles context and pipes it to an AI CLI tool.

```bash
python3.12 runner.py --goal "Build a REST API" --ai-command "claude --print"
```

## Quick Start

0. Verify setup: `python3.12 runner.py --check`
1. Clone this repository
2. Install dependencies: `pip install pyyaml`
3. Try a dry run: `python3.12 runner.py --goal "Hello world app" --dry-run`
4. Generate a consolidated prompt: `python3.12 runner.py --goal "Build X" --generate-prompt`
5. Pipe to your AI: `python3.12 runner.py --goal "Build X" --generate-prompt | claude --print`

## Key Commands

```bash
# Dry run with custom iteration limit
python3.12 runner.py --goal "..." --dry-run --max-iterations 10

# Generate consolidated prompt (all kernel context in one output)
python3.12 runner.py --goal "..." --generate-prompt

# Real execution with timeout per iteration
python3.12 runner.py --goal "..." --ai-command "claude --print" --timeout 600

# Resume a previous session
python3.12 runner.py --goal "..." --resume --ai-command "claude --print"
```

## Project Structure

- `kernel/BOOT.md` - Boot sequence for AI agents
- `kernel/constitution.md` - Immutable safety rules
- `kernel/graph.yaml` - Workflow graph (nodes and transitions)
- `kernel/state.yaml` - Current execution state
- `kernel/prompts/` - Role-specific prompts for each node
- `kernel/philosophy/` - Guiding principles (dao.md, strategy.md)
- `knowledge/` - Skills, rules, and patterns
- `memory/` - Persistent state across iterations
- `runner.py` - Main entry point
