"""Tests for context selection"""

import pytest
from mcp_llm_bridge.context_selector import ContextSelector


@pytest.fixture
def context_selector():
    """Create a ContextSelector instance"""
    return ContextSelector()


@pytest.fixture
def sample_messages():
    """Create sample conversation messages"""
    return [
        {"turn": 1, "speaker": "user", "content": "Initial question"},
        {"turn": 2, "speaker": "assistant", "content": "First response"},
        {"turn": 3, "speaker": "user", "content": "Follow-up 1"},
        {"turn": 4, "speaker": "assistant", "content": "Response 1"},
        {"turn": 5, "speaker": "user", "content": "Follow-up 2"},
        {"turn": 6, "speaker": "assistant", "content": "Response 2"},
        {"turn": 7, "speaker": "user", "content": "Follow-up 3"},
        {"turn": 8, "speaker": "assistant", "content": "Response 3"},
    ]


def test_select_none_mode(context_selector, sample_messages):
    """Test 'none' context mode"""
    selected = context_selector.select(sample_messages, "none")
    assert selected == []


def test_select_minimal_mode(context_selector, sample_messages):
    """Test 'minimal' context mode"""
    selected = context_selector.select(sample_messages, "minimal")
    assert len(selected) == 1
    assert selected[0] == sample_messages[-1]


def test_select_minimal_mode_empty(context_selector):
    """Test 'minimal' context mode with empty messages"""
    selected = context_selector.select([], "minimal")
    assert selected == []


def test_select_recent_mode(context_selector, sample_messages):
    """Test 'recent' context mode"""
    selected = context_selector.select(sample_messages, "recent")
    assert len(selected) == len(sample_messages)  # Less than 10 messages
    assert selected == sample_messages


def test_select_recent_mode_truncated(context_selector):
    """Test 'recent' context mode with more than 10 messages"""
    messages = [{"turn": i, "content": f"Message {i}"} for i in range(1, 16)]

    selected = context_selector.select(messages, "recent")
    assert len(selected) == 10
    assert selected[0]["turn"] == 6  # Should be last 10 messages
    assert selected[-1]["turn"] == 15


def test_select_smart_mode_short(context_selector, sample_messages):
    """Test 'smart' context mode with short conversation"""
    selected = context_selector.select(sample_messages, "smart")
    assert len(selected) == len(sample_messages)  # 8 messages, less than 10
    assert selected == sample_messages


def test_select_smart_mode_long(context_selector):
    """Test 'smart' context mode with long conversation"""
    messages = [{"turn": i, "content": f"Message {i}"} for i in range(10)]

    selected = context_selector.select(messages, "smart")
    assert len(selected) == 6  # First + last 5
    assert selected[0]["turn"] == 0  # First message
    assert selected[1]["turn"] == 5  # Last 5 start from turn 5
    assert selected[-1]["turn"] == 9


def test_select_smart_mode_exactly_6(context_selector):
    """Test 'smart' context mode with exactly 6 messages"""
    messages = [{"turn": i, "content": f"Message {i}"} for i in range(6)]

    selected = context_selector.select(messages, "smart")
    assert len(selected) == 6
    assert selected == messages


def test_select_full_mode(context_selector, sample_messages):
    """Test 'full' context mode"""
    selected = context_selector.select(sample_messages, "full")
    assert len(selected) == len(sample_messages)
    assert selected == sample_messages


def test_select_unknown_mode(context_selector, sample_messages):
    """Test unknown context mode raises error"""
    with pytest.raises(ValueError, match="Unknown context mode"):
        context_selector.select(sample_messages, "unknown")


def test_select_empty_messages(context_selector):
    """Test selecting from empty messages"""
    modes = ["none", "minimal", "recent", "smart", "full"]

    for mode in modes:
        selected = context_selector.select([], mode)
        assert isinstance(selected, list)


def test_select_single_message(context_selector):
    """Test selecting from single message"""
    messages = [{"turn": 1, "content": "Only message"}]

    # All modes should work with single message
    for mode in ["minimal", "recent", "smart", "full"]:
        selected = context_selector.select(messages, mode)
        assert len(selected) == 1
        assert selected[0] == messages[0]

    # None mode should be empty
    selected = context_selector.select(messages, "none")
    assert len(selected) == 0


def test_smart_select_first_and_last_five(context_selector):
    """Test that smart selection gets first + last 5 messages"""
    # Create exactly 12 messages
    messages = [{"turn": i, "content": f"Message {i}"} for i in range(12)]

    selected = context_selector.select(messages, "smart")

    # Should be 6 messages: first (0) + last 5 (7-11)
    assert len(selected) == 6
    assert selected[0]["turn"] == 0
    assert selected[1]["turn"] == 7
    assert selected[-1]["turn"] == 11


def test_context_selection_with_message_structure(context_selector):
    """Test that context selection preserves message structure"""
    messages = [
        {
            "turn": 1,
            "speaker": "user",
            "content": "Question",
            "timestamp": "2023-01-01T00:00:00",
            "metadata": {"tokens": 10},
        },
        {
            "turn": 2,
            "speaker": "assistant",
            "content": "Answer",
            "timestamp": "2023-01-01T00:01:00",
            "metadata": {"tokens": 15},
        },
    ]

    selected = context_selector.select(messages, "smart")

    # Should preserve all fields
    assert len(selected) == 2
    assert selected[0]["turn"] == 1
    assert selected[0]["speaker"] == "user"
    assert selected[0]["metadata"]["tokens"] == 10
    assert selected[1]["turn"] == 2
    assert selected[1]["speaker"] == "assistant"
    assert selected[1]["metadata"]["tokens"] == 15
