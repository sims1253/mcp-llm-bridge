# MCP LLM Bridge

![CI](https://github.com/sims1253/mcp-llm-bridge/workflows/CI/badge.svg)
![Code Quality](https://github.com/sims1253/mcp-llm-bridge/workflows/Code%20Quality/badge.svg)

MCP server for multi-LLM conversations with configurable bash adapters.

This project was mostly implemented by claude sonnet 4.5 via claude code.

## Functionality

- Configure LLM CLI tools as adapters
- Store conversation history in JSON format
- Select context for LLM calls (smart, recent, full, minimal, none)
- Call multiple LLMs in the same conversation

## Components

- ConversationManager: JSON file I/O and metadata management
- AdapterManager: Bash-based LLM adapter execution
- ContextSelector: Conversation history selection (smart, recent, full, minimal, none)
- MCP Server: Six tools for conversation management

## Installation

### Prerequisites

- Python 3.10+
- `uv` or `pip`

### Install

```bash
cd mcp-llm-bridge
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Configuration

### 1. Configure Adapters

Create `~/.mcp-llm-bridge/adapters.json`:

```json
{
  "adapters": {
    "claude": {
      "type": "bash",
      "command": "claude",
      "args": ["-p"],
      "input_method": "stdin",
      "description": "Claude Sonnet 4.5 via claude code CLI"
    },
    "qwen": {
      "type": "bash",
      "command": "qwen",
      "args": ["-p"],
      "input_method": "stdin",
      "description": "qwen coder via qwen CLI"
    },
    "gemini": {
      "type": "bash",
      "command": "gemini",
      "args": [],
      "input_method": "stdin",
      "description": "gemini gemini-2.5-pro via gemini CLI"
    }
  },
  "default_adapter": "claude",
  "default_summarization_adapter": "qwen"
}
```

Configuration fields:
- `default_adapter`: Main adapter for general use
- `default_summarization_adapter`: Cheap/fast adapter for summarization tasks (optional, reduces token costs)

See `examples/adapters.json.example` for more examples including GPT, LM Studio, and OpenRouter.

### 2. Configure MCP Client

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "llm-bridge": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/mcp-llm-bridge",
        "run",
        "python",
        "-m",
        "mcp_llm_bridge.server"
      ],
      "env": {
        "CONVERSATION_DIR": "${HOME}/.mcp-llm-bridge/conversations",
        "ADAPTER_CONFIG": "${HOME}/.mcp-llm-bridge/adapters.json"
      }
    }
  }
}
```

Replace `/absolute/path/to/mcp-llm-bridge`.

## Usage

Example workflow:

```
1. list_adapters: {}
2. create_conversation:
     initial_message: "Compare sorting algorithms"
3. call_llm:
     conversation_id: <id>
     adapter_name: "my-claude"
     message: "Your analysis?"
4. call_llm:
     conversation_id: <id>
     adapter_name: "my-glm"
     message: "Your perspective?"
5. get_recent_messages:
     conversation_id: <id>
```

For parallel execution (faster multi-participant conversations):

```
call_llm_parallel:
  conversation_id: <id>
  adapter_names: ["claude", "qwen", "gemini"]
  message: "What are your thoughts?"
```

### Example Conversation

Multi-LLM conversation stored in JSON format:

![Example conversation history](examples/history.svg)

## Tools

- `create_conversation`
- `call_llm`
- `call_llm_parallel` - Call multiple adapters concurrently for faster multi-participant conversations
- `summarize_conversation` - Generate conversation summary using cheap/fast adapter (saves host tokens)
- `get_recent_messages`
- `get_conversation_summary`
- `list_conversations`
- `list_adapters`

## Adapters

### stdin

Passes message to stdin (most common):

```json
{
  "type": "bash",
  "command": "claude",
  "args": ["-p"],
  "input_method": "stdin",
  "description": "Claude via Anthropic CLI"
}
```

### arg

Passes message as argument:

```json
{
  "type": "bash",
  "command": "echo",
  "args": ["You said:"],
  "input_method": "arg",
  "message_arg_template": "{message}",
  "description": "Simple echo for testing"
}
```

### LM Studio

For OpenAI-compatible APIs like LM Studio (requires `jq`):

```json
{
  "type": "bash",
  "command": "bash",
  "args": ["-c", "jq -Rs '{messages: [{role: \"user\", content: .}], model: \"your-model-name\", temperature: 0.7, max_tokens: -1}' | curl -s -X POST http://localhost:1234/v1/chat/completions -H 'Content-Type: application/json' -d @- | jq -r '.choices[0].message.content // .error.message // \"No response\"'"],
  "input_method": "stdin",
  "description": "Local LM Studio server"
}
```

Replace `your-model-name` with the model name from LM Studio (e.g., `"apriel-1.5-15b-thinker@q6_k"`). Enable "Serve on Local Network" in LM Studio settings if running from WSL.

### GPT via Codex CLI

```json
{
  "type": "bash",
  "command": "codex",
  "args": ["exec"],
  "input_method": "stdin",
  "description": "GPT-5 via codex CLI"
}
```

### OpenRouter

For OpenRouter API access (requires `jq`):

```json
{
  "type": "bash",
  "command": "bash",
  "args": ["-c", "jq -Rs '{messages: [{role: \"user\", content: .}], model: \"z-ai/glm-4.6\"}' | curl -s -X POST https://openrouter.ai/api/v1/chat/completions -H 'Content-Type: application/json' -H \"Authorization: Bearer $OPENROUTER_API_KEY\" -H 'HTTP-Referer: https://github.com/sims1253/mcp-llm-bridge' -H 'X-Title: MCP LLM Bridge' -d @- | jq -r '.choices[0].message.content // .error.message // \"No response\"'"],
  "input_method": "stdin",
  "description": "OpenRouter API"
}
```

Set your API key in `~/.bashrc` or wherever applicable:
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

## File Structure

- `~/.mcp-llm-bridge/conversations/`: JSON array files (one message per array element)
- `~/.mcp-llm-bridge/conversations/.metadata/`: JSON metadata
- `~/.mcp-llm-bridge/adapters.json`: Adapter configuration

Conversation IDs use timestamp with random suffix to prevent collisions.

## Security

- Conversation IDs are sanitized against path traversal
- Adapters run in subprocess with configurable timeout
- Input validation on all parameters

## Development

### Setup

```bash
git clone git@github.com:sims1253/mcp-llm-bridge.git
cd mcp-llm-bridge
uv sync --all-extras
```

### Tests

```bash
uv run pytest
uv run python simple_test.py
uv run python manual_test.py
uv run python interact.py
```

### Formatting

```bash
uv run ruff format
uv run ruff check
```

## Troubleshooting

Adapter not found:
- Check `adapters.json`
- Verify command exists: `which <command>`
- Run `list_adapters` with `test_availability: true`

Conversation not found:
- Run `list_conversations`
- Create conversation first

MCP server not connecting:
- Verify absolute path in `.mcp.json`
- Restart MCP client

## License

MIT