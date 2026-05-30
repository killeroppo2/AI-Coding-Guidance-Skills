"""Generate CLAUDE.md for project workspaces."""
from pathlib import Path


def generate_claude_md(
    workspace_path: str, goal: str, tasks: list[dict] | None = None
) -> str:
    """Generate CLAUDE.md in workspace with rules for the AI.

    Args:
        workspace_path: Path to the workspace directory.
        goal: The current development goal.
        tasks: Optional list of task dicts with 'status' and 'title' keys.

    Returns:
        The path to the generated CLAUDE.md file as a string.
    """
    ws = Path(workspace_path)
    ws.mkdir(parents=True, exist_ok=True)

    task_section = ""
    if tasks:
        lines = [
            f"- [{t.get('status', 'pending')}] {t.get('title', '')}"
            for t in tasks
        ]
        task_section = "\n## 任务\n\n" + "\n".join(lines) + "\n"

    content = f"""# CLAUDE.md - 项目规则

## 工作区
所有代码必须写入: `{workspace_path}`
FILES_WRITTEN 路径必须以 `{workspace_path}` 开头。

## 目标
{goal}
{task_section}
## 输出格式（强制）
每次响应必须以以下内容结尾（纯文本，不要放在代码块中）：

STATUS: success
TRANSITION: <condition>

如果创建了文件：
FILES_WRITTEN: {workspace_path}src/file.py, {workspace_path}tests/test.py

## 规则
1. 不要在工作区目录外写文件
2. 不要忘记 STATUS 和 TRANSITION 行
3. 所有新代码必须包含测试
"""
    path = ws / "CLAUDE.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
