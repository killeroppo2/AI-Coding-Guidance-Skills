```markdown
# AI-Coding-Guidance-Skills Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core conventions and workflows for contributing to the **AI-Coding-Guidance-Skills** repository. The project is written in Python and focuses on modular, trackable development with strong task management, semantic review, and test coverage practices. You'll learn how to structure code, manage features, handle reviews, and expand test coverage using standardized patterns and commands.

## Coding Conventions

- **File Naming:**  
  Use kebab-case for file names.  
  _Example:_  
  ```
  knowledge-skills.py
  task-manager.py
  ```

- **Import Style:**  
  Use relative imports within modules.  
  _Example:_  
  ```python
  from .utils import parse_feature_file
  from ..kernel.module import KernelModule
  ```

- **Export Style:**  
  Use named exports; explicitly specify what is exported from a module.  
  _Example:_  
  ```python
  __all__ = ["TaskManager", "FeatureTracker"]
  ```

- **Commit Messages:**  
  Follow the [Conventional Commits](https://www.conventionalcommits.org/) format with these prefixes:
    - `chore`: Maintenance tasks (e.g., `chore: update dependencies`)
    - `feat`: New features (e.g., `feat: add semantic review workflow`)
    - `fix`: Bug fixes (e.g., `fix: correct path normalization in runner`)
  Keep commit messages concise (average ~61 characters).

## Workflows

### Feature Development with Task Tracking
**Trigger:** When you want to add a new feature or major capability and track its progress.  
**Command:** `/new-feature`

1. Create or update implementation files (e.g., kernel modules, knowledge skills, scripts).
2. Add or update the corresponding feature file in `.agents/tasks/task-self-evolving-kernel/features/FEAT-XXX.json`.
3. Update or create tests to cover the new feature in `tests/`.
4. Mark the feature as completed by updating the `FEAT-XXX.json` file (status or metadata).

_Example:_
```python
# kernel/new-feature.py
class NewFeature:
    def run(self):
        pass

# tests/test-new-feature.py
from ..kernel.new-feature import NewFeature

def test_run():
    assert NewFeature().run() is None
```

### Test Suite Expansion and Coverage Increase
**Trigger:** When you want to improve or ensure high test coverage across modules.  
**Command:** `/increase-coverage`

1. Identify coverage gaps or missing test cases.
2. Add new test files or update existing ones in `tests/`.
3. Optionally update related feature tracking files for coverage goals.
4. Commit with coverage statistics and summary.

_Example:_
```python
# tests/test-edge-case.py
from ..kernel.edge_case import handle_edge_case

def test_handle_edge_case():
    assert handle_edge_case("input") == "expected_output"
```

### Semantic Review and Fix Cycle
**Trigger:** When you want to resolve review feedback or audit findings.  
**Command:** `/review-fix`

1. Receive or perform a semantic/code review (results saved in `.agents/tasks/task-self-evolving-kernel/YYYY-MM-DD-*.md`).
2. Apply fixes to implementation files (e.g., bug fixes, security checks, doc updates).
3. Add or update tests to verify the fix.
4. Update task state or review result files to reflect fixes.

_Example:_
```python
# kernel/secure-module.py
def sanitize_input(input_str):
    # Improved sanitization
    return input_str.strip()

# tests/test-secure-module.py
def test_sanitize_input():
    assert sanitize_input("  data ") == "data"
```

### Feature Status Marking
**Trigger:** When you want to officially mark a feature as done for tracking purposes.  
**Command:** `/mark-feature-complete`

1. Update `.agents/tasks/task-self-evolving-kernel/features/FEAT-XXX.json` to reflect completion.
2. Optionally update `.agents/tasks/task-self-evolving-kernel/task.json` or add review result files.

_Example:_
```json
// .agents/tasks/task-self-evolving-kernel/features/FEAT-123.json
{
  "feature": "new semantic review",
  "status": "completed",
  "completed_at": "2024-06-01"
}
```

## Testing Patterns

- **Test File Naming:**  
  Test files are named with the `.test.ts` pattern (for TypeScript), but Python test files are typically in `tests/` and follow the `test_*.py` convention.

- **Test Structure:**  
  Tests are written as functions, importing the module under test using relative imports.

- **Framework:**  
  The specific test framework is not detected, but `pytest`-style tests are recommended.

_Example:_
```python
# tests/test-feature.py
from ..kernel.feature import Feature

def test_feature_behavior():
    assert Feature().do_work() == "expected"
```

## Commands

| Command                  | Purpose                                                      |
|--------------------------|--------------------------------------------------------------|
| /new-feature             | Start a new feature with tracking and implementation steps   |
| /increase-coverage       | Add or update tests to improve code coverage                 |
| /review-fix              | Address review feedback and document fixes                   |
| /mark-feature-complete   | Mark a tracked feature as completed in the task system       |
```
