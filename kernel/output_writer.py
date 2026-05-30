"""Extract code blocks from AI output and write them to workspace.

When using --ai-command with tools like 'claude --print', the AI outputs code
in markdown code blocks but does not actually write files to disk. This module
parses the AI output, identifies file paths from contextual hints (bold text,
backtick filenames, comments, headings), and writes the extracted content to
the workspace directory.
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Patterns to detect filename hints before a code block
_FILENAME_PATTERNS = [
    # **src/main.py:** or **src/main.py**
    re.compile(r"\*\*([^\*]+?\.[a-zA-Z0-9]+):?\*\*"),
    # `src/main.py`: or `src/main.py`
    re.compile(r"`([^`]+?\.[a-zA-Z0-9]+)`"),
    # Heading with filename: ### src/main.py or ## filename.py
    re.compile(r"^#{1,4}\s+(.+?\.[a-zA-Z0-9]+)\s*$", re.MULTILINE),
]

# Pattern for # filename: comment inside code block (first line)
_INLINE_FILENAME_PATTERN = re.compile(
    r"^(?:#|//|--|;)\s*(?:filename|file|path):\s*(.+?\.[a-zA-Z0-9]+)\s*$",
    re.IGNORECASE,
)


def _find_filename_hint(text_before_block: str) -> str | None:
    """Search text preceding a code block for a filename hint.

    Args:
        text_before_block: The text content before a fenced code block.

    Returns:
        Extracted filename string, or None if no hint found.
    """
    # Look at the last few lines before the code block
    lines = text_before_block.rstrip().split("\n")
    # Check last 3 lines for filename patterns
    search_region = "\n".join(lines[-3:]) if len(lines) >= 3 else text_before_block

    for pattern in _FILENAME_PATTERNS:
        match = pattern.search(search_region)
        if match:
            candidate = match.group(1).strip().rstrip(":")
            # Validate it looks like a file path
            if "/" in candidate or "." in candidate:
                return candidate
    return None


def _find_inline_filename(first_line: str) -> str | None:
    """Check if the first line of a code block contains a filename comment.

    Args:
        first_line: The first line of code block content.

    Returns:
        Extracted filename string, or None if no inline hint found.
    """
    match = _INLINE_FILENAME_PATTERN.match(first_line.strip())
    if match:
        return match.group(1).strip()
    return None


def extract_and_write_files(ai_output: str, workspace_path: str, security_policy=None) -> list[str]:
    """Parse AI output for code blocks and write them to workspace.

    Scans the AI response text for fenced markdown code blocks (```),
    identifies associated filenames from surrounding context, and writes
    the code content to the appropriate paths within the workspace.

    Args:
        ai_output: The full text output from the AI command.
        workspace_path: The workspace root directory path.

    Returns:
        List of file paths that were successfully written.
    """
    if not ai_output or not workspace_path:
        return []

    workspace = Path(workspace_path)
    written_files: list[str] = []

    # Split on code fences to find blocks
    # Match ```lang\n...content...\n```
    fence_pattern = re.compile(
        r"```[a-zA-Z0-9_]*\s*\n(.*?)```",
        re.DOTALL,
    )

    # Track position for context lookup
    last_end = 0
    for match in fence_pattern.finditer(ai_output):
        block_content = match.group(1)
        text_before = ai_output[last_end:match.start()]
        last_end = match.end()

        # Skip empty blocks
        if not block_content.strip():
            continue

        # Try to find filename
        filename = _find_filename_hint(text_before)

        # If no hint found in preceding text, check first line of block
        if not filename and block_content.strip():
            first_line = block_content.strip().split("\n")[0]
            filename = _find_inline_filename(first_line)
            # If found inline, remove that line from content
            if filename:
                lines = block_content.split("\n")
                # Remove the first non-empty line
                for idx, line in enumerate(lines):
                    if line.strip():
                        lines.pop(idx)
                        break
                block_content = "\n".join(lines)

        if not filename:
            logger.warning(f"[输出提取] 代码块附近未检测到文件名，跳过块 (前50字符): {block_content[:50]!r}")
            continue

        # Normalize filename - strip leading slashes or workspace prefix
        filename = filename.lstrip("/")
        # Remove workspace prefix if AI included it
        if filename.startswith("workspace/"):
            parts = filename.split("/", 2)
            if len(parts) > 2:
                filename = parts[2]
            else:
                filename = parts[-1]

        # Security: prevent path traversal
        if ".." in filename:
            logger.warning(f"[安全] 跳过包含路径遍历的文件: {filename}")
            continue

        # Build full path
        file_path = workspace / filename

        # Security policy check before write
        if security_policy is not None and security_policy.check_path(str(file_path)) == "deny":
            logger.warning(f"[安全] 因安全策略跳过文件写入: {filename}")
            continue

        # Create parent directories
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Write content (strip trailing whitespace from block)
            file_path.write_text(block_content.rstrip() + "\n", encoding="utf-8")
            written_files.append(str(file_path))
            logger.debug(f"[写入] {filename}")
        except OSError as e:
            logger.warning(f"[写入失败] {filename}: {e}")

    return written_files
