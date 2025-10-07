"""Tests for adapter management"""

import pytest
import json
from mcp_llm_bridge.adapters import AdapterManager, AdapterConfig


@pytest.fixture
def temp_adapter_manager(tmp_path):
    """Create a temporary adapter manager"""
    config_path = tmp_path / "adapters.json"
    manager = AdapterManager(config_path)
    return manager


@pytest.fixture
def echo_adapter_config(tmp_path):
    """Create a simple adapter configuration for testing"""
    config = {
        "adapters": {
            "echo": {
                "type": "bash",
                "command": "cat",  # Use cat instead of echo for stdin tests
                "args": [],
                "input_method": "stdin",
                "description": "Simple cat adapter for stdin testing",
            },
            "echo-arg": {
                "type": "bash",
                "command": "echo",
                "args": ["You said:"],
                "input_method": "arg",
                "message_arg_template": "{message}",
                "description": "Echo adapter with arg",
            },
            "nonexistent": {
                "type": "bash",
                "command": "nonexistent-command-12345",
                "args": [],
                "input_method": "stdin",
                "description": "Nonexistent command for testing",
            },
        },
        "default_adapter": "echo",
    }

    config_path = tmp_path / "adapters.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    return config_path


@pytest.mark.asyncio
async def test_call_echo_adapter(echo_adapter_config):
    """Test calling a simple stdin adapter (cat)"""
    manager = AdapterManager(echo_adapter_config)

    # Call adapter
    result = await manager.call_adapter(
        adapter_name="echo", message="Hello world", pass_history=False
    )

    assert result["response"] == "Hello world"
    assert result["metadata"]["exit_code"] == 0
    assert result["metadata"]["adapter"] == "echo"
    assert result["metadata"]["error"] is None


@pytest.mark.asyncio
async def test_call_arg_adapter(echo_adapter_config):
    """Test calling an adapter that takes message as argument"""
    manager = AdapterManager(echo_adapter_config)

    result = await manager.call_adapter(
        adapter_name="echo-arg", message="Hello world", pass_history=False
    )

    assert "You said: Hello world" in result["response"]
    assert result["metadata"]["exit_code"] == 0


@pytest.mark.asyncio
async def test_adapter_with_history(echo_adapter_config):
    """Test adapter with conversation history"""

    # Use cat command that will echo input
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

    config_path = echo_adapter_config.parent / "cat_config.json"
    with open(config_path, "w") as f:
        json.dump(cat_config, f)

    cat_manager = AdapterManager(config_path)

    history = [
        {"speaker": "user", "content": "Previous message"},
        {"speaker": "assistant", "content": "Previous response"},
    ]

    result = await cat_manager.call_adapter(
        adapter_name="cat",
        message="New message",
        conversation_history=history,
        pass_history=True,
    )

    # Should contain both history and new message
    assert "Previous message" in result["response"]
    assert "Previous response" in result["response"]
    assert "New message" in result["response"]


@pytest.mark.asyncio
async def test_adapter_without_history(echo_adapter_config):
    """Test adapter without passing history"""
    manager = AdapterManager(echo_adapter_config)

    history = [{"speaker": "user", "content": "Previous message"}]

    result = await manager.call_adapter(
        adapter_name="echo",
        message="New message",
        conversation_history=history,
        pass_history=False,
    )

    # Should only contain the new message (using cat which echoes stdin)
    assert result["response"] == "New message"
    assert "Previous message" not in result["response"]


@pytest.mark.asyncio
async def test_nonexistent_adapter(echo_adapter_config):
    """Test calling a nonexistent adapter"""
    manager = AdapterManager(echo_adapter_config)

    with pytest.raises(ValueError, match="Unknown adapter"):
        await manager.call_adapter("nonexistent-adapter", "test")


@pytest.mark.asyncio
async def test_command_not_found(echo_adapter_config):
    """Test calling adapter with nonexistent command"""
    manager = AdapterManager(echo_adapter_config)

    result = await manager.call_adapter(adapter_name="nonexistent", message="test")

    assert result["response"] == ""
    assert result["metadata"]["exit_code"] == -1
    assert "Command not found" in result["metadata"]["error"]


@pytest.mark.asyncio
async def test_unsupported_adapter_type(tmp_path):
    """Test unsupported adapter type"""
    config = {
        "adapters": {
            "unsupported": {"type": "python", "description": "Unsupported type"}
        }
    }

    config_path = tmp_path / "adapters.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    manager = AdapterManager(config_path)

    with pytest.raises(ValueError, match="Unsupported adapter type"):
        await manager.call_adapter("unsupported", "test")


def test_list_adapters(echo_adapter_config):
    """Test listing adapters"""
    manager = AdapterManager(echo_adapter_config)

    adapters_info = manager.list_adapters()

    assert "adapters" in adapters_info
    assert "default_adapter" in adapters_info
    assert "config_path" in adapters_info

    adapters = adapters_info["adapters"]
    assert len(adapters) == 3

    # Check echo adapter
    echo_adapter = next(a for a in adapters if a["name"] == "echo")
    assert echo_adapter["type"] == "bash"
    assert echo_adapter["description"] == "Simple cat adapter for stdin testing"
    assert echo_adapter["command"] == "cat"

    assert adapters_info["default_adapter"] == "echo"


def test_create_default_config(tmp_path):
    """Test creating default configuration"""
    config_path = tmp_path / "nonexistent_config.json"

    # Should create default config
    AdapterManager(config_path)

    assert config_path.exists()

    with open(config_path) as f:
        config = json.load(f)

    assert "adapters" in config
    assert "example-bash" in config["adapters"]
    assert config["adapters"]["example-bash"]["type"] == "bash"


def test_adapter_config():
    """Test AdapterConfig class"""
    config = {
        "type": "bash",
        "command": "echo",
        "args": ["hello"],
        "description": "Test adapter",
    }

    adapter = AdapterConfig("test", config)

    assert adapter.name == "test"
    assert adapter.type == "bash"
    assert adapter.description == "Test adapter"
    assert adapter.config == config


@pytest.mark.asyncio
async def test_adapter_with_env_and_timeout(tmp_path):
    """Test adapter with environment variables and timeout"""
    config = {
        "adapters": {
            "env-test": {
                "type": "bash",
                "command": "sh",
                "args": ["-c", "echo $TEST_VAR"],
                "input_method": "stdin",
                "env": {"TEST_VAR": "test_value"},
                "timeout_seconds": 5,
                "description": "Test environment and timeout",
            }
        }
    }

    config_path = tmp_path / "adapters.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    manager = AdapterManager(config_path)

    result = await manager.call_adapter("env-test", "test")

    assert result["response"] == "test_value"
    assert result["metadata"]["exit_code"] == 0


@pytest.mark.asyncio
async def test_test_adapter_available(echo_adapter_config):
    """Test adapter availability testing"""
    manager = AdapterManager(echo_adapter_config)

    # Test existing command
    is_available = await manager.test_adapter("echo")
    assert is_available

    # Test nonexistent command
    is_available = await manager.test_adapter("nonexistent")
    assert not is_available


@pytest.mark.asyncio
async def test_test_adapter_unknown(echo_adapter_config):
    """Test testing unknown adapter"""
    manager = AdapterManager(echo_adapter_config)

    is_available = await manager.test_adapter("unknown-adapter")
    assert not is_available


def test_load_adapters_with_existing_config(echo_adapter_config):
    """Test loading adapters from existing config"""
    manager = AdapterManager(echo_adapter_config)

    assert "echo" in manager.adapters
    assert "echo-arg" in manager.adapters
    assert manager.default_adapter == "echo"

    # Check adapter properties
    echo_adapter = manager.adapters["echo"]
    assert isinstance(echo_adapter, AdapterConfig)
    assert echo_adapter.name == "echo"
    assert echo_adapter.type == "bash"
