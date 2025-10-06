# MCP LLM Bridge

An MCP (Model Context Protocol) server that enables Claude Code to orchestrate multi-LLM conversations using configurable adapters.

## Features

- **Universal adapter system**: Configure any LLM CLI tool (Claude, GPT, Codex, Ollama, etc.)
- **Conversation management**: Persistent JSONL-based conversation history
- **Smart context selection**: Automatically select relevant history to pass to LLMs
- **Multiple context modes**: full, recent, smart, minimal, none
- **Portable**: Share the server, users configure their own adapters

## Installation

### Prerequisites

- Python 3.10+
- `uv` package manager (recommended) or `pip`

### Install with uv

```bash
# Clone or create project
cd mcp-llm-bridge

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### Install with pip

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

See `examples/adapters.json.example` for more examples.

### 2. Configure Claude Code

Add to your `.mcp.json`:

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

Replace `/absolute/path/to/mcp-llm-bridge` with the actual path.

### 3. Restart Claude Code

The MCP server will be available after restart.

## Usage

See `examples/CLAUDE.md.example` for detailed usage instructions to add to your project.

### Quick Example

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

## Available Tools

- `create_conversation`: Start a new conversation
- `call_llm`: Call an LLM adapter
- `get_recent_messages`: View recent messages
- `get_conversation_summary`: Get metadata and stats
- `list_conversations`: List all conversations
- `list_adapters`: See configured adapters

## Adapter Types

### Bash Adapter (stdin)

Most common - pipes message to stdin:

```json
{
  "type": "bash",
  "command": "claude",
  "args": [],
  "input_method": "stdin"
}
```

Invokes: `echo "message" | claude`

### Bash Adapter (arg)

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

Invokes: `codex --non-interactive "message"`

## File Structure

- `~/.mcp-llm-bridge/conversations/`: Conversation JSONL files
- `~/.mcp-llm-bridge/conversations/.metadata/`: Conversation metadata
- `~/.mcp-llm-bridge/adapters.json`: Adapter configuration

## Development

### Run Tests

```bash
pytest
```

### Format Code

```bash
uv run ruff format
```

### Lint Code

```bash
uv run ruff check
```

### Type Check

```bash
uv run ruff check --select=UP
```

## Troubleshooting

**Adapter not found:**
- Check adapter is in adapters.json
- Verify CLI tool is installed: `which <command>`
- Use `list_adapters` with `test_availability: true`

**Conversation not found:**
- Use `list_conversations` to see available IDs
- Create with `create_conversation` first

**MCP server not showing in Claude Code:**
- Restart Claude Code
- Check `.mcp.json` path is absolute
- Run `/mcp` in Claude Code to see status

## License

MIT