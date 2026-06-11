from agents.care_coordinator import create_care_brief
from agents.emergency import assess_emergency, emergency_response
from agents.medication import MedicationManager
from agents.symptom import analyze_symptoms
from backend.app.schemas import AgentResult, ChatResponse, IntentName
from backend.app.services.intent_classifier import classify_intent
from backend.app.services.emergency_notifier import EmergencyNotifier
from backend.app.services.response_merger import merge_responses
from memory.store import HealthMemory


class Orchestrator:
    def __init__(
        self,
        memory: HealthMemory | None = None,
    ) -> None:
        self.memory = memory or HealthMemory()
        self.medication_manager = MedicationManager()
        self.emergency_notifier = EmergencyNotifier()

    async def run(
        self,
        message: str,
        profile_id: str,
        health_history: str | None = None,
        current_medications: list[dict] | None = None,
    ) -> ChatResponse:
        history = [health_history] if health_history else self.memory.recall(profile_id, message)

        # Emergency screening always runs first and can short-circuit all other work.
        emergency = await assess_emergency(message)
        if emergency.is_emergency:
            emergency.family_notified = self.emergency_notifier.notify_family(
                profile_id,
                message,
                emergency,
            )
            self.memory.remember(
                profile_id,
                message,
                {"type": "emergency_message", "severity": emergency.severity},
            )
            alert = emergency_response(emergency)
            return ChatResponse(
                message=alert,
                intents=["emergency_detection"],
                agents_used=["emergency_detector"],
                results=[AgentResult(agent="emergency_detector", summary=alert)],
                emergency=True,
                emergency_details=emergency,
            )

        intents = await classify_intent(message)
        actionable = [intent for intent in intents if intent != "emergency_detection"]
        if not actionable:
            actionable = ["symptom_analysis"]

        results: list[AgentResult] = []
        for intent in actionable:
            result = await self._run_intent(
                intent,
                message,
                profile_id,
                history,
                current_medications or [],
            )
            if result:
                results.append(result)

        self.memory.remember(profile_id, message, {"type": "user_message"})
        merged = await merge_responses(results)
        return ChatResponse(
            message=merged,
            intents=intents,
            agents_used=["emergency_detector", *[result.agent for result in results]],
            results=results,
        )

    async def _run_intent(
        self,
        intent: IntentName,
        message: str,
        profile_id: str,
        history: list[str],
        current_medications: list[dict],
    ) -> AgentResult | None:
        if intent == "symptom_analysis":
            return AgentResult(
                agent="symptom_analyst",
                summary=await analyze_symptoms(message, history),
            )
        if intent == "report_reading":
            return AgentResult(
                agent="report_reader",
                summary="Please upload the PDF report using the report endpoint for a full interpretation.",
            )
        if intent == "medication_management":
            return AgentResult(
                agent="medication_manager",
                summary=await self.medication_manager.run(
                    "explain",
                    {"drug": message, "current_medications": current_medications},
                    profile_id,
                ),
            )
        if intent == "care_coordination":
            return AgentResult(
                agent="care_coordinator",
                summary=await create_care_brief(
                    profile_id,
                    self.memory,
                    health_history="\n".join(history),
                    current_medications=current_medications,
                ),
            )
        return None
