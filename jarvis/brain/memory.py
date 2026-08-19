"""Short-term memory: last N commands + intents for pronoun resolution."""
from collections import deque

from config import settings


class Memory:
    def __init__(self, maxlen: int = settings.CONTEXT_WINDOW):
        self.history = deque(maxlen=maxlen)

    def add(self, command: str, intent: dict) -> None:
        self.history.append({"command": command, "intent": intent})

    def last_intent(self) -> dict | None:
        return self.history[-1]["intent"] if self.history else None

    def last_target(self) -> str | None:
        """Most recent non-empty target — what "it"/"that" refers to."""
        for item in reversed(self.history):
            target = item["intent"].get("target")
            if target:
                return target
        return None

    def context_lines(self) -> list[str]:
        """Render history for the LLM prompt."""
        return [
            f'- "{h["command"]}" -> {h["intent"].get("action")} {h["intent"].get("target") or ""}'.strip()
            for h in self.history
        ]


# Module-level singleton shared by interpreter + main loop.
memory = Memory()
