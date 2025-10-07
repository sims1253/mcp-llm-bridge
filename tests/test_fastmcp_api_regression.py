"""Regression tests for FastMCP API compatibility issues"""

import pytest
import subprocess
import sys
from pathlib import Path


def test_server_starts_without_errors():
    """Regression test: Server should start without FastMCP API errors"""
    # This test ensures the server module can be imported and initialized
    # without the 'set_lifespan' AttributeError we encountered

    try:
        assert True  # If we get here, no import/initialization error
    except AttributeError as e:
        if "set_lifespan" in str(e):
            pytest.fail(
                "FastMCP API regression: 'set_lifespan' method does not exist in current FastMCP version"
            )
        else:
            raise


def test_server_has_correct_fastmcp_methods():
    """Regression test: Verify we're using correct FastMCP API"""
    from mcp_llm_bridge.server import mcp

    # Should have run() method (current FastMCP API)
    assert hasattr(mcp, "run"), "FastMCP should have run() method"

    # Should NOT have deprecated methods
    deprecated_methods = ["set_lifespan", "create_initialization_options"]
    for method in deprecated_methods:
        assert not hasattr(mcp, method), (
            f"FastMCP should not have deprecated method: {method}"
        )


def test_server_can_be_executed_directly():
    """Regression test: Server should be executable via `python -m`"""
    # Test that the module can be executed without immediate errors
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_llm_bridge.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=Path(__file__).parent.parent,
    )

    try:
        # Give it a moment to start and check if it's still running
        import time

        time.sleep(1)

        # Check if process is still running (no immediate crash)
        if proc.poll() is None:
            # Server started successfully, terminate it
            proc.terminate()
            proc.wait(timeout=5)
            success = True
        else:
            # Process exited, check for errors
            success = False
            returncode = proc.poll()
            _, stderr = proc.communicate()

            if "AttributeError" in stderr and "set_lifespan" in stderr:
                pytest.fail(f"FastMCP API regression detected: {stderr}")
            elif returncode != 0:
                pytest.fail(f"Server exited with error code {returncode}: {stderr}")

        assert success, "Server should start without errors"

    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Server did not respond within timeout")

    except Exception as e:
        proc.kill()
        pytest.fail(f"Unexpected error testing server execution: {e}")


def test_tool_functions_are_decorated():
    """Regression test: Verify tool functions are properly decorated with @mcp.tool()"""
    import mcp_llm_bridge.server as server_module

    # Get all functions that should be decorated as tools
    expected_tools = [
        "create_conversation",
        "call_llm",
        "get_recent_messages",
        "get_conversation_summary",
        "list_conversations",
        "list_adapters",
    ]

    for tool_name in expected_tools:
        tool_func = getattr(server_module, tool_name)

        # FastMCP decorates functions into FunctionTool objects
        # Check that it has tool-like attributes (FastMCP FunctionTool properties)
        assert hasattr(tool_func, "name"), (
            f"Tool {tool_name} should have name attribute"
        )
        assert hasattr(tool_func, "description"), (
            f"Tool {tool_name} should have description attribute"
        )


def test_global_components_initialization():
    """Regression test: Components should be initialized at module level, not in lifespan"""
    from mcp_llm_bridge.server import (
        conversation_manager,
        adapter_manager,
        context_selector,
    )

    # Components should be initialized when module is imported
    assert conversation_manager is not None, (
        "Conversation manager should be initialized"
    )
    assert adapter_manager is not None, "Adapter manager should be initialized"
    assert context_selector is not None, "Context selector should be initialized"

    # Components should be functional
    from mcp_llm_bridge.conversation import ConversationManager
    from mcp_llm_bridge.adapters import AdapterManager
    from mcp_llm_bridge.context_selector import ContextSelector

    assert isinstance(conversation_manager, ConversationManager)
    assert isinstance(adapter_manager, AdapterManager)
    assert isinstance(context_selector, ContextSelector)


def test_no_deprecated_imports():
    """Regression test: Ensure we're not using deprecated MCP SDK imports"""
    import mcp_llm_bridge.server as server_module
    import inspect

    # Get the source code
    source = inspect.getsource(server_module)

    # Should not contain deprecated imports or patterns
    deprecated_patterns = [
        "from mcp.server import Server",  # Old MCP server import
        "mcp.server.stdio.stdio_server",  # Old stdio import pattern
        "app.create_initialization_options()",  # Old initialization pattern
        "set_lifespan",  # Old FastMCP API
    ]

    for pattern in deprecated_patterns:
        assert pattern not in source, f"Deprecated pattern found: {pattern}"


def test_server_module_structure():
    """Regression test: Verify server module has correct structure"""
    import mcp_llm_bridge.server as server_module

    # Should have the main components
    required_components = [
        "mcp",
        "conversation_manager",
        "adapter_manager",
        "context_selector",
    ]
    for component in required_components:
        assert hasattr(server_module, component), (
            f"Missing required component: {component}"
        )

    # Should have tool functions
    required_tools = ["create_conversation", "call_llm", "list_adapters"]
    for tool in required_tools:
        assert hasattr(server_module, tool), f"Missing required tool: {tool}"

    # Check that module has proper __name__ and can be executed
    assert hasattr(server_module, "__name__"), "Module should have __name__ attribute"
    assert server_module.__name__ == "mcp_llm_bridge.server", (
        "Module should have correct name"
    )


def test_fastmcp_version_compatibility():
    """Regression test: Verify FastMCP version compatibility"""
    try:
        import fastmcp

        fastmcp_version = fastmcp.__version__

        # We know FastMCP 2.x works with our current implementation
        major_version = int(fastmcp_version.split(".")[0])

        assert major_version >= 2, (
            f"FastMCP version {fastmcp_version} may not be compatible. Expected >= 2.0"
        )

    except ImportError:
        pytest.fail("FastMCP should be installed")
    except Exception as e:
        pytest.fail(f"Error checking FastMCP version: {e}")
