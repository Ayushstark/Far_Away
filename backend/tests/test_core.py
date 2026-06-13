import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import db
from backend.app.services import llm
from backend.app.services.orchestrator import Orchestrator, is_casual_message
from backend.app.services.input_understanding import (
    IntentExtraction,
    extract_intent,
    understand_input,
)
from backend.app.schemas import EmergencyAssessment
from backend.app.services.intent_classifier import classify_intent_fallback
from agents import emergency
from memory.store import HealthMemory


def test_semantic_memory_is_user_scoped() -> None:
    memory = HealthMemory(persistent=False)
    memory.remember("user-a", "Started a new blood pressure medicine", {"type": "medication"})
    memory.remember("user-b", "Has a fever and cough", {"type": "symptom"})

    results = memory.recall("user-a", "new tablet dose")

    assert results == ["Started a new blood pressure medicine"]


def test_chat_runs_emergency_first(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_health_history", lambda *args, **kwargs: "No history")
    monkeypatch.setattr(db, "get_medications", lambda *args, **kwargs: [])
    monkeypatch.setattr(db, "save_health_event", lambda **kwargs: kwargs)
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"message": "I have chest pain and cannot breathe", "profile_id": "test-user"},
    )

    assert response.status_code == 200
    assert response.json()["emergency"] is True
    assert response.json()["agents_used"] == ["emergency_detector"]


def test_medication_add_and_list(monkeypatch) -> None:
    saved: list[dict] = []

    def add(**kwargs):
        saved.append(kwargs)
        return kwargs

    monkeypatch.setattr(db, "add_medication", add)
    monkeypatch.setattr(db, "get_medications", lambda *args, **kwargs: saved)
    client = TestClient(app)
    response = client.post(
        "/api/medications",
        json={
            "action": "add",
            "profile_id": "med-test",
            "data": {"name": "ExampleMed", "dose": "5 mg", "times": ["8am"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["medications"][0]["drug_name"] == "ExampleMed"


def test_reasoning_routes_to_gemini_first(monkeypatch) -> None:
    calls: list[str] = []

    async def gemini(*args) -> str:
        calls.append("gemini")
        return "reasoned"

    async def groq(*args) -> str:
        calls.append("groq")
        return "fast"

    monkeypatch.setattr(llm, "_gemini_complete", gemini)
    monkeypatch.setattr(llm, "_groq_complete", groq)

    result = asyncio.run(llm.complete("system", "prompt", provider="reasoning"))

    assert result == "reasoned"
    assert calls == ["gemini"]


def test_fast_routes_to_groq_then_gemini_fallback(monkeypatch) -> None:
    calls: list[str] = []

    async def gemini(*args) -> str:
        calls.append("gemini")
        return "fallback"

    async def groq(*args) -> str:
        calls.append("groq")
        return ""

    monkeypatch.setattr(llm, "_gemini_complete", gemini)
    monkeypatch.setattr(llm, "_groq_complete", groq)

    result = asyncio.run(llm.complete("system", "prompt", provider="fast"))

    assert result == "fallback"
    assert calls == ["groq", "gemini"]


def test_emergency_detector_rejects_contradictory_model_result(monkeypatch) -> None:
    async def contradictory(*args, **kwargs):
        return {
            "is_emergency": True,
            "severity": "none",
            "suspected": "general concern",
            "immediate_steps": ["Call back later"],
            "call_number": "not provided",
        }

    monkeypatch.setattr(emergency, "complete_json", contradictory)

    result = asyncio.run(emergency.assess_emergency("Hello"))

    assert result.is_emergency is False


def test_emergency_detector_rejects_false_positive_without_red_flag(monkeypatch) -> None:
    async def false_positive(*args, **kwargs):
        return {
            "is_emergency": True,
            "severity": "critical",
            "suspected": "communication failure",
            "immediate_steps": ["Call emergency services"],
            "call_number": "112 or 108",
        }

    monkeypatch.setattr(emergency, "complete_json", false_positive)

    result = asyncio.run(emergency.assess_emergency("Please reply in Hindi"))

    assert result.is_emergency is False


def test_greeting_gets_short_response_without_symptom_agent(monkeypatch) -> None:
    async def no_emergency(*args, **kwargs):
        return emergency.EmergencyAssessment()

    monkeypatch.setattr("backend.app.services.orchestrator.assess_emergency", no_emergency)

    response = asyncio.run(Orchestrator(memory=HealthMemory(persistent=False)).run("Hi", "user-1"))

    assert response.intents == []
    assert response.agents_used == ["emergency_detector"]
    assert "How can I help" in response.message
    assert len(response.message) < 160


def test_general_conversation_is_casual_and_hindi_request_uses_hindi(monkeypatch) -> None:
    async def no_emergency(*args, **kwargs):
        return emergency.EmergencyAssessment()

    monkeypatch.setattr("backend.app.services.orchestrator.assess_emergency", no_emergency)

    assert is_casual_message("Hello, how are you?") is True
    response = asyncio.run(
        Orchestrator(memory=HealthMemory(persistent=False)).run(
            "Hello, how are you? Reply in Hindi",
            "user-1",
        )
    )

    assert response.intents == []
    assert "हिंदी" in response.message


def test_input_understanding_blocks_random_clinical_routing() -> None:
    assert understand_input("Can we talk in Hindi?").kind == "language_request"
    assert understand_input("Hello, how are you?").kind == "casual"
    assert understand_input("आप कैसे हैं?").kind == "casual"
    assert understand_input("Tell me something interesting").kind == "unclear"
    assert understand_input("My stomach hurts").kind == "healthcare"
    assert classify_intent_fallback("My stomach hurts") == ["symptom_analysis"]
    assert classify_intent_fallback("Can we talk in Hindi?") == []


def test_structured_intent_extraction_understands_romanized_hindi() -> None:
    casual = asyncio.run(extract_intent("Aap kaise ho?"))
    symptom = asyncio.run(extract_intent("Mere sir me dard ho raha hai"))

    assert casual.primary_intent == "casual"
    assert casual.intents == ()
    assert symptom.primary_intent == "symptom_analysis"
    assert symptom.intents == ("symptom_analysis",)
    assert symptom.detected_language == "hinglish"
    assert symptom.confidence >= 0.9


def test_recurring_moderate_symptom_runs_autonomous_agent_chain(monkeypatch) -> None:
    orchestrator = Orchestrator(memory=HealthMemory(persistent=False))

    async def symptoms(*args, **kwargs):
        return "Symptom analysis"

    async def medication(action, data, user_id):
        assert action == "side_effects"
        return "Medication review"

    async def specialist(*args, **kwargs):
        return "Specialist advice"

    async def merge(results, preferred_language):
        assert preferred_language == "hi"
        return "संयुक्त उत्तर"

    monkeypatch.setattr("backend.app.services.orchestrator.analyze_symptoms", symptoms)
    monkeypatch.setattr(orchestrator.medication_manager, "run", medication)
    monkeypatch.setattr("backend.app.services.orchestrator.specialist_advice", specialist)
    monkeypatch.setattr("backend.app.services.orchestrator.merge_responses", merge)

    response = asyncio.run(
        orchestrator.run(
            "Mere sir me dard phir ho raha hai, it is getting worse",
            "user-1",
            health_history="Previous headache",
            current_medications=[{"drug_name": "Amlodipine"}],
            preferred_language="hi",
            extraction=IntentExtraction(
                "symptom_analysis",
                intents=("symptom_analysis",),
                normalized_query="Recurring worsening headache",
                detected_language="hinglish",
                confidence=1.0,
            ),
            emergency_assessment=EmergencyAssessment(),
        )
    )

    assert response.severity == "moderate"
    assert response.agents_used == [
        "emergency_detector",
        "symptom_analyst",
        "medication_manager",
        "care_coordinator",
    ]
    assert response.steps_taken == [
        "Analyzing symptoms",
        "Checking your medications",
        "Finding the right specialist",
    ]
    assert response.message == "संयुक्त उत्तर"


def test_follow_up_outcome_is_detected_before_general_intent_routing() -> None:
    response = asyncio.run(
        Orchestrator(memory=HealthMemory(persistent=False)).run(
            "Better now",
            "user-1",
            previous_assistant_message="How is your headache now?",
            follow_up_event_id="event-1",
            emergency_assessment=EmergencyAssessment(),
        )
    )

    assert response.follow_up_outcome == "resolved"
    assert response.steps_taken == ["Updating your health timeline"]
