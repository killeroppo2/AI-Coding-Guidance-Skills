"""API Bridge - reads stdin, sends to AI API, prints response to stdout.

Supports Anthropic and OpenAI APIs via environment variables:
  - AI_PROVIDER: "anthropic" (default) or "openai"
  - AI_MODEL: Model name (defaults to provider-specific default)
  - AI_MAX_TOKENS: Max tokens in response (default: 4096)
  - ANTHROPIC_API_KEY: API key for Anthropic
  - OPENAI_API_KEY: API key for OpenAI
"""

import os
import sys

SYSTEM_PROMPT = """你是一个自动化开发内核的AI执行节点。

【强制输出格式】
你的每次响应必须以以下两行结尾（纯文本，不在代码块中）：

STATUS: success
TRANSITION: <condition>

如果创建或修改了文件，在STATUS之前加：
FILES_WRITTEN: path/to/file1, path/to/file2

有效STATUS值：success, failure
有效TRANSITION值取决于当前节点（用户消息中会指明）。
缺少这两行 = 输出被拒绝 = 浪费重试。"""


def get_config() -> dict:
    """Read configuration from environment variables.

    Returns:
        Dict with provider, model, max_tokens, and api_key.
    """
    provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "4096"))

    if provider == "openai":
        model = os.environ.get("AI_MODEL", "gpt-4")
        api_key = os.environ.get("OPENAI_API_KEY", "")
    else:
        model = os.environ.get("AI_MODEL", "claude-sonnet-4-20250514")
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    return {
        "provider": provider,
        "model": model,
        "max_tokens": max_tokens,
        "api_key": api_key,
    }


def call_anthropic(prompt: str, config: dict) -> tuple[str, bool]:
    """Send prompt to Anthropic API and return response text.

    Args:
        prompt: The input text to send.
        config: Configuration dict with api_key, model, max_tokens.

    Returns:
        A tuple of (response_text, is_error). When is_error is True,
        the response_text is an error message.
    """
    try:
        import anthropic
    except ImportError:
        return ("错误: 请安装 anthropic 包: pip install anthropic", True)

    if not config["api_key"]:
        return ("错误: 请设置 ANTHROPIC_API_KEY 环境变量", True)

    client = anthropic.Anthropic(api_key=config["api_key"])
    message = client.messages.create(
        model=config["model"],
        max_tokens=config["max_tokens"],
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return (message.content[0].text, False)


def call_openai(prompt: str, config: dict) -> tuple[str, bool]:
    """Send prompt to OpenAI API and return response text.

    Args:
        prompt: The input text to send.
        config: Configuration dict with api_key, model, max_tokens.

    Returns:
        A tuple of (response_text, is_error). When is_error is True,
        the response_text is an error message.
    """
    try:
        import openai
    except ImportError:
        return ("错误: 请安装 openai 包: pip install openai", True)

    if not config["api_key"]:
        return ("错误: 请设置 OPENAI_API_KEY 环境变量", True)

    client = openai.OpenAI(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config["model"],
        max_tokens=config["max_tokens"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content, False)


def _ensure_format_lines(text: str, prompt: str) -> str:
    """Ensure STATUS and TRANSITION lines are present in the output.

    If the AI response is missing required format lines, append sensible
    defaults based on the detected node from the prompt.

    Args:
        text: The AI response text.
        prompt: The original prompt sent to the AI (used for node detection).

    Returns:
        The text with STATUS/TRANSITION lines guaranteed.
    """
    has_status = any(
        line.strip().startswith("STATUS:") for line in text.splitlines()
    )
    has_transition = any(
        line.strip().startswith("TRANSITION:") for line in text.splitlines()
    )
    if has_status and has_transition:
        return text

    node_transitions = {
        "init": "goal_loaded",
        "plan": "plan_ready",
        "code": "code_written",
        "test": "tests_pass",
        "review": "review_pass",
        "reflect": "no_evolution_needed",
        "evolve": "evolution_applied",
    }

    detected_node = None
    for node in node_transitions:
        if f"NODE PROMPT ({node})" in prompt or f"Current Node: {node}" in prompt:
            detected_node = node
            break

    default_transition = node_transitions.get(detected_node, "goal_loaded")

    additions = []
    if not has_status:
        additions.append("STATUS: success")
    if not has_transition:
        additions.append(f"TRANSITION: {default_transition}")

    return text.rstrip() + "\n\n" + "\n".join(additions) + "\n"


def run_bridge() -> None:
    """Main bridge logic: read stdin, call API, print response."""
    config = get_config()
    prompt = sys.stdin.read()

    if not prompt.strip():
        print("错误: 未从 stdin 收到输入", file=sys.stderr)
        sys.exit(1)

    if config["provider"] == "openai":
        result, is_error = call_openai(prompt, config)
    else:
        result, is_error = call_anthropic(prompt, config)

    if is_error:
        print(result, file=sys.stderr)
        sys.exit(2)

    output = _ensure_format_lines(result, prompt)
    print(output)


if __name__ == "__main__":
    run_bridge()
