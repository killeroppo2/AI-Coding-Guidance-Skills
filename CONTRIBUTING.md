# Contributing to AI Coding Guidance Skills

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Development Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/<your-fork>/AI-Coding-Guidance-Skills.git
   cd AI-Coding-Guidance-Skills
   ```

2. Install the package in development mode with all dev dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

3. Initialize runtime files:

   ```bash
   python runner.py --init
   ```

## Running Tests

Run the full test suite with coverage:

```bash
make test
```

This runs `pytest` with a 90% coverage threshold. All tests must pass and coverage must stay above 90% before submitting changes.

## Linting

Check for linting issues:

```bash
make lint
```

Auto-format code:

```bash
make format
```

Run type checking:

```bash
make typecheck
```

## Code Style

- **Linter/Formatter:** [Ruff](https://docs.astral.sh/ruff/) is enforced for all Python code.
- **Type hints:** Required on all function signatures.
- **Docstrings:** Required on all public functions and classes.
- **Line length:** 100 characters maximum.
- **Imports:** Sorted by `isort` rules via Ruff.

## Adding a New Skill

Skills live in the `skills/` directory. Each skill is a directory containing at least a `SKILL.md` file that describes the skill's purpose and behavior.

To create a new skill:

1. Reference the `write-a-skill` skill in `skills/` for a detailed walkthrough.
2. Create a new directory under `skills/` with your skill name (use kebab-case).
3. Add a `SKILL.md` file describing the skill.
4. Register the skill in `skills/_index.yaml`.

## Submitting Changes

1. Fork the repository.
2. Create a feature branch from `main`:

   ```bash
   git checkout -b feat/my-new-feature
   ```

3. Make your changes, ensuring tests pass and lint is clean.
4. Push to your fork and open a Pull Request against `main`.

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Each commit message should follow this format:

```
<type>: <short description>
```

### Types

| Type       | Description                                      |
|------------|--------------------------------------------------|
| `feat`     | A new feature                                    |
| `fix`      | A bug fix                                        |
| `chore`    | Maintenance tasks, dependency updates            |
| `docs`     | Documentation-only changes                       |
| `refactor` | Code changes that neither fix a bug nor add a feature |

### Examples

```
feat: add skill validation on init
fix: resolve YAML parsing error for empty files
docs: update README with new CLI options
chore: bump ruff to 0.5.0
refactor: extract orchestrator loop into separate module
```
