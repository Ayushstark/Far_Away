import re

from agents.care_coordinator import create_care_brief, specialist_advice
from agents.emergency import assess_emergency, emergency_response
from agents.medication import MedicationManager
from agents.symptom import analyze_symptoms
from backend.app.schemas import AgentResult, ChatResponse, EmergencyAssessment, IntentName
from backend.app.services.emergency_notifier import EmergencyNotifier
from backend.app.services.language import wants_hindi
from backend.app.services.input_understanding import IntentExtraction, extract_intent
from backend.app.services.response_merger import merge_responses
from memory.store import HealthMemory

CASUAL_MESSAGES = {
    "hi",
    "hello",
    "hey",
    "hii",
    "hiii",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
    "how are you",
    "hello how are you",
    "hi how are you",
    "what can you do",
    "who are you",
    "okay",
    "ok",
    "bye",
}

RECURRING_PATTERN = re.compile(
    r"\b(again|every|recurring|repeated|keeps happening|keeps coming|wapas|phir|baar baar|bar bar|फिर|बार बार)\b",
    re.IGNORECASE,
)
HIGH_SEVERITY_TERMS = (
    "severe", "unbearable", "worst", "very intense", "can't walk", "cannot walk",
    "बहुत तेज", "असहनीय",
)
MODERATE_SEVERITY_TERMS = (
    "moderate", "persistent", "keeps", "again", "every day", "worse",
    "लगातार", "बार बार", "फिर", "बढ़",
)
RESOLVED_FOLLOW_UP_TERMS = (
    "better", "fine now", "gone", "resolved", "no pain", "stopped",
    "theek", "thik", "ठीक", "बेहतर", "अब नहीं",
)
CLEAR_RESOLVED_FOLLOW_UP_TERMS = (
    "fine now", "gone", "resolved", "no pain", "stopped", "completely better",
    "theek ho gaya", "thik ho gaya", "ठीक हो गया", "अब दर्द नहीं", "पूरी तरह बेहतर",
)
ONGOING_FOLLOW_UP_TERMS = (
    "still", "same", "worse", "hurts", "pain", "not better",
    "abhi bhi", "same hai", "अभी भी", "वैसा", "बदतर", "दर्द",
)


def symptom_severity(message: str) -> str:
    lowered = message.lower()
    if any(term in lowered for term in HIGH_SEVERITY_TERMS):
        return "high"
    if any(term in lowered for term in MODERATE_SEVERITY_TERMS):
        return "moderate"
    return "none"


def follow_up_outcome(message: str) -> str | None:
    lowered = message.lower()
    if any(term in lowered for term in CLEAR_RESOLVED_FOLLOW_UP_TERMS):
        return "resolved"
    if any(term in lowered for term in ONGOING_FOLLOW_UP_TERMS):
        return "ongoing"
    if any(term in lowered for term in RESOLVED_FOLLOW_UP_TERMS):
        return "resolved"
    return None


def is_follow_up_question(message: str) -> bool:
    lowered = message.lower()
    return any(
        phrase in lowered
        for phrase in (
            "better, worse, or about the same",
            "how are you feeling now",
            "how is your",
            "बेहतर, बदतर या पहले जैसे",
            "अब आप कैसा महसूस",
        )
    )


def is_casual_message(message: str) -> bool:
    normalized = " ".join(
        message.strip().lower().translate(str.maketrans("", "", "!?.,")).split()
    )
    for token in ("reply in hindi", "respond in hindi", "hindi mein", "hindi me"):
        normalized = normalized.replace(token, "").strip()
    return normalized in CASUAL_MESSAGES


def casual_response(message: str) -> str:
    if wants_hindi(message):
        return "नमस्ते! मैं ठीक हूँ। आज मैं आपकी स्वास्थ्य संबंधी किस तरह सहायता कर सकता हूँ?"
    return "Hello! I am doing well. How can I help you today?"


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
        preferred_language: str = "en",
        extraction: IntentExtraction | None = None,
        emergency_assessment: EmergencyAssessment | None = None,
        previous_assistant_message: str | None = None,
        conversation_history: list[str] | None = None,
        follow_up_event_id: str | None = None,
        memory_profile_id: str | None = None,
    ) -> ChatResponse:
        memory_id = memory_profile_id or profile_id
        # Emergency screening always runs first and can short-circuit all other work.
        emergency = emergency_assessment or await assess_emergency(message)
        if emergency.is_emergency:
            emergency.family_notified = self.emergency_notifier.notify_family(
                profile_id,
                message,
                emergency,
            )
            self.memory.remember(
                memory_id,
                message,
                {"type": "emergency_message", "severity": emergency.severity},
            )
            alert = emergency_response(emergency, preferred_language)
            return ChatResponse(
                message=alert,
                intents=["emergency_detection"],
                agents_used=["emergency_detector"],
                results=[AgentResult(agent="emergency_detector", summary=alert)],
                emergency=True,
                emergency_details=emergency,
                severity="high",
            )

        outcome = (
            follow_up_outcome(message)
            if follow_up_event_id
            and previous_assistant_message
            and is_follow_up_question(previous_assistant_message)
            else None
        )
        if outcome:
            if outcome == "resolved":
                reply = (
                    "यह सुनकर अच्छा लगा कि अब आप बेहतर हैं। मैं इस लक्षण को ठीक हुआ दर्ज कर रहा हूँ; दोबारा होने पर CareOS या डॉक्टर को बताएँ।"
                    if preferred_language == "hi"
                    else "I am glad you are feeling better. I will mark this symptom as resolved; tell CareOS or your doctor if it returns."
                )
            else:
                routed_follow_up = (
                    f"{message}\n\nThe symptom is ongoing. Continue the assessment "
                    "proactively using OPQRST / OLD CART. Ask the most important "
                    "missing questions and provide a cautious differential. "
                    f"Previous CareOS question: {previous_assistant_message}"
                )
                if preferred_language == "hi":
                    routed_follow_up += "\n\nReply entirely in fluent Hindi using Devanagari."
                reply = await analyze_symptoms(
                    routed_follow_up,
                    [health_history or "No additional health history available."],
                )
            return ChatResponse(
                message=reply,
                intents=["symptom_analysis"],
                agents_used=(
                    ["emergency_detector", "care_coordinator"]
                    if outcome == "resolved"
                    else ["emergency_detector", "symptom_analyst", "care_coordinator"]
                ),
                steps_taken=(
                    ["Updating your health timeline"]
                    if outcome == "resolved"
                    else ["Updating your health timeline", "Running OPQRST assessment"]
                ),
                results=(
                    [AgentResult(agent="care_coordinator", summary=reply)]
                    if outcome == "resolved"
                    else [
                        AgentResult(agent="symptom_analyst", summary=reply),
                        AgentResult(agent="care_coordinator", summary="Follow-up outcome recorded."),
                    ]
                ),
                severity="none" if outcome == "resolved" else "moderate",
                follow_up_outcome=outcome,
            )

        understood = extraction or await extract_intent(message, conversation_history)
        if understood.primary_intent == "language_request":
            return ChatResponse(
                message="हाँ, बिल्कुल। मैं आपसे हिंदी में बात कर सकता हूँ। आप क्या जानना चाहते हैं?",
                intents=[],
                agents_used=["emergency_detector"],
                results=[],
            )

        if understood.primary_intent == "casual" or is_casual_message(message):
            return ChatResponse(
                message=casual_response(
                    f"{message} हिंदी" if preferred_language == "hi" else message
                ),
                intents=[],
                agents_used=["emergency_detector"],
                results=[],
            )

        if understood.primary_intent == "unclear" or understood.needs_clarification:
            if understood.normalized_query == "Dashboard summary card text, not a user care question.":
                return ChatResponse(
                    message="That looks like a CareOS summary card, not a question. Please type what you want to know about it.",
                    intents=[],
                    agents_used=["emergency_detector"],
                    results=[],
                )
            return ChatResponse(
                message=(
                    "मैं आपकी बात सही तरह समझना चाहता हूँ। क्या आप किसी लक्षण, दवा, मेडिकल रिपोर्ट या डॉक्टर से मिलने के बारे में पूछ रहे हैं?"
                    if preferred_language == "hi"
                    else "I want to make sure I understand correctly. Are you asking about a symptom, medicine, medical report, or doctor visit?"
                ),
                intents=[],
                agents_used=["emergency_detector"],
                results=[],
            )

        history = [health_history] if health_history else self.memory.recall(memory_id, message)
        intents = list(understood.intents)
        actionable = [intent for intent in intents if intent != "emergency_detection"]
        if not actionable:
            return ChatResponse(
                message=(
                    "कृपया अपनी स्वास्थ्य संबंधी चिंता के बारे में थोड़ी और जानकारी दें, ताकि मैं सही CareOS एजेंट चुन सकूँ।"
                    if preferred_language == "hi"
                    else "Please share a little more detail about the health concern so I can choose the right care agent."
                ),
                intents=[],
                agents_used=["emergency_detector"],
                results=[],
            )

        results: list[AgentResult] = []
        steps_taken: list[str] = []
        severity = "none"
        routed_message = (
            f"{message}\n\nPlease reply in fluent Hindi."
            if preferred_language == "hi" and not wants_hindi(message)
            else message
        )
        routed_message += f"\n\nInterpreted user meaning: {understood.normalized_query}"
        if conversation_history:
            routed_message += "\n\nRecent conversation context:\n" + "\n".join(conversation_history[-6:])
        for intent in actionable:
            result = await self._run_intent(
                intent,
                routed_message,
                profile_id,
                history,
                current_medications or [],
                preferred_language,
                memory_id,
            )
            if result:
                results.append(result)
                steps_taken.append(
                    {
                        "symptom_analysis": "Analyzing symptoms",
                        "report_reading": "Reviewing report request",
                        "medication_management": "Checking medications",
                        "care_coordination": "Coordinating care",
                    }[intent]
                )

        if "symptom_analysis" in actionable:
            severity = symptom_severity(message)
            if severity in {"high", "moderate"} and current_medications:
                results.append(
                    AgentResult(
                        agent="medication_manager",
                        summary=await self.medication_manager.run(
                            "side_effects",
                            {
                                "symptom": routed_message,
                                "current_medications": current_medications,
                            },
                            profile_id,
                        ),
                    )
                )
                steps_taken.append("Checking your medications")
            if RECURRING_PATTERN.search(message):
                results.append(
                    AgentResult(
                        agent="care_coordinator",
                        summary=await specialist_advice(
                            routed_message,
                            "\n".join(history),
                            preferred_language,
                        ),
                    )
                )
                steps_taken.append("Finding the right specialist")

        self.memory.remember(memory_id, message, {"type": "user_message"})
        merged = await merge_responses(results, preferred_language)
        return ChatResponse(
            message=merged,
            intents=intents,
            agents_used=["emergency_detector", *[result.agent for result in results]],
            steps_taken=steps_taken,
            results=results,
            severity=severity,
        )

    async def _run_intent(
        self,
        intent: IntentName,
        message: str,
        profile_id: str,
        history: list[str],
        current_medications: list[dict],
        preferred_language: str,
        memory_profile_id: str,
    ) -> AgentResult | None:
        if intent == "symptom_analysis":
            return AgentResult(
                agent="symptom_analyst",
                summary=await analyze_symptoms(message, history),
            )
        if intent == "report_reading":
            return AgentResult(
                agent="report_reader",
                summary=(
                    "पूरी व्याख्या के लिए कृपया रिपोर्ट स्क्रीन से PDF अपलोड करें।"
                    if preferred_language == "hi"
                    else "Please upload the PDF report using the report endpoint for a full interpretation."
                ),
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
                    memory_profile_id,
                    self.memory,
                    health_history="\n".join(history),
                    current_medications=current_medications,
                    preferred_language=preferred_language,
                ),
            )
        return None
