#!/usr/bin/env python3
"""Simple test client for the MCP LLM Bridge server"""

import asyncio
import json
import subprocess
import sys


async def test_mcp_server():
    """Test the MCP server by sending JSON-RPC messages"""

    # Start the server process
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_llm_bridge.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        # Send request
        request_str = json.dumps(init_request) + "\n"
        server_proc.stdin.write(request_str)
        server_proc.stdin.flush()

        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print("✅ Initialize response:")
            print(json.dumps(response, indent=2))

        # Send list_tools request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        request_str = json.dumps(tools_request) + "\n"
        server_proc.stdin.write(request_str)
        server_proc.stdin.flush()

        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print("\n✅ Tools list response:")
            tools = response.get("result", {}).get("tools", [])
            print(f"Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")

        # Test create_conversation
        create_conv_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_conversation",
                "arguments": {
                    "initial_message": "Hello, this is a test conversation!",
                    "topic": "Testing MCP Server",
                },
            },
        }

        request_str = json.dumps(create_conv_request) + "\n"
        server_proc.stdin.write(request_str)
        server_proc.stdin.flush()

        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print("\n✅ Create conversation response:")
            result = response.get("result", {})
            if result and "content" in result and result["content"]:
                content = result["content"][0]
                print(f"Status: {content['text']}")

        # Test list_adapters
        list_adapters_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "list_adapters", "arguments": {}},
        }

        request_str = json.dumps(list_adapters_request) + "\n"
        server_proc.stdin.write(request_str)
        server_proc.stdin.flush()

        # Read response
        response_line = server_proc.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print("\n✅ List adapters response:")
            result = response.get("result", {})
            if result and "content" in result and result["content"]:
                content = result["content"][0]
                adapters_info = json.loads(content["text"])
                print(f"Default adapter: {adapters_info.get('default_adapter')}")
                print(f"Available adapters: {len(adapters_info.get('adapters', []))}")
                for adapter in adapters_info.get("adapters", []):
                    print(f"  - {adapter['name']}: {adapter['description']}")

        print("\n🎉 All tests completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        # Print any stderr output
        _, stderr_output = server_proc.communicate(timeout=1)
        if stderr_output:
            print(f"Server stderr: {stderr_output}")

    finally:
        # Clean up
        try:
            server_proc.terminate()
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
