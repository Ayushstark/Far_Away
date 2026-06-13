from backend.app.schemas import EmergencyAssessment
from backend.app.services.llm import complete_json

CRITICAL_FLAGS = {
    "chest pain": "possible heart or chest emergency",
    "can't breathe": "severe breathing difficulty",
    "cannot breathe": "severe breathing difficulty",
    "difficulty breathing": "breathing difficulty",
    "unconscious": "loss of consciousness",
    "severe bleeding": "severe bleeding",
    "stroke": "possible stroke symptoms",
    "heart attack": "possible heart attack",
    "seizure": "possible seizure",
    "choking": "possible choking",
    "suicidal": "immediate mental-health emergency",
    "kill myself": "immediate mental-health emergency",
    "overdose": "possible overdose",
    "poisoning": "possible poisoning",
}


def emergency_fallback(message: str) -> EmergencyAssessment:
    text = message.lower()
    matched = next((label for phrase, label in CRITICAL_FLAGS.items() if phrase in text), "")
    if not matched:
        return EmergencyAssessment()
    return EmergencyAssessment(
        is_emergency=True,
        severity="critical",
        suspected=matched,
        immediate_steps=[
            "Call emergency services now.",
            "Stay with the person and follow the dispatcher's instructions.",
            "Do not drive yourself if you feel faint, breathless, or unsafe.",
        ],
    )


async def assess_emergency(message: str) -> EmergencyAssessment:
    fallback = emergency_fallback(message)
    result = await complete_json(
        "You screen messages for medical emergencies only. Be conservative.",
        f"""
Message: {message!r}

Red flags include chest pain, difficulty breathing, stroke symptoms, severe
bleeding, loss of consciousness, poisoning, and heart attack signs.

Return:
{{
  "is_emergency": true,
  "severity": "critical",
  "suspected": "short plain-language concern",
  "immediate_steps": ["safe immediate action"],
  "call_number": "112 or 108"
}}
""",
        fallback.model_dump(),
        provider="fast",
    )
    try:
        assessment = EmergencyAssessment.model_validate(result)
    except Exception:
        assessment = fallback

    # Reject contradictory model output such as emergency=true with no severity
    # or no valid Indian emergency number.
    if (
        assessment.is_emergency
        and (
            assessment.severity == "none"
            or assessment.call_number not in {"112", "108", "112 or 108"}
        )
    ):
        assessment = fallback

    # Do not let a model turn ordinary conversation into an emergency. The
    # deterministic red-flag screen remains the safety authority.
    if assessment.is_emergency and not fallback.is_emergency:
        assessment = fallback

    # Never allow an LLM response to downgrade a deterministic critical flag.
    return fallback if fallback.is_emergency and not assessment.is_emergency else assessment


def emergency_response(data: EmergencyAssessment, preferred_language: str = "en") -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(data.immediate_steps, 1))
    if preferred_language == "hi":
        hindi_steps = "\n".join(
            [
                "1. अभी आपातकालीन सेवाओं को कॉल करें।",
                "2. व्यक्ति के साथ रहें और डिस्पैचर के निर्देशों का पालन करें।",
                "3. चक्कर, सांस की तकलीफ या असुरक्षित महसूस होने पर स्वयं गाड़ी न चलाएँ।",
            ]
        )
        return (
            f"आपातकालीन चेतावनी: {data.suspected or 'तत्काल चिकित्सा चिंता'}\n"
            f"अभी {data.call_number} पर कॉल करें।\n\n{hindi_steps}"
        )
    return (
        f"EMERGENCY ALERT: {data.suspected or 'urgent medical concern'}\n"
        f"Call {data.call_number} now.\n\n{steps}"
    )
