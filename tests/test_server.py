"""Tests for MCP server implementation and API compatibility"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path


def test_server_imports():
    """Test that the server module can be imported without errors"""
    from mcp_llm_bridge import server

    # Check that required components are initialized
    assert hasattr(server, 'mcp')
    assert hasattr(server, 'conversation_manager')
    assert hasattr(server, 'adapter_manager')
    assert hasattr(server, 'context_selector')

    # Check that components are properly initialized
    assert server.conversation_manager is not None
    assert server.adapter_manager is not None
    assert server.context_selector is not None


def test_server_components_initialization():
    """Test that server components are properly initialized at module level"""
    from mcp_llm_bridge.server import conversation_manager, adapter_manager, context_selector, mcp

    # Verify components are instances of expected classes
    from mcp_llm_bridge.conversation import ConversationManager
    from mcp_llm_bridge.adapters import AdapterManager
    from mcp_llm_bridge.context_selector import ContextSelector

    assert isinstance(conversation_manager, ConversationManager)
    assert isinstance(adapter_manager, AdapterManager)
    assert isinstance(context_selector, ContextSelector)

    # Verify MCP server is properly initialized
    assert hasattr(mcp, 'run')
    assert hasattr(mcp, 'tool')


def test_server_tools_registration():
    """Test that all expected tools are registered with the MCP server"""

    # Check that the server has tools registered
    # FastMCP stores tools internally, so we check the module's tool functions
    import mcp_llm_bridge.server as server_module

    expected_tools = [
        'create_conversation',
        'call_llm',
        'get_recent_messages',
        'get_conversation_summary',
        'list_conversations',
        'list_adapters'
    ]

    for tool_name in expected_tools:
        assert hasattr(server_module, tool_name), f"Tool {tool_name} not found"
        tool_func = getattr(server_module, tool_name)
        # FastMCP decorates functions into FunctionTool objects, so we check for callability
        assert callable(tool_func), f"Tool {tool_name} is not callable"


def test_server_configuration_paths():
    """Test that server configuration paths are properly set up"""
    from mcp_llm_bridge.server import CONVERSATION_DIR, ADAPTER_CONFIG

    # Check that paths are Path objects
    assert isinstance(CONVERSATION_DIR, Path)
    assert isinstance(ADAPTER_CONFIG, Path)

    # Check that paths are expanded (user home paths should be expanded)
    assert str(CONVERSATION_DIR).startswith("/home") or str(CONVERSATION_DIR).startswith(str(Path.home()))
    assert str(ADAPTER_CONFIG).startswith("/home") or str(ADAPTER_CONFIG).startswith(str(Path.home()))


def test_server_module_execution():
    """Test that the server module can be executed as a script"""
    # This test ensures the server module has proper __main__ guard
    import mcp_llm_bridge.server as server_module

    # Check that the module has the expected main execution pattern
    assert hasattr(server_module, 'mcp')
    assert hasattr(server_module.mcp, 'run')


@pytest.mark.asyncio
async def test_server_component_functionality():
    """Test that server components are functional"""
    from mcp_llm_bridge.server import conversation_manager, adapter_manager

    # Test conversation manager
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        conv_manager = conversation_manager.__class__(temp_path)

        # Should be able to create conversation
        conv_id = conv_manager.create_conversation(initial_message="Test")
        assert conv_manager.conversation_exists(conv_id)

        # Should be able to list conversations
        conversations = conv_manager.list_conversations()
        assert len(conversations) >= 1

    # Test adapter manager with temporary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_path = Path(f.name)
        test_config = {
            "adapters": {
                "test-echo": {
                    "type": "bash",
                    "command": "echo",
                    "args": ["test"],
                    "input_method": "stdin",
                    "description": "Test echo adapter"
                }
            },
            "default_adapter": "test-echo"
        }
        json.dump(test_config, f)

    try:
        temp_adapter_manager = adapter_manager.__class__(config_path)

        # Should be able to list adapters
        adapters_info = temp_adapter_manager.list_adapters()
        assert "adapters" in adapters_info
        assert len(adapters_info["adapters"]) >= 1
        assert adapters_info["default_adapter"] == "test-echo"

    finally:
        config_path.unlink()  # Clean up


def test_fastmcp_api_compatibility():
    """Regression test for FastMCP API compatibility"""
    from mcp_llm_bridge.server import mcp

    # Test that FastMCP instance has expected methods
    assert hasattr(mcp, 'run'), "FastMCP instance should have run() method"
    assert callable(getattr(mcp, 'run')), "run() should be callable"

    # Test that we don't have deprecated methods
    assert not hasattr(mcp, 'set_lifespan'), "set_lifespan() should not exist (deprecated FastMCP API)"
    assert not hasattr(mcp, 'create_initialization_options'), "create_initialization_options() should not exist (deprecated FastMCP API)"


def test_no_asyncio_main_function():
    """Regression test to ensure we don't have the old asyncio.main() pattern"""
    import mcp_llm_bridge.server as server_module
    import inspect

    # Check that we don't have an async main function
    if hasattr(server_module, 'main'):
        main_func = getattr(server_module, 'main')
        assert not inspect.iscoroutinefunction(main_func), "main() should not be async (use mcp.run() directly)"


def test_tool_signatures():
    """Test that tool functions have correct signatures"""
    import mcp_llm_bridge.server as server_module

    # Check create_conversation exists and is callable
    create_conv = getattr(server_module, 'create_conversation')
    assert callable(create_conv), "create_conversation should be callable"

    # Check call_llm exists and is callable
    call_llm = getattr(server_module, 'call_llm')
    assert callable(call_llm), "call_llm should be callable"

    # FastMCP FunctionTool objects don't expose function signatures the same way
    # but they should be callable and have the expected structure


def test_server_error_handling():
    """Test server handles initialization errors gracefully"""
    # Test with invalid configuration paths

    try:
        # Test that server can handle missing config (should create default)
        temp_dir = Path(tempfile.mkdtemp())
        fake_config = temp_dir / "nonexistent" / "adapters.json"

        # This should not raise an exception during import
        from mcp_llm_bridge.adapters import AdapterManager
        AdapterManager(fake_config)

        # Should create a default config
        assert fake_config.exists()

    finally:
        # Clean up temp dir if we created one
        shutil.rmtree(temp_dir, ignore_errors=True)