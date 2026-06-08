from dataclasses import dataclass
from typing import Literal

from backend.app.schemas import AgentName
from backend.app.services.llm import complete


@dataclass(frozen=True)
class HealthcareAgent:
    name: AgentName
    purpose: str
    keywords: tuple[str, ...]
    emergency_keywords: tuple[str, ...] = ()

    def matches(self, message: str) -> bool:
        text = message.lower()
        return any(keyword in text for keyword in self.keywords)

    def is_emergency(self, message: str) -> bool:
        text = message.lower()
        return any(keyword in text for keyword in self.emergency_keywords)

    async def run(self, message: str, context: list[str]) -> str:
        system = (
            f"You are the JARVIS {self.name.replace('_', ' ')}. {self.purpose} "
            "Be cautious, concise, and never claim to diagnose. Ask for missing "
            "details and recommend professional care when appropriate."
        )
        memory = "\n".join(context) if context else "No relevant health memory."
        return await complete(system, f"Relevant memory:\n{memory}\n\nUser:\n{message}")

