#!/usr/bin/env python3
"""API Bridge - connects kernel to Claude/OpenAI API.

Usage:
    python runner.py --goal "..." --ai-command "python scripts/api_bridge.py"

Environment variables:
    ANTHROPIC_API_KEY - Required for Claude (default)
    OPENAI_API_KEY   - Required for OpenAI
    AI_PROVIDER      - "anthropic" (default) or "openai"
    AI_MODEL         - Model name (default: claude-sonnet-4-20250514 or gpt-4o)
    AI_MAX_TOKENS    - Max response tokens (default: 8192)
"""

import os
import sys


def main():
    prompt = sys.stdin.read()
    if not prompt.strip():
        print("Error: Empty prompt received on stdin", file=sys.stderr)
        sys.exit(1)

    provider = os.environ.get("AI_PROVIDER", "anthropic")
    max_tokens = int(os.environ.get("AI_MAX_TOKENS", "8192"))

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
            sys.exit(1)

        model = os.environ.get("AI_MODEL", "claude-sonnet-4-20250514")

        try:
            import anthropic
        except ImportError:
            print(
                "Error: anthropic package not installed. Run: pip install anthropic",
                file=sys.stderr,
            )
            sys.exit(1)

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        print(response.content[0].text)

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
            sys.exit(1)

        model = os.environ.get("AI_MODEL", "gpt-4o")

        try:
            import openai
        except ImportError:
            print(
                "Error: openai package not installed. Run: pip install openai",
                file=sys.stderr,
            )
            sys.exit(1)

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        print(response.choices[0].message.content)

    else:
        print(
            f"Error: Unknown AI_PROVIDER '{provider}'. Use 'anthropic' or 'openai'.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
