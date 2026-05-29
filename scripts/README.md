# Scripts

## api_bridge.py - API Bridge for Kernel Execution

Allows running the kernel using Claude API or OpenAI API as the AI backend.

### Quick Start

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run the kernel with API bridge
python runner.py --goal "Build a REST API with FastAPI" --ai-command "python scripts/api_bridge.py" --verbose

# Or use OpenAI
export OPENAI_API_KEY="sk-..."
export AI_PROVIDER="openai"
python runner.py --goal "Build a REST API" --ai-command "python scripts/api_bridge.py" --verbose
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required for anthropic) | Anthropic API key |
| `OPENAI_API_KEY` | (required for openai) | OpenAI API key |
| `AI_PROVIDER` | `anthropic` | Provider: `anthropic` or `openai` |
| `AI_MODEL` | `claude-sonnet-4-20250514` / `gpt-4o` | Model name |
| `AI_MAX_TOKENS` | `8192` | Maximum response tokens |

### How It Works

The kernel pipes assembled context prompts to the bridge script via stdin. The bridge sends the prompt to the API and prints the response to stdout. The kernel then parses the response for STATUS/TRANSITION lines.

```
kernel (context prompt) -> stdin -> api_bridge.py -> API -> stdout -> kernel (parse response)
```
