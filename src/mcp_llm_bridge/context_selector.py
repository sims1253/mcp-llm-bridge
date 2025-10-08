"""Context selection - decides which messages to include in history"""

from typing import Any


class ContextSelector:
    """Selects conversation history based on context mode"""

    def select(
        self,
        messages: list[dict[str, Any]],
        mode: str,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Select messages based on context mode

        Args:
            messages: Full conversation history
            mode: Context mode (full, recent, smart, minimal, none)
            max_tokens: Optional maximum token limit

        Returns:
            Selected messages
        """
        if mode == "none":
            return []
        elif mode == "minimal":
            selected = messages[-1:] if messages else []
        elif mode == "recent":
            selected = messages[-10:] if len(messages) > 10 else messages
        elif mode == "smart":
            selected = self._smart_select(messages)
        elif mode == "full":
            selected = messages
        else:
            raise ValueError(f"Unknown context mode: {mode}")

        # Apply token limit if specified
        if max_tokens is not None:
            selected = self._apply_token_limit(selected, max_tokens, mode)

        return selected

    def _smart_select(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Smart selection algorithm:
        - If conversation is short (< 10 messages), include all
        - Otherwise: include first message (initial question) + last 5 messages
        - Total: up to 6 messages for long conversations
        """
        if len(messages) < 10:
            return messages

        # First message + last 5
        selected = [messages[0]]
        selected.extend(messages[-5:])

        return selected

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        Estimate token count for messages (approximately 4 chars per token)

        Args:
            messages: List of message dicts

        Returns:
            Estimated token count
        """
        if not messages:
            return 0

        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            speaker = msg.get("speaker", "")
            # Count content + speaker name + formatting overhead
            total_chars += len(content) + len(speaker) + 4  # ": " and newlines

        # Rough estimation: 4 characters per token
        return total_chars // 4

    def _apply_token_limit(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        mode: str,
    ) -> list[dict[str, Any]]:
        """
        Trim messages to fit within token limit

        Args:
            messages: Selected messages
            max_tokens: Maximum token limit
            mode: Context mode (used to determine trimming strategy)

        Returns:
            Messages that fit within token limit
        """
        if not messages:
            return messages

        # Check if already within limit
        if self.estimate_tokens(messages) <= max_tokens:
            return messages

        # Trim from appropriate end based on mode
        if mode == "smart" and len(messages) > 1:
            # For smart mode, keep first message and trim from middle
            first_msg = messages[0]
            remaining = messages[1:]

            # Try to keep as many recent messages as possible
            for i in range(len(remaining), 0, -1):
                candidate = [first_msg] + remaining[-i:]
                if self.estimate_tokens(candidate) <= max_tokens:
                    return candidate

            # If even first + last doesn't fit, just return last messages
            for i in range(len(messages), 0, -1):
                candidate = messages[-i:]
                if self.estimate_tokens(candidate) <= max_tokens:
                    return candidate
        else:
            # For other modes, trim from the front (keep most recent)
            for i in range(len(messages), 0, -1):
                candidate = messages[-i:]
                if self.estimate_tokens(candidate) <= max_tokens:
                    return candidate

        # If even one message is too large, return empty list
        return []
