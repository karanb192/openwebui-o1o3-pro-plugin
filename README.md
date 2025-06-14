# OpenAI o1-pro & o3-pro Integration for Open Web UI

Access OpenAI's most advanced reasoning models with comprehensive token usage tracking and cost analytics directly in Open Web UI.

## 🌟 Features

- **Premium Models**: Access to o1-pro and o3-pro reasoning models
- **Cost Tracking**: Detailed per-message and cumulative conversation costs
- **Token Analytics**: Track input, output, and reasoning tokens separately
- **Multi-Key Support**: Round-robin load balancing across multiple API keys
- **Smart Conversation Tracking**: Maintains cost history throughout conversations
- **Configurable Parameters**: Adjust reasoning effort, output length, and more

## 📋 Prerequisites

- Open Web UI installation
- OpenAI API key(s) with access to o1-pro and/or o3-pro models
- Basic understanding of token-based pricing

## 🚀 Quick Start

1. Install the [function](https://www.openwebui.com/f/karanb192/o3pro_o1pro_support) in Open Web UI
2. Add your OpenAI API key(s) in settings
3. Select "OpenAI: o1-pro" or "OpenAI: o3-pro" from the model dropdown
4. Start chatting with cost tracking enabled

## ⚙️ Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| **API_KEYS** | OpenAI API key(s), comma-separated | *(required)* |
| **THINKING_EFFORT** | Reasoning intensity: `low`, `medium`, `high` | `medium` |
| **SHOW_TOKEN_STATS** | Display usage after responses | `True` |
| **SHOW_CUMULATIVE_COST** | Show conversation totals | `True` |
| **MAX_OUTPUT_TOKENS** | Maximum response length | `3200` |
| **TIMEOUT_SECONDS** | Request timeout | `600` |

## 💰 Model Pricing

| Model | Input | Output | Best For |
|-------|-------|--------|----------|
| **o1-pro** | $150/M | $600/M | Complex logic, coding, math |
| **o3-pro** | $20/M | $80/M | Cost effectiveness, general use |

## 📊 Cost Tracking Example

```
📊 Token Usage (This Message):
- Input: 1,234 tokens
- Reasoning: 567 tokens
- Output: 890 tokens
- Total: 2,691 tokens
- Cost for this message: $0.1234

💰 Conversation Totals:
- Messages: 3
- Total Input: 3,456 tokens
- Total Output: 2,345 tokens
- Total Cost: $0.3456
```

## 🎯 Model Selection Guide

**Choose o1-pro when you need:**
- Advanced mathematical problem solving
- Complex code generation or debugging
- Multi-step logical reasoning
- Maximum reasoning capability

**Choose o3-pro when you need:**
- Cost-effective advanced reasoning
- General purpose queries
- Analysis tasks

## ⚡ Tips for Cost Optimization

1. Use `low` thinking effort for simple queries
2. Set appropriate `MAX_OUTPUT_TOKENS` limits
3. Use o3-pro instead of o1-pro when possible
4. Monitor cumulative costs during long conversations

## 🔧 Troubleshooting

**No API keys configured**
- Add your OpenAI API key in function settings

**High costs**
- Lower `THINKING_EFFORT` setting
- Reduce `MAX_OUTPUT_TOKENS`
- Switch from o1-pro to o3-pro

**Timeout errors**
- Increase `TIMEOUT_SECONDS`
- Simplify complex queries

## 📝 Notes

- Responses appear all at once (no streaming) to ensure accurate token counting
- Conversation costs reset when starting a new chat
- Pricing subject to change per OpenAI's policies

## 🤝 Support

For issues or suggestions, please [reach out to me](mailto:karanb192@gmail.com).

---

**Version**: 1.0.0  
**License**: MIT License  
**Author**: Karan Bansal · [@karanb192](https://github.com/karanb192)
