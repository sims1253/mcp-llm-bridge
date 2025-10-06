"""Context selection - decides which messages to include in history"""

from typing import Any



class ContextSelector:
    """Selects conversation history based on context mode"""

    def select(self, messages: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
        """
        Select messages based on context mode

        Args:
            messages: Full conversation history
            mode: Context mode (full, recent, smart, minimal, none)

        Returns:
            Selected messages
        """
        if mode == "none":
            return []
        elif mode == "minimal":
            return messages[-1:] if messages else []
        elif mode == "recent":
            return messages[-10:] if len(messages) > 10 else messages
        elif mode == "smart":
            return self._smart_select(messages)
        elif mode == "full":
            return messages
        else:
            raise ValueError(f"Unknown context mode: {mode}")

    def _smart_select(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Smart selection algorithm:
        - Always include first message (initial question)
        - Include last 5 messages (current context)
        - Total: up to 6 messages
        """
        if len(messages) <= 6:
            return messages

        # First message + last 5
        selected = [messages[0]]
        selected.extend(messages[-5:])

        return selected
