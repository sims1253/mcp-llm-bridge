"""Tests for conversation management"""

import pytest
from mcp_llm_bridge.conversation import ConversationManager


@pytest.fixture
def temp_conv_manager(tmp_path):
    """Create a temporary conversation manager"""
    return ConversationManager(tmp_path)


def test_create_conversation(temp_conv_manager):
    """Test creating a new conversation"""
    conv_id = temp_conv_manager.create_conversation(
        conversation_id="test_conv", initial_message="Hello world"
    )

    assert conv_id == "test_conv"
    assert temp_conv_manager.conversation_exists("test_conv")


def test_create_conversation_auto_id(temp_conv_manager):
    """Test creating a conversation with auto-generated ID"""
    conv_id = temp_conv_manager.create_conversation(initial_message="Hi")

    assert conv_id.startswith("conversation_")
    assert temp_conv_manager.conversation_exists(conv_id)


def test_create_conversation_duplicate(temp_conv_manager):
    """Test creating duplicate conversation fails"""
    temp_conv_manager.create_conversation("test", "Hello")

    with pytest.raises(ValueError, match="already exists"):
        temp_conv_manager.create_conversation("test", "Another")


def test_append_message(temp_conv_manager):
    """Test appending messages"""
    conv_id = temp_conv_manager.create_conversation(initial_message="Hi")

    temp_conv_manager.append_message(
        conversation_id=conv_id, speaker="assistant", content="Hello back!"
    )

    messages = temp_conv_manager.read_messages(conv_id)
    assert len(messages) == 2
    assert messages[1]["speaker"] == "assistant"
    assert messages[1]["content"] == "Hello back!"


def test_read_messages_with_slicing(temp_conv_manager):
    """Test reading messages with start/end"""
    conv_id = temp_conv_manager.create_conversation(initial_message="Start")

    for i in range(5):
        temp_conv_manager.append_message(conv_id, f"user{i}", f"Message {i}")

    messages = temp_conv_manager.read_messages(conv_id, start=1, end=4)
    assert len(messages) == 3
    assert messages[0]["content"] == "Message 0"
    assert messages[2]["content"] == "Message 2"


def test_read_messages_nonexistent(temp_conv_manager):
    """Test reading from non-existent conversation"""
    messages = temp_conv_manager.read_messages("nonexistent")
    assert messages == []


def test_get_metadata(temp_conv_manager):
    """Test getting conversation metadata"""
    conv_id = temp_conv_manager.create_conversation(initial_message="Test")
    temp_conv_manager.append_message(conv_id, "bot", "Response")

    metadata = temp_conv_manager.get_metadata(conv_id)

    assert metadata["id"] == conv_id
    assert metadata["message_count"] == 2
    assert "host" in metadata["participants"]
    assert "bot" in metadata["participants"]
    assert metadata["status"] == "active"


def test_get_metadata_generate_from_file(temp_conv_manager):
    """Test generating metadata from conversation file"""
    conv_id = temp_conv_manager.create_conversation(initial_message="First")
    temp_conv_manager.append_message(conv_id, "assistant", "Second")

    # Delete metadata file to force generation
    meta_path = temp_conv_manager._get_metadata_path(conv_id)
    if meta_path.exists():
        meta_path.unlink()

    metadata = temp_conv_manager.get_metadata(conv_id)
    assert metadata["message_count"] == 2
    assert "host" in metadata["participants"]
    assert "assistant" in metadata["participants"]


def test_list_conversations(temp_conv_manager):
    """Test listing conversations"""
    temp_conv_manager.create_conversation("conv1", "Message 1")
    temp_conv_manager.create_conversation("conv2", "Message 2")

    conversations = temp_conv_manager.list_conversations()

    assert len(conversations) == 2
    assert any(c["id"] == "conv1" for c in conversations)
    assert any(c["id"] == "conv2" for c in conversations)


def test_list_conversations_sorting(temp_conv_manager):
    """Test listing conversations with sorting"""
    # Create conversations with different timestamps
    conv1 = temp_conv_manager.create_conversation("conv1", "First")
    temp_conv_manager.create_conversation("conv2", "Second")

    # Add message to update timestamp
    temp_conv_manager.append_message(conv1, "user", "Update")

    # Test sorting by updated_at (default)
    conversations = temp_conv_manager.list_conversations(
        sort_by="updated_at", order="desc"
    )
    assert conversations[0]["id"] == "conv1"  # Most recently updated

    # Test sorting by message_count
    conversations = temp_conv_manager.list_conversations(
        sort_by="message_count", order="desc"
    )
    assert conversations[0]["id"] == "conv1"  # Has 2 messages vs 1


def test_list_conversations_limit(temp_conv_manager):
    """Test listing conversations with limit"""
    for i in range(5):
        temp_conv_manager.create_conversation(f"conv{i}", f"Message {i}")

    conversations = temp_conv_manager.list_conversations(limit=3)
    assert len(conversations) == 3


def test_conversation_id_sanitization(temp_conv_manager):
    """Test that conversation IDs are properly sanitized"""
    dangerous_id = "../../../etc/passwd"
    safe_id = "conv1"

    # Should create safe conversation even with dangerous input
    conv_id = temp_conv_manager.create_conversation(dangerous_id, "Test")
    assert conv_id == ""

    # Safe ID should work
    conv_id = temp_conv_manager.create_conversation(safe_id, "Test")
    assert conv_id == safe_id


def test_empty_conversation_metadata(temp_conv_manager):
    """Test metadata for empty conversation"""
    conv_id = temp_conv_manager.create_conversation()

    metadata = temp_conv_manager.get_metadata(conv_id)
    assert metadata["message_count"] == 0
    assert metadata["participants"] == []
    assert metadata["topic"] == ""
