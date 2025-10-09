"""Adapter management - configurable LLM execution system"""

import json
import os
import asyncio
import time
from pathlib import Path
from typing import Any


class AdapterConfig:
    """Configuration for a single adapter"""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.type = config["type"]
        self.description = config.get("description", "")
        self.config = config


class AdapterManager:
    """Manages and executes LLM adapters"""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path).expanduser()
        self.adapters: dict[str, AdapterConfig] = {}
        self.default_adapter: str | None = None
        self.default_summarization_adapter: str | None = None
        self.load_adapters()

    def load_adapters(self) -> None:
        """Load adapter configurations from JSON file"""
        if not self.config_path.exists():
            self._create_default_config()

        with open(self.config_path, encoding="utf-8") as f:
            config = json.load(f)

        # Load adapters
        for name, adapter_config in config.get("adapters", {}).items():
            self.adapters[name] = AdapterConfig(name, adapter_config)

        # Load default adapters
        self.default_adapter = config.get("default_adapter")
        self.default_summarization_adapter = config.get("default_summarization_adapter")

    def _create_default_config(self) -> None:
        """Create default adapter configuration file"""
        default_config = {
            "adapters": {
                "example-bash": {
                    "type": "bash",
                    "command": "echo",
                    "args": ["Example adapter - configure with your actual LLM CLI"],
                    "input_method": "stdin",
                    "description": "Example adapter - edit ~/.mcp-llm-bridge/adapters.json",
                }
            },
            "default_adapter": "example-bash",
            "default_summarization_adapter": "example-bash",
            "_comment": "Edit this file to configure your LLM adapters. See examples in documentation.",
        }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)

    async def call_adapter(
        self,
        adapter_name: str,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        pass_history: bool = True,
    ) -> dict[str, Any]:
        """
        Call an adapter with a message

        Args:
            adapter_name: Name of adapter to call
            message: Message to send
            conversation_history: Optional conversation history
            pass_history: Whether to pass history to adapter

        Returns:
            {
                "response": str,
                "metadata": {
                    "adapter": str,
                    "exit_code": int,
                    "execution_time_ms": int,
                    "error": str | None
                }
            }
        """
        adapter = self.adapters.get(adapter_name)
        if not adapter:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        if adapter.type == "bash":
            return await self._call_bash_adapter(
                adapter, message, conversation_history, pass_history
            )
        else:
            raise ValueError(f"Unsupported adapter type: {adapter.type}")

    async def _call_bash_adapter(
        self,
        adapter: AdapterConfig,
        message: str,
        conversation_history: list[dict[str, Any]] | None,
        pass_history: bool,
    ) -> dict[str, Any]:
        """Execute bash command adapter"""
        config = adapter.config
        command = config["command"]
        args = config.get("args", [])
        input_method = config.get("input_method", "stdin")
        env = {**os.environ, **config.get("env", {})}
        timeout = config.get("timeout_seconds", 300)
        working_dir = config.get("working_dir")

        # Build command
        full_command = [command]

        # Handle message placement
        if input_method == "arg":
            # Message goes in args
            processed_args = []
            message_added = False

            for arg in args:
                if "{message}" in arg:
                    processed_args.append(arg.replace("{message}", message))
                    message_added = True
                else:
                    processed_args.append(arg)

            # If no template found and message is not empty, append message at end
            if not message_added and message:
                processed_args.append(message)

            full_command.extend(processed_args)
            stdin_input = None
        else:
            # Message goes to stdin
            full_command.extend(args)
            stdin_input = message

        # Optionally prepend history
        if pass_history and conversation_history:
            history_text = self._format_history(conversation_history)
            if stdin_input:
                # Both history and message: prepend history
                stdin_input = f"{history_text} | {stdin_input}"
            else:
                # Only history, no message
                stdin_input = history_text

        # Execute command
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdin=asyncio.subprocess.PIPE if stdin_input else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=working_dir,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(
                    input=stdin_input.encode("utf-8") if stdin_input else None
                ),
                timeout=timeout,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            response = stdout.decode("utf-8").strip()
            error = stderr.decode("utf-8").strip() if stderr else None

            return {
                "response": response,
                "metadata": {
                    "adapter": adapter.name,
                    "exit_code": process.returncode,
                    "execution_time_ms": execution_time_ms,
                    "error": error if process.returncode != 0 else None,
                },
            }

        except asyncio.TimeoutError:
            return {
                "response": "",
                "metadata": {
                    "adapter": adapter.name,
                    "exit_code": -1,
                    "execution_time_ms": timeout * 1000,
                    "error": f"Command timed out after {timeout} seconds",
                },
            }

        except FileNotFoundError:
            return {
                "response": "",
                "metadata": {
                    "adapter": adapter.name,
                    "exit_code": -1,
                    "execution_time_ms": 0,
                    "error": f"Command not found: {command}",
                },
            }

        except Exception as e:
            return {
                "response": "",
                "metadata": {
                    "adapter": adapter.name,
                    "exit_code": -1,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "error": str(e),
                },
            }

    def _format_history(self, history: list[dict[str, Any]]) -> str:
        """Format conversation history in compact format"""
        if not history:
            return ""

        lines = []
        for msg in history:
            speaker = msg.get("speaker", "unknown")
            content = msg.get("content", "").replace("\n", " ")
            lines.append(f"{speaker}: {content}")

        return " | ".join(lines)

    def list_adapters(self) -> dict[str, Any]:
        """List all configured adapters"""
        return {
            "adapters": [
                {
                    "name": name,
                    "type": adapter.type,
                    "description": adapter.description,
                    "command": adapter.config.get("command", "N/A"),
                }
                for name, adapter in self.adapters.items()
            ],
            "default_adapter": self.default_adapter,
            "default_summarization_adapter": self.default_summarization_adapter,
            "config_path": str(self.config_path),
        }

    async def test_adapter(self, adapter_name: str) -> bool:
        """Test if an adapter is available"""
        adapter = self.adapters.get(adapter_name)
        if not adapter:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        if adapter.type == "bash":
            command = adapter.config["command"]

            # Check if command exists using 'which' or 'where'
            check_command = "where" if os.name == "nt" else "which"

            try:
                result = await asyncio.create_subprocess_exec(
                    check_command,
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await result.wait()
                return result.returncode == 0
            except Exception:
                return False

        raise ValueError(f"Unsupported adapter type: {adapter.type}")
