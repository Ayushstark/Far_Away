from backend.app.schemas import IntentName
from backend.app.services.llm import complete_json

INTENT_KEYWORDS: dict[IntentName, tuple[str, ...]] = {
    "symptom_analysis": (
        "pain", "fever", "cough", "symptom", "feel", "sick", "headache",
        "vomit", "rash", "dizzy", "weak",
    ),
    "report_reading": ("report", "lab", "blood test", "pdf", "scan", "result"),
    "medication_management": (
        "medicine", "medication", "tablet", "dose", "prescription", "pill", "drug",
    ),
    "care_coordination": (
        "doctor", "specialist", "appointment", "brief", "next step", "care",
    ),
    "emergency_detection": (
        "emergency", "chest pain", "can't breathe", "cannot breathe", "unconscious",
        "severe bleeding", "stroke", "overdose", "poison",
    ),
}


def classify_intent_fallback(message: str) -> list[IntentName]:
    text = message.lower()
    intents = [
        intent
        for intent, keywords in INTENT_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    return intents or ["symptom_analysis"]


async def classify_intent(message: str) -> list[IntentName]:
    fallback = classify_intent_fallback(message)
    result = await complete_json(
        "You classify healthcare requests for a multi-agent assistant.",
        f"""
User said: {message!r}

Classify into one or more of:
- symptom_analysis
- report_reading
- medication_management
- care_coordination
- emergency_detection

Return a JSON list only.
""",
        fallback,
    )
    valid = set(INTENT_KEYWORDS)
    if not isinstance(result, list):
        return fallback
    intents = [item for item in result if item in valid]
    return list(dict.fromkeys(intents)) or fallback
