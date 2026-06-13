import re
from dataclasses import dataclass
from typing import Literal

from backend.app.schemas import IntentName
from backend.app.services.language import wants_hindi
from backend.app.services.llm import complete_json


RouteIntent = Literal[
    "casual",
    "language_request",
    "symptom_analysis",
    "report_reading",
    "medication_management",
    "care_coordination",
    "unclear",
]
DetectedLanguage = Literal["en", "hi", "hinglish"]

CASUAL_PATTERNS = (
    r"^(hi+|hello|hey|namaste)[!.? ]*$",
    r"^(hi+|hello|hey)[, ]+(how are you|what can you do)[?.! ]*$",
    r"^(aap|ap|tum)\s+kaise\s+(ho|hain|hai)[?.! ]*$",
    r"^(how are you|who are you|what can you do)[?.! ]*$",
    r"^(thanks|thank you|shukriya|dhanyavad|ok|okay|bye)[!.? ]*$",
    r"^(नमस्ते|हैलो|हाय|आप कैसे हैं|तुम कैसे हो)[?।!. ]*$",
)
LANGUAGE_PATTERNS = (
    r"\b(can|could|will|would)\s+(we|you)\s+(talk|speak|reply|respond)\s+in\s+hindi\b",
    r"\b(reply|respond|talk|speak)\s+in\s+hindi\b",
    r"\bhindi\s+(mein|me)\s+(baat|bolo|boliye|jawab)\b",
)
INTENT_TERMS: dict[IntentName, tuple[str, ...]] = {
    "symptom_analysis": (
        "pain", "hurt", "ache", "fever", "cough", "headache", "dizzy", "weak",
        "tired", "tingling", "nausea", "bleeding", "breathing", "stomach", "chest",
        "injury", "symptom", "dard", "bukhar", "khansi", "chakkar", "kamzori",
        "thakan", "jhanjhanahat", "ulti", "saans", "sir", "pet", "seena",
        "दर्द", "बुखार", "खांसी", "चक्कर", "कमजोरी", "सांस", "सिर", "पेट",
    ),
    "report_reading": (
        "report", "lab", "blood test", "pdf", "scan", "result", "hba1c",
        "रिपोर्ट", "जांच", "रिजल्ट",
    ),
    "medication_management": (
        "medicine", "medication", "tablet", "dose", "prescription", "pill", "drug",
        "dawa", "dawai", "goli", "दवा", "गोली",
    ),
    "care_coordination": (
        "doctor", "specialist", "appointment", "brief", "next step", "clinic",
        "डॉक्टर", "अपॉइंटमेंट",
    ),
    "emergency_detection": (
        "emergency", "chest pain", "can't breathe", "cannot breathe", "unconscious",
        "severe bleeding", "stroke", "overdose", "poison",
    ),
}


@dataclass(frozen=True)
class IntentExtraction:
    primary_intent: RouteIntent
    intents: tuple[IntentName, ...] = ()
    normalized_query: str = ""
    detected_language: DetectedLanguage = "en"
    confidence: float = 0.0
    needs_clarification: bool = False

    @property
    def is_healthcare(self) -> bool:
        return bool(self.intents)

    @property
    def kind(self) -> Literal["casual", "language_request", "healthcare", "unclear"]:
        return "healthcare" if self.is_healthcare else self.primary_intent


def _language(message: str) -> DetectedLanguage:
    if re.search(r"[\u0900-\u097f]", message):
        return "hi"
    roman_hindi = {"aap", "mere", "mera", "mujhe", "dard", "hai", "ho", "dawa", "sir", "pet"}
    words = set(re.findall(r"[a-z]+", message.lower()))
    return "hinglish" if len(words & roman_hindi) >= 2 else "en"


def extract_intent_fallback(message: str) -> IntentExtraction:
    text = " ".join(message.strip().lower().split())
    language = _language(message)
    if any(re.search(pattern, text) for pattern in LANGUAGE_PATTERNS):
        return IntentExtraction("language_request", normalized_query="User wants to converse in Hindi.", detected_language=language, confidence=1.0)
    if any(re.search(pattern, text) for pattern in CASUAL_PATTERNS):
        return IntentExtraction("casual", normalized_query="Casual conversation.", detected_language=language, confidence=1.0)

    intents = tuple(
        intent for intent, terms in INTENT_TERMS.items()
        if any(term in text for term in terms)
    )
    non_emergency = tuple(intent for intent in intents if intent != "emergency_detection")
    if non_emergency:
        return IntentExtraction(
            non_emergency[0],
            intents=intents,
            normalized_query=message.strip(),
            detected_language=language,
            confidence=0.9,
        )
    return IntentExtraction(
        "unclear",
        normalized_query=message.strip(),
        detected_language=language,
        confidence=0.35,
        needs_clarification=True,
    )


async def extract_intent(message: str) -> IntentExtraction:
    fallback = extract_intent_fallback(message)
    if fallback.confidence >= 0.9:
        return fallback

    result = await complete_json(
        (
            "You extract user intent before a healthcare assistant responds. Understand "
            "English, Hindi, Devanagari, and Romanized Hindi. Be literal: never invent "
            "a symptom, medicine, report, or request that the user did not state."
        ),
        f"""
User input: {message!r}

Return one JSON object:
{{
  "primary_intent": "casual|language_request|symptom_analysis|report_reading|medication_management|care_coordination|unclear",
  "intents": ["zero or more healthcare intents"],
  "normalized_query": "one short faithful English paraphrase of what the user means",
  "detected_language": "en|hi|hinglish",
  "confidence": 0.0,
  "needs_clarification": true
}}

Use casual for greetings and ordinary conversation. Use unclear when meaning is
not sufficiently clear. Only include healthcare intents explicitly supported by
the user's words.
""",
        {
            "primary_intent": fallback.primary_intent,
            "intents": list(fallback.intents),
            "normalized_query": fallback.normalized_query,
            "detected_language": fallback.detected_language,
            "confidence": fallback.confidence,
            "needs_clarification": fallback.needs_clarification,
        },
        provider="reasoning",
    )
    if not isinstance(result, dict):
        return fallback

    valid_routes = {"casual", "language_request", "symptom_analysis", "report_reading", "medication_management", "care_coordination", "unclear"}
    valid_intents = set(INTENT_TERMS)
    primary = result.get("primary_intent")
    confidence = result.get("confidence")
    if primary not in valid_routes or not isinstance(confidence, (int, float)) or confidence < 0.65:
        return fallback
    intents = tuple(item for item in result.get("intents", []) if item in valid_intents)
    if primary in {"casual", "language_request", "unclear"}:
        intents = ()
    elif primary not in intents:
        intents = (primary, *intents)
    return IntentExtraction(
        primary,
        intents=intents,
        normalized_query=str(result.get("normalized_query") or message).strip(),
        detected_language=result.get("detected_language") if result.get("detected_language") in {"en", "hi", "hinglish"} else _language(message),
        confidence=float(confidence),
        needs_clarification=bool(result.get("needs_clarification", primary == "unclear")),
    )


def understand_input(message: str) -> IntentExtraction:
    """Backward-compatible deterministic extraction for synchronous callers/tests."""
    return extract_intent_fallback(message)
