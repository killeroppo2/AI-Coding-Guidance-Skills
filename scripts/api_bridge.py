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
        messages=[{"role": "user", "content": prompt}],
    )
    return (response.choices[0].message.content, False)


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

    print(result)


if __name__ == "__main__":
    run_bridge()
