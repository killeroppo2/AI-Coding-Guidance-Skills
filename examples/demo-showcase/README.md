# Demo Showcase: URL Shortener CLI

This example demonstrates the kernel's graph-based workflow traversal using
a "URL shortener CLI with SQLite backend" as the development goal.

## What This Demo Shows

The kernel operates as a **directed graph executor**. In dry-run mode, it
traverses the workflow graph without calling an LLM, showing exactly which
nodes would be visited and what prompts would be assembled at each step.

This is useful for:
- Understanding the kernel's execution flow
- Verifying graph structure and transitions
- Seeing how prompts are loaded for each phase
- Confirming skill auto-selection for a given goal

## How Skill Auto-Selection Works

When you provide a goal like "Build a URL shortener CLI with SQLite backend",
the kernel's `skill_selector.py` tokenizes the goal into lowercase words and
matches them against skill metadata (tags and descriptions). Tags receive a
3x weight multiplier compared to description word matches. The top-scoring
skills (up to 5) are loaded into context for that run.

## Graph Nodes

Each node in the workflow graph represents a development phase:

| Node | Description | What Happens |
|------|-------------|--------------|
| `init` | Initialize context | Loads goal, assesses current state, prepares workspace |
| `plan` | Create execution plan | Breaks goal into tasks, determines order of work |
| `code` | Implement next task | Writes code for the next pending task from the plan |
| `test` | Run tests | Executes tests, checks coverage thresholds |
| `review` | Code review | Reviews code quality, patterns, and correctness |

In dry-run mode, the kernel follows the first available transition from each
node, creating the cycle: `init -> plan -> code -> test -> review -> plan -> ...`
until max iterations is reached.

## How to Run

```bash
# From the project root:
bash examples/demo-showcase/run.sh

# Or manually:
python runner.py --goal "Build a URL shortener CLI with SQLite backend" \
    --dry-run --verbose --max-iterations 15
```

## Expected Output

See `expected-output/dry-run.txt` for the full output of a successful run.

The output shows each iteration with:
- The current node name
- Node description
- Path to the prompt file that would be used
- Character length of the prompt
- Which node would be visited next
