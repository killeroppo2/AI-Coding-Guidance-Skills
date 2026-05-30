# Scripts - 工具脚本

## api_bridge.py - AI API 桥接器

将 stdin 输入发送到 AI API，并将响应输出到 stdout。

### 用法

```bash
echo "你好，请帮我写一个 Python 函数" | python scripts/api_bridge.py
```

### 配合内核使用

```bash
python runner.py --goal "创建一个计算器" --ai-command "python scripts/api_bridge.py"
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AI_PROVIDER` | AI 提供商 (`anthropic` 或 `openai`) | `anthropic` |
| `AI_MODEL` | 模型名称 | 取决于提供商 |
| `AI_MAX_TOKENS` | 最大输出 token 数 | `4096` |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | (必填，使用 anthropic 时) |
| `OPENAI_API_KEY` | OpenAI API 密钥 | (必填，使用 openai 时) |

### 安装依赖

```bash
# 使用 Anthropic
pip install anthropic

# 使用 OpenAI
pip install openai
```

### 示例

```bash
# 使用 Anthropic (默认)
export ANTHROPIC_API_KEY="your-key-here"
echo "写一个排序算法" | python scripts/api_bridge.py

# 使用 OpenAI
export AI_PROVIDER=openai
export OPENAI_API_KEY="your-key-here"
echo "写一个排序算法" | python scripts/api_bridge.py
```
