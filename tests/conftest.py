"""Pytest configuration and shared fixtures."""

import os
import shutil
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def kernel_root() -> Path:
    """Return the root directory of the kernel project."""
    return Path(__file__).parent.parent


@pytest.fixture
def state_yaml(kernel_root: Path) -> Path:
    """Return the path to state.yaml."""
    return kernel_root / "kernel" / "state.yaml"


@pytest.fixture
def graph_yaml(kernel_root: Path) -> Path:
    """Return the path to graph.yaml."""
    return kernel_root / "kernel" / "graph.yaml"


@pytest.fixture
def tmp_knowledge(tmp_path: Path) -> Path:
    """Create a temporary knowledge directory structure."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "rules").mkdir()
    (knowledge_dir / "rules" / "manual").mkdir()
    (knowledge_dir / "rules" / "learned").mkdir()
    (knowledge_dir / "patterns").mkdir()

    # Skills directory is now a sibling of knowledge/ at project root level
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create empty indexes
    for subdir in ["rules", "patterns"]:
        index_path = knowledge_dir / subdir / "_index.yaml"
        with open(index_path, "w") as f:
            yaml.safe_dump({"items": []}, f)

    # Skills index lives in the skills/ directory
    skills_index_path = skills_dir / "_index.yaml"
    with open(skills_index_path, "w") as f:
        yaml.safe_dump({"items": []}, f)

    return knowledge_dir


@pytest.fixture
def tmp_memory(tmp_path: Path) -> Path:
    """Create a temporary memory directory."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    # Create required files
    (memory_dir / "decisions.jsonl").touch()
    (memory_dir / "reflections.jsonl").touch()
    (memory_dir / "current_goal.md").touch()
    (memory_dir / "plan.md").touch()
    progress = {"iteration": 0, "tasks_total": 0, "tasks_done": 0, "status": "pending"}
    with open(memory_dir / "progress.yaml", "w") as f:
        yaml.safe_dump(progress, f)
    return memory_dir


@pytest.fixture
def tmp_state(tmp_path: Path) -> Path:
    """Create a temporary state.yaml."""
    state_file = tmp_path / "state.yaml"
    state_data = {
        "current_node": "init",
        "iteration_count": 0,
        "max_iterations": 30,
        "goal": "",
        "status": "idle",
        "last_updated": "",
        "errors": [],
        "context": {
            "skills_loaded": [],
            "current_task": "",
            "phase": "startup",
        },
    }
    with open(state_file, "w") as f:
        yaml.safe_dump(state_data, f)
    return state_file


@pytest.fixture
def tmp_graph(tmp_path: Path) -> Path:
    """Create a temporary graph.yaml."""
    graph_file = tmp_path / "graph.yaml"
    graph_data = {
        "version": "1.0",
        "description": "Test graph",
        "nodes": [
            {
                "id": "init",
                "prompt_file": "prompts/orchestrator.md",
                "description": "Initialize",
                "transitions": [{"to": "plan", "condition": "goal_loaded"}],
                "max_retries": 1,
            },
            {
                "id": "plan",
                "prompt_file": "prompts/planner.md",
                "description": "Plan tasks",
                "transitions": [
                    {"to": "code", "condition": "plan_ready"},
                    {"to": "plan", "condition": "plan_needs_revision"},
                ],
                "max_retries": 2,
            },
            {
                "id": "code",
                "prompt_file": "prompts/coder.md",
                "description": "Write code",
                "transitions": [{"to": "init", "condition": "done"}],
                "max_retries": 3,
            },
        ],
        "default_start": "init",
        "max_iterations": 30,
    }
    with open(graph_file, "w") as f:
        yaml.safe_dump(graph_data, f)
    return graph_file
