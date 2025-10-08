"""Conversation management - handles JSON file I/O for conversation history"""

import json
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
        """Get path to conversation JSON file"""
        safe_id = self._sanitize_id(conversation_id)
        return self.conversation_dir / f"{safe_id}.json"

    def _get_metadata_path(self, conversation_id: str) -> Path:
        """Get path to conversation metadata file"""
        safe_id = self._sanitize_id(conversation_id)
        return self.metadata_dir / f"{safe_id}.json"

    def conversation_exists(self, conversation_id: str) -> bool:
        """Check if conversation exists"""
        return self._get_conversation_path(conversation_id).exists()

    def create_conversation(
        self,
        conversation_id: str | None = None,
        initial_message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new conversation

        Args:
            conversation_id: Optional ID, auto-generated if not provided
            initial_message: First message in the conversation
            metadata: Optional metadata dict

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

        # Initialize empty conversation file
        conv_path = self._get_conversation_path(sanitized_id)
        with open(conv_path, "w", encoding="utf-8") as f:
            json.dump([], f)
            f.write("\n")

        # Add initial message if provided
        if initial_message:
            self.append_message(
                conversation_id=sanitized_id,
                speaker="user",
                content=initial_message,
                metadata={},
            )

        # Create metadata
        meta = {
            "id": sanitized_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "participants": ["user"] if initial_message else [],
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
        conv_path = self._get_conversation_path(conversation_id)

        # Read existing messages
        messages = self.read_messages(conversation_id)

        # Create message entry
        message = {
            "turn": len(messages) + 1,
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        # Append to messages array
        messages.append(message)

        # Write entire array back
        with open(conv_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
            f.write("\n")

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
        conv_path = self._get_conversation_path(conversation_id)

        if not conv_path.exists():
            return []

        with open(conv_path, encoding="utf-8") as f:
            messages = json.load(f)

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

        for conv_file in self.conversation_dir.glob("*.json"):
            conv_id = conv_file.stem
            metadata = self.get_metadata(conv_id)
            conversations.append(metadata)

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
