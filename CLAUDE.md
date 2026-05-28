# CLAUDE.md - System Rules for claude --print mode

You are operating inside a **self-evolving kernel**. Your output is parsed programmatically by `runner.py`. Do not treat this as a conversation. Treat it as a structured protocol.

## MANDATORY OUTPUT FORMAT

Every response MUST end with these two lines as plain text (NOT inside a code block):

STATUS: success
TRANSITION: <condition>

Or on failure:

STATUS: failure
TRANSITION: <condition>

If you omit these lines, runner.py will reject your output and retry. This wastes iteration budget. Do not forget them.

## Valid TRANSITION values by node

| Node    | Valid TRANSITION values                     |
|---------|---------------------------------------------|
| init    | goal_loaded                                 |
| plan    | plan_ready, plan_needs_revision             |
| code    | code_written, code_needs_retry              |
| test    | tests_pass, tests_fail                      |
| review  | review_pass, review_needs_changes           |
| reflect | evolution_proposed, no_evolution_needed      |
| evolve  | evolution_applied                           |

## Optional: FILES_WRITTEN

If you created or modified files, include:

FILES_WRITTEN: path/to/file1.py, path/to/file2.py

## Rules

1. STATUS must be exactly `success` or `failure`
2. TRANSITION must be a valid value for the current node
3. These lines must appear at the END of your response, as raw text
4. Do not wrap them in markdown code fences
5. Do not omit them under any circumstance

## Permission Auto-Review

The `.claude/settings.json` file defines which operations Claude Code can perform automatically without manual approval.

### Allowed Operations

- **Read**: Reading any file in the workspace
- **Write(workspace/**)**: Writing files in the workspace directory
- **Write(memory/**)**: Writing to memory storage (yaml, md, jsonl)
- **Write(knowledge/**)**: Writing to the knowledge base
- **Bash(python3.12 -m pytest*)**: Running tests
- **Bash(python3.12 runner.py*)**: Running the kernel
- **Bash(ls)**, **Bash(ls *)**: Directory listing (current directory only)
- **Bash(mkdir workspace/*, memory/*, knowledge/*, tests/*)**: Creating directories within project scope
- **Bash(cat kernel/*)**, **Bash(cat tests/*)**, etc.: Reading project files (scoped to project directories and known extensions: .md, .py, .yaml, .json, .toml)

### Denied Operations

- **Write(kernel/constitution.md)**: Cannot modify the kernel constitution
- **Write(kernel/BOOT.md)**: Cannot modify the boot protocol
- **Write(runner.py)**: Cannot modify the runner entry point
- **Bash(rm -rf*)**, **Bash(rm -r *)**: Cannot perform destructive deletions
- **Bash(git push*)**: Cannot push to remote repositories
- **Bash(curl*, wget*)**: Cannot make network requests

### How It Works

If Claude requests a command not in the allow list, it will be blocked and require manual approval. This protects core kernel files and prevents dangerous operations while allowing productive development work.

To modify these permissions, edit `.claude/settings.json`.
