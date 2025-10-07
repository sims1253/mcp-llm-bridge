#!/usr/bin/env python3
"""Simple test to verify the MCP server starts correctly"""

import subprocess
import sys
import time


def check_server_startup():
    """Test that the server starts without errors"""
    print("🚀 Testing MCP server startup...")

    try:
        # Start the server process
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_llm_bridge.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it a moment to start
        time.sleep(2)

        # Check if it's still running (no crash on startup)
        if proc.poll() is None:
            print("✅ Server started successfully!")
            proc.terminate()
            proc.wait(timeout=5)
            return True
        else:
            # Server exited, check for errors
            returncode = proc.poll()
            _, stderr = proc.communicate()
            print(f"❌ Server exited with code {returncode}")
            if stderr:
                print(f"Error: {stderr}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def check_import():
    """Test that the module can be imported"""
    print("📦 Testing module import...")

    try:
        from mcp_llm_bridge import server

        print("✅ Module imported successfully!")

        # Check components
        print(f"✅ Conversation manager: {type(server.conversation_manager).__name__}")
        print(f"✅ Adapter manager: {type(server.adapter_manager).__name__}")
        print(f"✅ Context selector: {type(server.context_selector).__name__}")
        print(f"✅ MCP server: {type(server.mcp).__name__}")

        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Running MCP LLM Bridge Tests")
    print("=" * 50)

    import_success = check_import()
    startup_success = check_server_startup()

    print("=" * 50)
    if import_success and startup_success:
        print("🎉 All tests passed! The MCP server is working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed.")
        sys.exit(1)
