#!/usr/bin/env python3
"""Manual test of MCP LLM Bridge functionality"""

import asyncio
import json
from pathlib import Path
from mcp_llm_bridge.conversation import ConversationManager
from mcp_llm_bridge.adapters import AdapterManager
from mcp_llm_bridge.context_selector import ContextSelector


async def run_end_to_end_test():
    """Test the complete workflow"""
    print("🧪 Testing MCP LLM Bridge End-to-End")
    print("=" * 60)

    # Set up paths
    test_conv_dir = Path("/tmp/mcp-test-conversations")
    test_adapter_config = Path("/tmp/test_adapters.json")

    # Clean up from previous runs
    import shutil

    if test_conv_dir.exists():
        shutil.rmtree(test_conv_dir)

    # Create adapter configuration
    adapter_config = {
        "adapters": {
            "test-echo": {
                "type": "bash",
                "command": "cat",
                "args": [],
                "input_method": "stdin",
                "description": "Simple test adapter using cat",
            },
            "test-uppercase": {
                "type": "bash",
                "command": "tr",
                "args": ["[:lower:]", "[:upper:]"],
                "input_method": "stdin",
                "description": "Test adapter that converts to uppercase",
            },
        },
        "default_adapter": "test-echo",
    }

    with open(test_adapter_config, "w") as f:
        json.dump(adapter_config, f, indent=2)

    # Initialize components
    print("\n1. Initializing components...")
    conv_manager = ConversationManager(test_conv_dir)
    adapter_manager = AdapterManager(test_adapter_config)
    context_selector = ContextSelector()
    print("   ✅ Components initialized")

    # List adapters
    print("\n2. Listing available adapters...")
    adapters_info = adapter_manager.list_adapters()
    print(f"   Default adapter: {adapters_info['default_adapter']}")
    for adapter in adapters_info["adapters"]:
        print(f"   - {adapter['name']}: {adapter['description']}")

    # Test adapter availability
    print("\n3. Testing adapter availability...")
    for adapter in adapters_info["adapters"]:
        is_available = await adapter_manager.test_adapter(adapter["name"])
        status = "✅" if is_available else "❌"
        print(f"   {status} {adapter['name']}")

    # Create a conversation
    print("\n4. Creating a new conversation...")
    conv_id = conv_manager.create_conversation(
        initial_message="Hello! Can you help me test this system?",
        metadata={"topic": "System Testing"},
    )
    print(f"   ✅ Created conversation: {conv_id}")
    print(f"   📁 File location: {conv_manager._get_conversation_path(conv_id)}")

    # Verify conversation file exists
    conv_path = conv_manager._get_conversation_path(conv_id)
    if conv_path.exists():
        print("   ✅ Conversation file created successfully")
        with open(conv_path) as f:
            lines = f.readlines()
            print(f"   📄 File contains {len(lines)} message(s)")
    else:
        print("   ❌ Conversation file NOT created")
        return

    # Read the initial message
    print("\n5. Reading conversation messages...")
    messages = conv_manager.read_messages(conv_id)
    print(f"   📊 Found {len(messages)} message(s)")
    for msg in messages:
        print(f"   [Turn {msg['turn']}] {msg['speaker']}: {msg['content'][:50]}...")

    # Call an adapter (test-echo uses cat)
    print("\n6. Calling LLM adapter (test-echo)...")
    selected = context_selector.select(messages, "smart")
    result = await adapter_manager.call_adapter(
        adapter_name="test-echo",
        message="This is a test response from the adapter!",
        conversation_history=selected,
        pass_history=False,
    )
    print(f"   🤖 Adapter response: {result['response']}")
    print(f"   ⏱️  Execution time: {result['metadata']['execution_time_ms']}ms")
    print(f"   📊 Exit code: {result['metadata']['exit_code']}")

    # Append the response
    conv_manager.append_message(
        conversation_id=conv_id,
        speaker="test-echo",
        content=result["response"],
        metadata=result["metadata"],
    )
    print("   ✅ Response appended to conversation")

    # Call another adapter (test-uppercase uses tr)
    print("\n7. Calling another adapter (test-uppercase)...")
    messages = conv_manager.read_messages(conv_id)
    result = await adapter_manager.call_adapter(
        adapter_name="test-uppercase",
        message="hello world this should be uppercase",
        conversation_history=messages,
        pass_history=False,
    )
    print(f"   🤖 Adapter response: {result['response']}")

    conv_manager.append_message(
        conversation_id=conv_id,
        speaker="test-uppercase",
        content=result["response"],
        metadata=result["metadata"],
    )

    # Read all messages
    print("\n8. Reading complete conversation...")
    all_messages = conv_manager.read_messages(conv_id)
    print(f"   📊 Total messages: {len(all_messages)}")
    for msg in all_messages:
        print(f"   [Turn {msg['turn']}] {msg['speaker']}: {msg['content'][:60]}...")

    # Get conversation metadata
    print("\n9. Getting conversation metadata...")
    metadata = conv_manager.get_metadata(conv_id)
    print("   📋 Metadata:")
    print(f"      - ID: {metadata['id']}")
    print(f"      - Created: {metadata['created_at']}")
    print(f"      - Updated: {metadata['updated_at']}")
    print(f"      - Participants: {metadata['participants']}")
    print(f"      - Message count: {metadata['message_count']}")
    print(f"      - Topic: {metadata['topic']}")

    # List all conversations
    print("\n10. Listing all conversations...")
    conversations = conv_manager.list_conversations()
    print(f"    📂 Found {len(conversations)} conversation(s)")
    for conv in conversations:
        print(f"       - {conv['id']}: {conv['message_count']} messages")

    # Test context selection modes
    print("\n11. Testing context selection modes...")
    for mode in ["none", "minimal", "recent", "smart", "full"]:
        selected = context_selector.select(all_messages, mode)
        print(f"    - {mode:10s}: {len(selected)} messages selected")

    # Verify file contents
    print("\n12. Verifying conversation file structure...")
    with open(conv_path, "r") as f:
        for i, line in enumerate(f, 1):
            msg = json.loads(line)
            print(
                f"    Line {i}: Turn {msg['turn']}, Speaker: {msg['speaker']}, Content length: {len(msg['content'])} chars"
            )

    print("\n" + "=" * 60)
    print("🎉 All tests completed successfully!")
    print(f"📁 Conversation files are in: {test_conv_dir}")
    print(f"   - Conversation: {conv_path}")
    print(f"   - Metadata: {conv_manager._get_metadata_path(conv_id)}")


if __name__ == "__main__":
    asyncio.run(run_end_to_end_test())
