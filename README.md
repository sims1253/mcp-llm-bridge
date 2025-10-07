# MCP LLM Bridge

![CI](https://github.com/sims1253/mcp-llm-bridge/workflows/CI/badge.svg)
![Code Quality](https://github.com/sims1253/mcp-llm-bridge/workflows/Code%20Quality/badge.svg)

MCP server for multi-LLM conversations with configurable bash adapters.

## Functionality

- Configure LLM CLI tools as adapters
- Store conversation history in JSONL format
- Select context for LLM calls (smart, recent, full, minimal, none)
- Call multiple LLMs in the same conversation

## Components

- ConversationManager: JSONL file I/O and metadata management
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
    "my-claude": {
      "type": "bash",
      "command": "claude",
      "args": [],
      "input_method": "stdin",
      "description": "Claude via Anthropic CLI"
    },
    "my-glm": {
      "type": "bash",
      "command": "glm",
      "args": ["--no-stream"],
      "input_method": "stdin",
      "description": "GLM via CLI"
    }
  },
  "default_adapter": "my-claude"
}
```

See `examples/adapters.json.example`.

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

## Tools

- `create_conversation`
- `call_llm`
- `get_recent_messages`
- `get_conversation_summary`
- `list_conversations`
- `list_adapters`

## Adapters

### stdin

Passes message to stdin:

```json
{
  "type": "bash",
  "command": "claude",
  "args": [],
  "input_method": "stdin"
}
```

### arg

Passes message as argument:

```json
{
  "type": "bash",
  "command": "codex",
  "args": ["--non-interactive"],
  "input_method": "arg",
  "message_arg_template": "{message}"
}
```

## File Structure

- `~/.mcp-llm-bridge/conversations/`: JSONL files (one JSON object per line)
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