"""Conversation management - handles JSONL file I/O for conversation history"""

import json
import os
import random
from pathlib import Path
from datetime import datetime
from typing import Any


class ConversationManager:
    """Manages conversation files and metadata"""

    def __init__(self, conversation_dir: Path):
        self.conversation_dir = Path(conversation_dir).expanduser()
        self.conversation_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.conversation_dir / ".metadata"
        self.metadata_dir.mkdir(exist_ok=True)

    def _sanitize_id(self, conversation_id: str) -> str:
        """
        Sanitize conversation ID to prevent path traversal
        Returns empty string if ID contains path separators or becomes empty after sanitization
        """
        # Reject IDs with path separators
        if "/" in conversation_id or "\\" in conversation_id or ".." in conversation_id:
            return ""

        # Filter to alphanumeric and safe characters
        safe_id = "".join(c for c in conversation_id if c.isalnum() or c in "-_")

        # Return empty if sanitization removed everything
        return safe_id if safe_id else ""

    def _get_conversation_path(self, conversation_id: str) -> Path:
        """Get path to conversation JSONL file"""
        safe_id = self._sanitize_id(conversation_id)
        return self.conversation_dir / f"{safe_id}.jsonl"

    def _get_metadata_path(self, conversation_id: str) -> Path:
        """Get path to conversation metadata file"""
        safe_id = self._sanitize_id(conversation_id)
        return self.metadata_dir / f"{safe_id}.json"

    def conversation_exists(self, conversation_id: str) -> bool:
        """Check if conversation exists (JSONL or legacy JSON)"""
        jsonl_path = self._get_conversation_path(conversation_id)
        if jsonl_path.exists():
            return True

        # Check for legacy .json file
        safe_id = self._sanitize_id(conversation_id)
        legacy_path = self.conversation_dir / f"{safe_id}.json"
        return legacy_path.exists()

    def create_conversation(
        self,
        conversation_id: str | None = None,
        initial_message: str = "",
        metadata: dict[str, Any] | None = None,
        host_name: str = "",
    ) -> str:
        """
        Create a new conversation

        Args:
            conversation_id: Optional ID, auto-generated if not provided
            initial_message: First message in the conversation
            metadata: Optional metadata dict
            host_name: Optional 2-word host identifier (e.g., "claude_moderator").
                      Will be prefixed with "host_". Defaults to "host" if not provided.

        Returns:
            conversation_id (empty string if sanitization fails)
        """
        # Generate ID if not provided
        if not conversation_id:
            # Use microseconds and random suffix to avoid collisions
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            random_suffix = random.randint(1000, 9999)
            conversation_id = f"conversation_{timestamp}_{random_suffix}"

        # Sanitize the ID
        sanitized_id = self._sanitize_id(conversation_id)
        if not sanitized_id:
            # Return empty string for invalid IDs (test expects this)
            return ""

        # Check if already exists
        if self.conversation_exists(sanitized_id):
            raise ValueError(f"Conversation {sanitized_id} already exists")

        # Initialize empty JSONL conversation file
        conv_path = self._get_conversation_path(sanitized_id)
        conv_path.touch()  # Create empty file

        # Add initial message if provided
        if initial_message:
            # Format host speaker name
            speaker = f"host_{host_name}" if host_name else "host"
            self.append_message(
                conversation_id=sanitized_id,
                speaker=speaker,
                content=initial_message,
                metadata={},
            )

        # Create metadata
        speaker = f"host_{host_name}" if host_name else "host"
        meta = {
            "id": sanitized_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "participants": [speaker] if initial_message else [],
            "message_count": 1 if initial_message else 0,
            "topic": metadata.get("topic", "") if metadata else "",
            "tags": metadata.get("tags", []) if metadata else [],
            "status": "active",
        }

        self._save_metadata(sanitized_id, meta)

        return sanitized_id

    def append_message(
        self,
        conversation_id: str,
        speaker: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Append a message to conversation file

        Args:
            conversation_id: Conversation identifier
            speaker: Who is speaking (e.g., "user", "gpt4", "claude")
            content: Message content
            metadata: Optional metadata (tokens, cost, etc.)
        """
        # Migrate legacy JSON if needed
        self._migrate_if_needed(conversation_id)

        conv_path = self._get_conversation_path(conversation_id)

        # Count existing messages to determine turn number
        message_count = self._count_messages(conversation_id)

        # Create message entry
        message = {
            "turn": message_count + 1,
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        # Append as single JSONL line
        with open(conv_path, "a", encoding="utf-8") as f:
            json.dump(message, f, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())  # Ensure durability

        # Update metadata
        self._update_metadata_on_append(conversation_id, speaker)

    def read_messages(
        self,
        conversation_id: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Read messages from conversation

        Args:
            conversation_id: Conversation identifier
            start: Starting message index (inclusive)
            end: Ending message index (exclusive)

        Returns:
            List of message dicts
        """
        # Migrate legacy JSON if needed
        self._migrate_if_needed(conversation_id)

        conv_path = self._get_conversation_path(conversation_id)

        if not conv_path.exists():
            return []

        messages = []
        with open(conv_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue

                try:
                    message = json.loads(line)
                    messages.append(message)
                except json.JSONDecodeError as e:
                    # Handle corrupted lines gracefully - log and skip
                    print(
                        f"Warning: Skipping corrupted line {line_num} in {conversation_id}: {e}"
                    )
                    continue

        # Apply slicing
        if start is not None or end is not None:
            return messages[start:end]

        return messages

    def get_metadata(self, conversation_id: str) -> dict[str, Any]:
        """Get conversation metadata"""
        meta_path = self._get_metadata_path(conversation_id)

        if not meta_path.exists():
            # Generate from conversation file
            return self._generate_metadata(conversation_id)

        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)

    def list_conversations(
        self, limit: int = 20, sort_by: str = "updated_at", order: str = "desc"
    ) -> list[dict[str, Any]]:
        """
        List all conversations

        Args:
            limit: Maximum number to return
            sort_by: Field to sort by (created_at, updated_at, message_count)
            order: Sort order (asc, desc)

        Returns:
            List of conversation metadata dicts
        """
        conversations = []
        seen_ids = set()

        # First, get all JSONL files
        for conv_file in self.conversation_dir.glob("*.jsonl"):
            conv_id = conv_file.stem
            seen_ids.add(conv_id)
            metadata = self.get_metadata(conv_id)
            conversations.append(metadata)

        # Also check for legacy JSON files that haven't been migrated yet
        for conv_file in self.conversation_dir.glob("*.json"):
            conv_id = conv_file.stem
            if conv_id not in seen_ids:
                # This is a legacy file that needs migration
                metadata = self.get_metadata(conv_id)
                conversations.append(metadata)
                seen_ids.add(conv_id)

        # Sort
        reverse = order == "desc"
        conversations.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

        return conversations[:limit]

    def _count_messages(self, conversation_id: str) -> int:
        """Count messages in conversation"""
        return len(self.read_messages(conversation_id))

    def _save_metadata(self, conversation_id: str, metadata: dict[str, Any]) -> None:
        """Save metadata to file"""
        meta_path = self._get_metadata_path(conversation_id)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _update_metadata_on_append(self, conversation_id: str, speaker: str) -> None:
        """Update metadata after appending a message"""
        metadata = self.get_metadata(conversation_id)

        # Update fields
        metadata["updated_at"] = datetime.now().isoformat()
        metadata["message_count"] = self._count_messages(conversation_id)

        # Add speaker to participants if new
        if speaker not in metadata["participants"]:
            metadata["participants"].append(speaker)

        self._save_metadata(conversation_id, metadata)

    def _generate_metadata(self, conversation_id: str) -> dict[str, Any]:
        """Generate metadata from conversation file"""
        # Note: This calls read_messages which will trigger migration if needed
        messages = self.read_messages(conversation_id)

        if not messages:
            return {
                "id": conversation_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "participants": [],
                "message_count": 0,
                "topic": "",
                "status": "active",
            }

        participants = list(set(msg["speaker"] for msg in messages))

        metadata = {
            "id": conversation_id,
            "created_at": messages[0]["timestamp"],
            "updated_at": messages[-1]["timestamp"],
            "participants": participants,
            "message_count": len(messages),
            "topic": messages[0].get("content", "")[:100],  # First 100 chars
            "status": "active",
        }

        self._save_metadata(conversation_id, metadata)

        return metadata

    def _migrate_if_needed(self, conversation_id: str) -> None:
        """
        Migrate legacy .json file to .jsonl format if needed.
        Creates backup as .json.bak
        """
        safe_id = self._sanitize_id(conversation_id)
        legacy_path = self.conversation_dir / f"{safe_id}.json"
        jsonl_path = self._get_conversation_path(conversation_id)

        # If JSONL file exists, no migration needed
        if jsonl_path.exists():
            return

        # If legacy JSON doesn't exist, nothing to migrate
        if not legacy_path.exists():
            return

        # Read legacy JSON file
        try:
            with open(legacy_path, encoding="utf-8") as f:
                messages = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to read legacy file {legacy_path}: {e}")
            return

        # Write to JSONL format
        try:
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for message in messages:
                    json.dump(message, f, ensure_ascii=False)
                    f.write("\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            print(f"Warning: Failed to write JSONL file {jsonl_path}: {e}")
            return

        # Backup original as .json.bak
        backup_path = self.conversation_dir / f"{safe_id}.json.bak"
        try:
            legacy_path.rename(backup_path)
        except OSError as e:
            print(f"Warning: Failed to create backup {backup_path}: {e}")
            # Don't fail migration if backup fails
