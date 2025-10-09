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
    conversation_id: str | None = None,
    initial_message: str = "",
    topic: str = "",
    host_name: str = "",
) -> str:
    """Create a new conversation with an optional initial message

    Args:
        conversation_id: Optional conversation ID
        initial_message: Optional initial message from host
        topic: Optional topic description
        host_name: Optional 2-word host identifier (e.g., "claude_moderator").
                   Will be prefixed with "host_". Defaults to "host" if not provided.
    """
    global conversation_manager

    metadata = {"topic": topic} if topic else None

    result_id = conversation_manager.create_conversation(
        conversation_id=conversation_id,
        initial_message=initial_message,
        metadata=metadata,
        host_name=host_name,
    )

    conv_path = conversation_manager._get_conversation_path(result_id)

    response = {
        "conversation_id": result_id,
        "file_path": str(conv_path),
        "message": f"Created conversation: {result_id}",
    }

    import json

    return json.dumps(response)


@mcp.tool()
async def call_llm(
    conversation_id: str,
    adapter_name: str,
    message: str = "",
    context_mode: str = "smart",
    pass_history: bool = True,
    ctx: Context | None = None,
) -> str:
    """Call an LLM adapter with optional message and append response to conversation

    If message is empty and pass_history is True, the LLM will respond based on
    conversation history alone. This is useful for multi-LLM conversations where
    the host wants LLMs to interact without adding orchestrating messages.
    """
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
async def call_llm_parallel(
    conversation_id: str,
    adapter_names: list[str],
    message: str = "",
    context_mode: str = "smart",
    pass_history: bool = True,
    ctx: Context | None = None,
) -> str:
    """Call multiple LLM adapters in parallel and append all responses to conversation

    Args:
        conversation_id: Conversation identifier
        adapter_names: List of adapter names to call
        message: Optional message to send to all adapters
        context_mode: Context selection mode (full, smart, recent, minimal, none)
        pass_history: Whether to pass conversation history to adapters
        ctx: Optional context for progress reporting

    Returns:
        JSON with responses from all adapters
    """
    global conversation_manager, adapter_manager, context_selector
    import asyncio
    import json

    # Report progress if context available
    if ctx:
        await ctx.info(
            f"Calling {len(adapter_names)} adapters in parallel for conversation '{conversation_id}'"
        )

    # Validate inputs
    if not adapter_names:
        raise ValueError("adapter_names list cannot be empty")

    # Check if conversation exists
    if not conversation_manager.conversation_exists(conversation_id):
        raise ValueError(
            f"Conversation '{conversation_id}' does not exist. Create it first with create_conversation."
        )

    # Read conversation history once
    messages = conversation_manager.read_messages(conversation_id)

    # Select context once (all adapters get same context)
    selected_messages = []
    if pass_history:
        selected_messages = context_selector.select(messages, context_mode)

    # Define async function to call single adapter
    async def call_single_adapter(adapter_name: str) -> dict:
        try:
            result = await adapter_manager.call_adapter(
                adapter_name=adapter_name,
                message=message,
                conversation_history=selected_messages,
                pass_history=pass_history,
            )

            # Check for errors
            if result["metadata"].get("error"):
                return {
                    "adapter": adapter_name,
                    "response": "",
                    "error": result["metadata"]["error"],
                    "success": False,
                }

            # Append response to conversation
            conversation_manager.append_message(
                conversation_id=conversation_id,
                speaker=adapter_name,
                content=result["response"],
                metadata=result["metadata"],
            )

            return {
                "adapter": adapter_name,
                "response": result["response"],
                "error": None,
                "success": True,
            }

        except Exception as e:
            return {
                "adapter": adapter_name,
                "response": "",
                "error": str(e),
                "success": False,
            }

    # Call all adapters in parallel
    results = await asyncio.gather(*[call_single_adapter(name) for name in adapter_names])

    # Format response
    response = {
        "conversation_id": conversation_id,
        "total_adapters": len(adapter_names),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "results": results,
    }

    return json.dumps(response)


@mcp.tool()
async def summarize_conversation(
    conversation_id: str,
    adapter_name: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Generate a summary of the conversation using an LLM adapter

    Args:
        conversation_id: Conversation identifier
        adapter_name: Optional adapter to use (defaults to default_summarization_adapter)
        ctx: Optional context for progress reporting

    Returns:
        Summary of the conversation
    """
    global conversation_manager, adapter_manager
    import json

    # Check if conversation exists
    if not conversation_manager.conversation_exists(conversation_id):
        raise ValueError(f"Conversation '{conversation_id}' does not exist.")

    # Determine which adapter to use
    if adapter_name is None:
        adapter_name = adapter_manager.default_summarization_adapter
        if adapter_name is None:
            raise ValueError(
                "No adapter specified and no default_summarization_adapter configured"
            )

    # Report progress if context available
    if ctx:
        await ctx.info(
            f"Generating summary of '{conversation_id}' using '{adapter_name}'"
        )

    # Read all messages
    messages = conversation_manager.read_messages(conversation_id)

    if not messages:
        return json.dumps(
            {
                "conversation_id": conversation_id,
                "summary": "Empty conversation - no messages to summarize.",
                "message_count": 0,
            }
        )

    # Format conversation for summarization
    conversation_text = []
    for msg in messages:
        speaker = msg.get("speaker", "unknown")
        content = msg.get("content", "")
        conversation_text.append(f"{speaker}: {content}")

    full_text = "\n\n".join(conversation_text)

    # Create summarization prompt
    prompt = f"""Please provide a concise summary of the following conversation:

{full_text}

Summary:"""

    # Call adapter for summarization
    result = await adapter_manager.call_adapter(
        adapter_name=adapter_name,
        message=prompt,
        conversation_history=[],
        pass_history=False,
    )

    # Check for errors
    if result["metadata"].get("error"):
        error_msg = result["metadata"]["error"]
        raise ValueError(f"Error generating summary with '{adapter_name}': {error_msg}")

    # Return summary
    response = {
        "conversation_id": conversation_id,
        "summary": result["response"].strip(),
        "message_count": len(messages),
        "summarized_by": adapter_name,
    }

    return json.dumps(response)


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

    return json.dumps(metadata)


@mcp.tool()
async def list_conversations(limit: int = 20, sort_by: str = "updated_at") -> str:
    """List all available conversations"""
    global conversation_manager

    conversations = conversation_manager.list_conversations(
        limit=limit, sort_by=sort_by, order="desc"
    )

    import json

    result = {"total": len(conversations), "conversations": conversations}

    return json.dumps(result)


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

    return json.dumps(adapters_info)


if __name__ == "__main__":
    mcp.run()
