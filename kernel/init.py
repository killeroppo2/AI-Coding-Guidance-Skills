"""Initialization module for creating runtime files."""

from pathlib import Path


def init_runtime_files(kernel_root: Path) -> None:
    """Create all necessary runtime files if they don't already exist.

    Args:
        kernel_root: The root directory of the kernel project.
    """
    state_yaml_content = (
        "current_node: init\n"
        "iteration_count: 0\n"
        "status: idle\n"
        "goal: \"\"\n"
        "errors: []\n"
        "node_visits: {}\n"
    )

    files = {
        kernel_root / "kernel" / "state.yaml": state_yaml_content,
        kernel_root / "memory" / "current_goal.md": "",
        kernel_root / "memory" / "plan.md": "",
        kernel_root / "memory" / "progress.yaml": "{}\n",
        kernel_root / "memory" / "assessment.yaml": "{}\n",
        kernel_root / "memory" / "tasks.yaml": "tasks: []\n",
        kernel_root / "memory" / "decisions.jsonl": "",
        kernel_root / "memory" / "reflections.jsonl": "",
        kernel_root / "kernel" / "evolution" / "history.jsonl": "",
    }

    created = 0
    skipped = 0

    for path, content in files.items():
        if path.exists():
            print(f"  [skip] {path.relative_to(kernel_root)} (already exists)")
            skipped += 1
        else:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                print(f"  [created] {path.relative_to(kernel_root)}")
                created += 1
            except PermissionError:
                print(
                    f"  [error] {path.relative_to(kernel_root)}"
                    " (permission denied - check directory permissions)"
                )
            except OSError as e:
                print(f"  [error] {path.relative_to(kernel_root)} ({e})")

    print(
        f"\nInitialization complete. Created {created} file(s), "
        f"skipped {skipped} file(s)."
    )
