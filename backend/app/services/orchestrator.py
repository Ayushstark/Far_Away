from agents.registry import AGENTS
from backend.app.schemas import AgentResult, ChatResponse
from memory.store import HealthMemory


class Orchestrator:
    def __init__(self) -> None:
        self.memory = HealthMemory()

    async def run(self, message: str, profile_id: str) -> ChatResponse:
        selected = [agent for agent in AGENTS if agent.matches(message)]
        if not selected:
            selected = [AGENTS[0], AGENTS[3]]

        emergency_agent = AGENTS[-1]
        if emergency_agent not in selected:
            selected.append(emergency_agent)

        context = self.memory.recall(profile_id, message)
        results = [
            AgentResult(agent=agent.name, summary=await agent.run(message, context))
            for agent in selected
        ]
        emergency = emergency_agent.is_emergency(message)

        self.memory.remember(profile_id, message, {"type": "user_message"})
        response_text = "\n\n".join(result.summary for result in results)
        if emergency:
            response_text = (
                "This may be an emergency. Call local emergency services now "
                "(112 in India, 911 in the US) and do not wait for this app.\n\n"
                + response_text
            )

        return ChatResponse(
            message=response_text,
            agents_used=[agent.name for agent in selected],
            results=results,
            emergency=emergency,
        )

