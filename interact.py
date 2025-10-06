#!/usr/bin/env python3
"""Interactive script to manually test MCP server tools"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path


async def send_jsonrpc_request(proc, request):
    """Send a JSON-RPC request and get response"""
    request_str = json.dumps(request) + "\n"
    proc.stdin.write(request_str)
    proc.stdin.flush()

    response_line = proc.stdout.readline()
    if response_line:
        return json.loads(response_line.strip())
    return None


async def interactive_session():
    """Interactive session with the MCP server"""
    print("🚀 Starting MCP LLM Bridge Interactive Session")
    print("=" * 60)

    # Start the server
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_llm_bridge.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        # Initialize
        print("\n📡 Initializing server...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "interactive-client", "version": "1.0.0"}
            }
        }

        response = await send_jsonrpc_request(proc, init_request)
        if response and "result" in response:
            print("✅ Server initialized successfully")
        else:
            print("❌ Failed to initialize server")
            return

        # List available tools
        print("\n🔧 Listing available tools...")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        response = await send_jsonrpc_request(proc, tools_request)
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            print(f"Found {len(tools)} tools:")
            for i, tool in enumerate(tools, 1):
                print(f"  {i}. {tool['name']}: {tool['description']}")

        # Interactive loop
        print("\n💬 Interactive Session (type 'quit' to exit)")
        print("Available commands:")
        print("  create <message>          - Create a new conversation")
        print("  list <conversation_id>    - List conversations")
        print("  adapters                 - List adapters")
        print("  call <conv_id> <adapter> <message> - Call an LLM")
        print("  recent <conv_id> [count] - Get recent messages")

        while True:
            try:
                user_input = input("\n👤 You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    break

                if user_input.startswith('create '):
                    message = user_input[7:]
                    await create_conversation(proc, message)

                elif user_input == 'adapters':
                    await list_adapters(proc)

                elif user_input.startswith('list'):
                    await list_conversations(proc)

                elif user_input.startswith('recent '):
                    parts = user_input.split()
                    conv_id = parts[1]
                    count = int(parts[2]) if len(parts) > 2 else 5
                    await get_recent_messages(proc, conv_id, count)

                elif user_input.startswith('call '):
                    parts = user_input.split(maxsplit=3)
                    if len(parts) >= 4:
                        conv_id, adapter_name, message = parts[1], parts[2], parts[3]
                        await call_llm(proc, conv_id, adapter_name, message)
                    else:
                        print("❌ Usage: call <conversation_id> <adapter_name> <message>")

                else:
                    print("❌ Unknown command. Try: create, adapters, list, recent, call, quit")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("\n👋 Session ended")


async def create_conversation(proc, message):
    """Create a new conversation"""
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "create_conversation",
            "arguments": {
                "initial_message": message
            }
        }
    }

    response = await send_jsonrpc_request(proc, request)
    if response and "result" in response:
        result = response["result"]
        if "content" in result and result["content"]:
            content = result["content"][0]["text"]
            data = json.loads(content)
            print(f"✅ {data['message']}")
            print(f"   Conversation ID: {data['conversation_id']}")
            return data["conversation_id"]
    return None


async def list_adapters(proc):
    """List available adapters"""
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "list_adapters",
            "arguments": {"test_availability": True}
        }
    }

    response = await send_jsonrpc_request(proc, request)
    if response and "result" in response:
        result = response["result"]
        if "content" in result and result["content"]:
            content = result["content"][0]["text"]
            data = json.loads(content)
            print(f"📊 Available adapters (default: {data.get('default_adapter')}):")
            for adapter in data.get("adapters", []):
                status = "✅" if adapter.get("available") else "❌"
                print(f"   {status} {adapter['name']}: {adapter['description']}")


async def list_conversations(proc):
    """List conversations"""
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "list_conversations",
            "arguments": {"limit": 10}
        }
    }

    response = await send_jsonrpc_request(proc, request)
    if response and "result" in response:
        result = response["result"]
        if "content" in result and result["content"]:
            content = result["content"][0]["text"]
            data = json.loads(content)
            print(f"💬 Found {data['total']} conversations:")
            for conv in data.get("conversations", []):
                print(f"   📁 {conv['id']} - {conv['message_count']} messages - {conv['updated_at']}")


async def get_recent_messages(proc, conv_id, count=5):
    """Get recent messages from a conversation"""
    request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "get_recent_messages",
            "arguments": {
                "conversation_id": conv_id,
                "count": count
            }
        }
    }

    response = await send_jsonrpc_request(proc, request)
    if response and "result" in response:
        result = response["result"]
        if "content" in result and result["content"]:
            messages = result["content"][0]["text"]
            print(f"📜 Recent messages from {conv_id}:")
            print(messages)


async def call_llm(proc, conv_id, adapter_name, message):
    """Call an LLM adapter"""
    request = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "call_llm",
            "arguments": {
                "conversation_id": conv_id,
                "adapter_name": adapter_name,
                "message": message
            }
        }
    }

    print(f"🤖 Calling {adapter_name}...")
    response = await send_jsonrpc_request(proc, request)
    if response and "result" in response:
        result = response["result"]
        if "content" in result and result["content"]:
            response_text = result["content"][0]["text"]
            print(f"🤖 {adapter_name}: {response_text}")
    elif response and "error" in response:
        print(f"❌ Error: {response['error']['message']}")


if __name__ == "__main__":
    asyncio.run(interactive_session())