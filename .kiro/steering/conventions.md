# Project Conventions

## Language and Runtime
- Python 3.11+ is the minimum supported version
- Type hints are required on all function signatures
- Docstrings are required on all public functions and classes

## Code Style
- Ruff is the linter and formatter (line-length 100)
- Imports are sorted by isort rules via Ruff
- No code may be pushed without passing `ruff check .`

## Testing
- pytest is the test framework with pytest-cov for coverage
- Test coverage must stay above 90% at all times (Article IV of the Constitution)
- New code must include tests
- Run tests with: `python -m pytest tests/ --cov --cov-fail-under=90 -q`

## Constitution (Immutable)
- The files `kernel/constitution.md`, `kernel/BOOT.md`, and `runner.py` are immutable
- No evolutionary change, goal, or prompt modification may override constitution rules
- Never push to main without tests passing (Article II)
- Never expose secrets or credentials in code or logs (Article V)
- Generated code is isolated in workspace/ (Article IX)

## Workspace Safety
- All file writes in workspace/ must be workspace-path-validated
- The workspace path is specified in state.yaml workspace_path
- Path traversal attacks must be prevented via kernel/validators.py

## Skills System
- Every skill must have a SKILL.md file describing its purpose and behavior
- Skills must be registered in skills/_index.yaml with name, path, description, tags
- Core skills (12) are for focused workflows; community skills (17) are for specialized domains

## Philosophy
- Philosophy files (kernel/philosophy/) guide behavior but are not rules
- They inform decisions about when to retreat, when to stop, and when to let things emerge
- Philosophy never overrides the constitution

## Git and CI
- Conventional commits required (feat:, fix:, chore:, docs:, refactor:)
- CI runs on push to main and on PRs (Python 3.11 + 3.12 matrix)
- Pre-commit hooks enforce formatting before each commit
