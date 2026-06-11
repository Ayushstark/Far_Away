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

    # Never allow an LLM response to downgrade a deterministic critical flag.
    return fallback if fallback.is_emergency and not assessment.is_emergency else assessment


def emergency_response(data: EmergencyAssessment) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(data.immediate_steps, 1))
    return (
        f"EMERGENCY ALERT: {data.suspected or 'urgent medical concern'}\n"
        f"Call {data.call_number} now.\n\n{steps}"
    )
