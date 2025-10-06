"""MCP server implementation"""

import os
from pathlib import Path

from fastmcp import FastMCP, Context

from .conversation import ConversationManager
from .adapters import AdapterManager
from .context_selector import ContextSelector

# Get configuration paths
CONVERSATION_DIR = Path(
    os.getenv("CONVERSATION_DIR", "~/.mcp-llm-bridge/conversations")
).expanduser()

ADAPTER_CONFIG = Path(
    os.getenv("ADAPTER_CONFIG", "~/.mcp-llm-bridge/adapters.json")
).expanduser()

# Initialize global components
conversation_manager = ConversationManager(CONVERSATION_DIR)
adapter_manager = AdapterManager(ADAPTER_CONFIG)
context_selector = ContextSelector()

# Initialize MCP server
mcp = FastMCP("mcp-llm-bridge")


@mcp.tool()
async def create_conversation(
    conversation_id: str | None = None, initial_message: str = "", topic: str = ""
) -> str:
    """Create a new conversation with an optional initial message"""
    global conversation_manager

    metadata = {"topic": topic} if topic else None

    result_id = conversation_manager.create_conversation(
        conversation_id=conversation_id,
        initial_message=initial_message,
        metadata=metadata,
    )

    conv_path = conversation_manager._get_conversation_path(result_id)

    response = {
        "conversation_id": result_id,
        "file_path": str(conv_path),
        "message": f"Created conversation: {result_id}",
    }

    import json

    return json.dumps(response, indent=2)


@mcp.tool()
async def call_llm(
    conversation_id: str,
    adapter_name: str,
    message: str,
    context_mode: str = "smart",
    pass_history: bool = True,
    ctx: Context | None = None,
) -> str:
    """Call an LLM adapter with a message and append response to conversation"""
    global conversation_manager, adapter_manager, context_selector

    # Report progress if context available
    if ctx:
        await ctx.info(
            f"Calling adapter '{adapter_name}' for conversation '{conversation_id}'"
        )

    # Check if conversation exists
    if not conversation_manager.conversation_exists(conversation_id):
        raise ValueError(
            f"Conversation '{conversation_id}' does not exist. Create it first with create_conversation."
        )

    # Read conversation history
    messages = conversation_manager.read_messages(conversation_id)

    # Select context
    selected_messages = []
    if pass_history:
        selected_messages = context_selector.select(messages, context_mode)

    # Call adapter
    result = await adapter_manager.call_adapter(
        adapter_name=adapter_name,
        message=message,
        conversation_history=selected_messages,
        pass_history=pass_history,
    )

    # Check for errors
    if result["metadata"].get("error"):
        error_msg = result["metadata"]["error"]
        raise ValueError(f"Error calling adapter '{adapter_name}': {error_msg}")

    # Append response to conversation
    conversation_manager.append_message(
        conversation_id=conversation_id,
        speaker=adapter_name,
        content=result["response"],
        metadata=result["metadata"],
    )

    # Return only the response
    return result["response"]


@mcp.tool()
async def get_recent_messages(conversation_id: str, count: int = 5) -> str:
    """Get N most recent messages from a conversation"""
    global conversation_manager

    if not conversation_manager.conversation_exists(conversation_id):
        raise ValueError(f"Conversation '{conversation_id}' does not exist.")

    messages = conversation_manager.read_messages(conversation_id)
    recent = messages[-count:] if len(messages) > count else messages

    # Format as plain text
    lines = []
    for msg in recent:
        speaker = msg.get("speaker", "unknown")
        content = msg.get("content", "")
        turn = msg.get("turn", "?")
        lines.append(f"[Turn {turn}] {speaker}:")
        lines.append(content)
        lines.append("")

    output = "\n".join(lines) if lines else "No messages found."
    return output


@mcp.tool()
async def get_conversation_summary(conversation_id: str) -> str:
    """Get high-level summary and metadata about a conversation"""
    global conversation_manager

    if not conversation_manager.conversation_exists(conversation_id):
        raise ValueError(f"Conversation '{conversation_id}' does not exist.")

    metadata = conversation_manager.get_metadata(conversation_id)

    import json

    return json.dumps(metadata, indent=2)


@mcp.tool()
async def list_conversations(limit: int = 20, sort_by: str = "updated_at") -> str:
    """List all available conversations"""
    global conversation_manager

    conversations = conversation_manager.list_conversations(
        limit=limit, sort_by=sort_by, order="desc"
    )

    import json

    result = {"total": len(conversations), "conversations": conversations}

    return json.dumps(result, indent=2)


@mcp.tool()
async def list_adapters(test_availability: bool = False) -> str:
    """List all configured LLM adapters"""
    global adapter_manager

    adapters_info = adapter_manager.list_adapters()

    # Optionally test availability
    if test_availability:
        for adapter in adapters_info["adapters"]:
            is_available = await adapter_manager.test_adapter(adapter["name"])
            adapter["available"] = is_available

    import json

    return json.dumps(adapters_info, indent=2)


if __name__ == "__main__":
    mcp.run()
