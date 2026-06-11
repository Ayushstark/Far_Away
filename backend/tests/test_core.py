import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import db
from backend.app.services import llm
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
