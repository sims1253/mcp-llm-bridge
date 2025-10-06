"""Integration tests for full workflow"""

import pytest
import json
from mcp_llm_bridge.conversation import ConversationManager
from mcp_llm_bridge.adapters import AdapterManager
from mcp_llm_bridge.context_selector import ContextSelector


@pytest.fixture
def integration_setup(tmp_path):
    """Set up all components for integration testing"""
    conv_dir = tmp_path / "conversations"
    adapter_config = tmp_path / "adapters.json"

    # Create simple adapter config
    config = {
        "adapters": {
            "echo": {
                "type": "bash",
                "command": "echo",
                "args": [],
                "input_method": "stdin",
                "description": "Echo adapter",
            },
            "prefix-echo": {
                "type": "bash",
                "command": "echo",
                "args": ["Response:"],
                "input_method": "arg",
                "message_arg_template": "{message}",
                "description": "Prefix echo adapter",
            },
        },
        "default_adapter": "echo",
    }

    with open(adapter_config, "w") as f:
        json.dump(config, f)

    conv_manager = ConversationManager(conv_dir)
    adapter_manager = AdapterManager(adapter_config)
    context_selector = ContextSelector()

    return conv_manager, adapter_manager, context_selector


@pytest.mark.asyncio
async def test_full_conversation_flow(integration_setup):
    """Test complete conversation flow"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # 1. Create conversation
    conv_id = conv_manager.create_conversation(initial_message="What is 2+2?")

    # 2. Call LLM (echo adapter)
    messages = conv_manager.read_messages(conv_id)
    selected = context_selector.select(messages, "smart")

    result = await adapter_manager.call_adapter(
        adapter_name="echo",
        message="The answer is 4",
        conversation_history=selected,
        pass_history=True,
    )

    # 3. Append response
    conv_manager.append_message(
        conversation_id=conv_id,
        speaker="echo",
        content=result["response"],
        metadata=result["metadata"],
    )

    # 4. Verify conversation state
    all_messages = conv_manager.read_messages(conv_id)
    assert len(all_messages) == 2
    assert all_messages[0]["speaker"] == "user"
    assert all_messages[0]["content"] == "What is 2+2?"
    assert all_messages[1]["speaker"] == "echo"
    assert all_messages[1]["content"] == "The answer is 4"

    # 5. Get summary
    metadata = conv_manager.get_metadata(conv_id)
    assert metadata["message_count"] == 2
    assert "echo" in metadata["participants"]


@pytest.mark.asyncio
async def test_multi_turn_conversation(integration_setup):
    """Test multi-turn conversation with context"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Create conversation
    conv_id = conv_manager.create_conversation(initial_message="Initial question")

    # First turn
    messages = conv_manager.read_messages(conv_id)
    selected = context_selector.select(messages, "smart")

    result1 = await adapter_manager.call_adapter(
        adapter_name="prefix-echo",
        message="First response",
        conversation_history=selected,
        pass_history=False,
    )

    conv_manager.append_message(conv_id, "prefix-echo", result1["response"])

    # Second turn - should include history
    messages = conv_manager.read_messages(conv_id)
    selected = context_selector.select(messages, "smart")

    result2 = await adapter_manager.call_adapter(
        adapter_name="echo",
        message="Second response",
        conversation_history=selected,
        pass_history=True,
    )

    conv_manager.append_message(conv_id, "echo", result2["response"])

    # Verify conversation
    all_messages = conv_manager.read_messages(conv_id)
    assert len(all_messages) == 3
    assert all_messages[0]["speaker"] == "user"
    assert all_messages[1]["speaker"] == "prefix-echo"
    assert all_messages[2]["speaker"] == "echo"


@pytest.mark.asyncio
async def test_context_modes_in_integration(integration_setup):
    """Test different context modes in integration"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Create conversation with multiple messages
    conv_id = conv_manager.create_conversation(initial_message="Question 1")
    conv_manager.append_message(conv_id, "assistant1", "Answer 1")
    conv_manager.append_message(conv_id, "user", "Question 2")
    conv_manager.append_message(conv_id, "assistant2", "Answer 2")
    conv_manager.append_message(conv_id, "user", "Question 3")

    # Test different context modes
    all_messages = conv_manager.read_messages(conv_id)

    # Full mode
    full_selected = context_selector.select(all_messages, "full")
    assert len(full_selected) == 5

    # Recent mode (all messages since < 10)
    recent_selected = context_selector.select(all_messages, "recent")
    assert len(recent_selected) == 5

    # Smart mode (first + last 5 = all 5)
    smart_selected = context_selector.select(all_messages, "smart")
    assert len(smart_selected) == 5
    assert smart_selected[0]["content"] == "Question 1"

    # Minimal mode
    minimal_selected = context_selector.select(all_messages, "minimal")
    assert len(minimal_selected) == 1
    assert minimal_selected[0]["content"] == "Question 3"

    # None mode
    none_selected = context_selector.select(all_messages, "none")
    assert len(none_selected) == 0


@pytest.mark.asyncio
async def test_error_handling_in_flow(integration_setup):
    """Test error handling in conversation flow"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Create conversation
    conv_id = conv_manager.create_conversation(initial_message="Test")

    # Try to call nonexistent adapter
    with pytest.raises(ValueError, match="Unknown adapter"):
        await adapter_manager.call_adapter("nonexistent", "test")

    # Conversation should still be valid
    messages = conv_manager.read_messages(conv_id)
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_conversation_persistence(integration_setup):
    """Test that conversations persist and can be retrieved"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Create conversation and add messages
    conv_id = conv_manager.create_conversation(
        conversation_id="test-persistence", initial_message="First message"
    )

    result = await adapter_manager.call_adapter(
        adapter_name="echo", message="Echo response", pass_history=False
    )

    conv_manager.append_message(conv_id, "echo", result["response"])

    # Create new manager instance (simulating restart)
    new_conv_manager = ConversationManager(conv_manager.conversation_dir)

    # Verify conversation is still there
    assert new_conv_manager.conversation_exists("test-persistence")

    messages = new_conv_manager.read_messages("test-persistence")
    assert len(messages) == 2
    assert messages[0]["content"] == "First message"
    assert messages[1]["content"] == "Echo response"

    metadata = new_conv_manager.get_metadata("test-persistence")
    assert metadata["message_count"] == 2
    assert "echo" in metadata["participants"]


@pytest.mark.asyncio
async def test_list_conversations_with_activity(integration_setup):
    """Test listing conversations after activity"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Create multiple conversations
    conv1 = conv_manager.create_conversation(initial_message="Conversation 1")
    conv2 = conv_manager.create_conversation(initial_message="Conversation 2")

    # Add activity to first conversation
    result = await adapter_manager.call_adapter(
        adapter_name="echo", message="Response to conv 1", pass_history=False
    )
    conv_manager.append_message(conv1, "echo", result["response"])

    # List conversations
    conversations = conv_manager.list_conversations()

    assert len(conversations) == 2
    # Most recently updated should be first
    assert conversations[0]["id"] == conv1
    assert conversations[0]["message_count"] == 2
    assert conversations[1]["id"] == conv2
    assert conversations[1]["message_count"] == 1


@pytest.mark.asyncio
async def test_adapter_history_formatting(integration_setup):
    """Test that history is properly formatted for adapters"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Create conversation with structured messages
    conv_id = conv_manager.create_conversation(initial_message="Initial")
    conv_manager.append_message(conv_id, "assistant", "Response 1")
    conv_manager.append_message(conv_id, "user", "Follow up")

    # Use cat adapter to see formatted output
    cat_config = {
        "adapters": {
            "cat": {
                "type": "bash",
                "command": "cat",
                "args": [],
                "input_method": "stdin",
                "description": "Cat adapter",
            }
        }
    }

    config_path = adapter_manager.config_path.parent / "cat_config.json"
    with open(config_path, "w") as f:
        json.dump(cat_config, f)

    cat_manager = AdapterManager(config_path)

    messages = conv_manager.read_messages(conv_id)
    selected = context_selector.select(messages, "smart")

    result = await cat_manager.call_adapter(
        adapter_name="cat",
        message="New message",
        conversation_history=selected,
        pass_history=True,
    )

    # Should contain formatted history
    assert "=== Conversation History ===" in result["response"]
    assert "user:" in result["response"]
    assert "assistant:" in result["response"]
    assert "Initial" in result["response"]
    assert "Response 1" in result["response"]
    assert "Follow up" in result["response"]
    assert "New message" in result["response"]


def test_component_initialization(integration_setup):
    """Test that components initialize properly"""
    conv_manager, adapter_manager, context_selector = integration_setup

    # Verify conversation manager
    assert conv_manager.conversation_dir.exists()
    assert conv_manager.metadata_dir.exists()

    # Verify adapter manager
    assert "echo" in adapter_manager.adapters
    assert adapter_manager.default_adapter == "echo"

    # Verify context selector
    assert context_selector is not None
    assert hasattr(context_selector, "select")
