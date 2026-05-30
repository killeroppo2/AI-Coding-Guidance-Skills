"""User-friendly error messages with recovery suggestions.

Maps error types to human-readable messages with what/why/fix structure.
"""

import re

# Error message templates with what/why/fix structure
ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "stuck_node": {
        "what": "系统在节点 '{node}' 上卡住了",
        "why": "该节点已访问 {visits} 次但没有进展（最大重试: {max_retries}）",
        "fix": (
            "建议: 简化目标、添加相关技能，"
            "或通过 --max-iterations 增加最大重试次数"
        ),
    },
    "command_not_found": {
        "what": "AI 命令 '{cmd}' 未找到",
        "why": "该命令未安装或不在 PATH 中",
        "fix": "请安装: pip install {cmd}（或检查 shell 的 PATH 配置）",
    },
    "timeout": {
        "what": "在节点 '{node}' 上迭代超时（{seconds}秒）",
        "why": "AI 子进程响应时间过长",
        "fix": (
            "建议: 增加 --timeout 值、简化当前任务，"
            "或检查 AI 服务是否正常响应"
        ),
    },
    "skill_not_found": {
        "what": "技能 '{name}' 在知识库中未找到",
        "why": "该技能被引用但未安装到 skills/ 目录",
        "fix": "运行: python3.12 setup_check.py --check 验证技能安装",
    },
    "contract_violation": {
        "what": "AI 输出在节点 '{node}' 上不符合预期格式",
        "why": "AI 响应中缺少或无效的 TRANSITION/STATUS 行",
        "fix": (
            "这通常意味着 AI 提示需要调整。"
            "尝试 --retry-strategy continue 重试"
        ),
    },
    "state_corrupted": {
        "what": "状态文件无法解析",
        "why": "state.yaml 文件包含无效的 YAML 或为空",
        "fix": "删除 kernel/state.yaml 并重启（状态将使用默认值重新创建）",
    },
}


def format_error(error_type: str, **kwargs) -> str:
    """Format an error message with recovery suggestions.

    Args:
        error_type: One of the keys in ERROR_MESSAGES.
        **kwargs: Template variables to substitute.

    Returns:
        Multi-line formatted error string with what/why/fix.
        Returns a generic message for unknown error types.
    """
    template = ERROR_MESSAGES.get(error_type)
    if template is None:
        # Generic fallback
        detail = kwargs.get("detail", error_type)
        return (
            f"  发生了什么: 发生错误（{detail}）\n"
            f"  原因: 内核无法继续当前操作\n"
            f"  解决方案: 检查上述错误详情并重试"
        )

    try:
        what = template["what"].format(**kwargs)
        why = template["why"].format(**kwargs)
        fix = template["fix"].format(**kwargs)
    except (KeyError, IndexError):
        # If template variables are missing, use raw templates
        what = template["what"]
        why = template["why"]
        fix = template["fix"]

    return f"  发生了什么: {what}\n  原因: {why}\n  解决方案: {fix}"


def classify_error(raw_error: str) -> tuple[str, dict]:
    """Classify a raw error string into a known error type.

    Parses the error message to determine type and extract kwargs.

    Args:
        raw_error: Raw error string from the runner.

    Returns:
        Tuple of (error_type, kwargs_dict).
        Returns ("unknown", {"detail": raw_error}) if cannot classify.
    """
    # Check for command not found
    cmd_match = re.search(r"command not found:\s*(\S+)", raw_error, re.IGNORECASE)
    if cmd_match:
        return ("command_not_found", {"cmd": cmd_match.group(1)})

    # Check for timeout
    timeout_match = re.search(r"timeout after (\d+)s on node (\S+)", raw_error, re.IGNORECASE)
    if timeout_match:
        return ("timeout", {"seconds": timeout_match.group(1), "node": timeout_match.group(2)})

    # Check for stuck node
    stuck_match = re.search(
        r"node '(\S+)' exceeded max_retries.*visited (\d+) times.*max (\d+)",
        raw_error,
        re.IGNORECASE,
    )
    if stuck_match:
        return (
            "stuck_node",
            {
                "node": stuck_match.group(1),
                "visits": stuck_match.group(2),
                "max_retries": stuck_match.group(3),
            },
        )

    # Check for contract violations
    if "contract violation" in raw_error.lower():
        return ("contract_violation", {"node": "unknown"})

    # Check for skill not found
    skill_match = re.search(r"skill not found:\s*(\S+)", raw_error, re.IGNORECASE)
    if skill_match:
        return ("skill_not_found", {"name": skill_match.group(1)})

    # Unknown
    return ("unknown", {"detail": raw_error})
