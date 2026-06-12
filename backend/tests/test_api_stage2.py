from fastapi.testclient import TestClient

from backend.app import db
from backend.app.main import app
from backend.app.schemas import AgentResult, ChatResponse
import backend.app.main as api


client = TestClient(app)


def test_chat_loads_context_and_saves_health_event(monkeypatch) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(db, "get_health_history", lambda *args: "Recent headache")
    monkeypatch.setattr(db, "get_medications", lambda *args: [{"drug_name": "Metformin"}])

    async def run(message, profile_id, health_history, current_medications):
        calls["context"] = (health_history, current_medications)
        return ChatResponse(
            message="Track symptoms.",
            intents=["symptom_analysis"],
            agents_used=["emergency_detector", "symptom_analyst"],
            results=[AgentResult(agent="symptom_analyst", summary="Track symptoms.")],
        )

    monkeypatch.setattr(api.orchestrator, "run", run)
    monkeypatch.setattr(db, "save_health_event", lambda **kwargs: calls.setdefault("event", kwargs))

    response = client.post(
        "/chat",
        json={"message": "Headache", "profile_id": "user-1", "family_member_id": "family-1"},
    )

    assert response.status_code == 200
    assert calls["context"] == ("Recent headache", [{"drug_name": "Metformin"}])
    assert calls["event"]["family_member_id"] == "family-1"
    assert calls["event"]["ai_response"] == "Track symptoms."


def test_chat_returns_response_when_event_save_temporarily_fails(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_health_history", lambda *args: "Recent headache")
    monkeypatch.setattr(db, "get_medications", lambda *args: [])

    async def run(*args, **kwargs):
        return ChatResponse(
            message="Track symptoms.",
            intents=["symptom_analysis"],
            agents_used=["emergency_detector", "symptom_analyst"],
            results=[AgentResult(agent="symptom_analyst", summary="Track symptoms.")],
        )

    monkeypatch.setattr(api.orchestrator, "run", run)
    monkeypatch.setattr(db, "save_health_event", lambda **kwargs: (_ for _ in ()).throw(OSError("offline")))

    response = client.post("/chat", json={"message": "Headache", "profile_id": "user-1"})

    assert response.status_code == 200
    assert response.json()["message"] == "Track symptoms."


def test_general_conversation_does_not_load_health_history(monkeypatch) -> None:
    monkeypatch.setattr(
        db,
        "get_health_history",
        lambda *args: (_ for _ in ()).throw(AssertionError("history should not load")),
    )
    monkeypatch.setattr(
        db,
        "get_medications",
        lambda *args: (_ for _ in ()).throw(AssertionError("medications should not load")),
    )
    monkeypatch.setattr(
        db,
        "save_health_event",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("casual chat should not save")),
    )

    response = client.post(
        "/chat",
        json={"message": "Can we talk in Hindi?", "profile_id": "user-1"},
    )

    assert response.status_code == 200
    assert response.json()["intents"] == []
    assert "हिंदी" in response.json()["message"]


def test_upload_report_stores_file_and_report_row(monkeypatch) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(db, "upload_report_file", lambda *args: "https://files/report.pdf")
    monkeypatch.setattr(db, "get_past_reports_summary", lambda *args: "Previous report summary")
    monkeypatch.setattr(db, "save_report", lambda **kwargs: calls.setdefault("report", kwargs))

    async def read_report(*args, **kwargs):
        return "Current report analysis"

    monkeypatch.setattr(api, "read_report", read_report)
    response = client.post(
        "/upload-report",
        data={"profile_id": "user-1", "report_type": "blood report"},
        files={"file": ("labs.pdf", b"%PDF-1.4 demo", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["interpretation"] == "Current report analysis"
    assert calls["report"]["file_url"] == "https://files/report.pdf"
    assert calls["report"]["ai_summary"] == "Current report analysis"


def test_family_medication_and_history_routes(monkeypatch) -> None:
    monkeypatch.setattr(db, "create_family_member", lambda **kwargs: {"id": "family-1", **kwargs})
    monkeypatch.setattr(db, "get_family_members", lambda owner_id: [{"owner_id": owner_id}])
    monkeypatch.setattr(db, "add_medication", lambda **kwargs: {"id": "med-1", **kwargs})
    monkeypatch.setattr(db, "get_medications", lambda *args: [{"drug_name": "Metformin"}])
    monkeypatch.setattr(db, "get_health_history", lambda *args, **kwargs: "Timeline")

    family = client.post(
        "/family/add",
        json={
            "owner_id": "user-1",
            "name": "Anita",
            "relation": "spouse",
            "age": 49,
            "blood_group": "B+",
            "known_conditions": [],
        },
    )
    medication = client.post(
        "/medications/add",
        json={
            "user_id": "user-1",
            "drug_name": "Metformin",
            "dose": "500 mg",
            "frequency": "twice daily",
            "timing": ["8am", "8pm"],
            "with_food": True,
        },
    )

    assert family.status_code == 200
    assert client.get("/family/user-1").status_code == 200
    assert medication.json()["drug_name"] == "Metformin"
    assert client.get("/medications/user-1").json()[0]["drug_name"] == "Metformin"
    assert client.get("/history/user-1").json()["history"] == "Timeline"


def test_doctor_brief_uses_database_context(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_health_history", lambda *args, **kwargs: "Timeline")
    monkeypatch.setattr(db, "get_medications", lambda *args, **kwargs: [{"drug_name": "Metformin"}])
    monkeypatch.setattr(db, "get_user", lambda user_id: {"id": user_id, "name": "Ramesh"})

    async def brief(*args, **kwargs):
        assert kwargs["health_history"] == "Timeline"
        assert kwargs["user_profile"]["name"] == "Ramesh"
        return "Doctor brief"

    monkeypatch.setattr(api, "create_care_brief", brief)
    response = client.get("/doctor-brief/user-1")

    assert response.status_code == 200
    assert response.json()["brief"] == "Doctor brief"


def test_stage4_profile_reports_and_interaction_routes(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_user", lambda user_id: {"id": user_id, "name": "Ramesh"})
    monkeypatch.setattr(db, "get_reports", lambda *args: [{"id": "report-1"}])
    monkeypatch.setattr(db, "get_medications", lambda *args: [{"drug_name": "Metformin"}])

    async def check_interactions(*args, **kwargs):
        return "No known major interaction found."

    monkeypatch.setattr(api.orchestrator.medication_manager, "run", check_interactions)

    assert client.get("/profile/user-1").json()["name"] == "Ramesh"
    assert client.get("/reports/user-1?family_member_id=family-1").json()[0]["id"] == "report-1"

    response = client.post(
        "/medications/check-interactions",
        json={"user_id": "user-1", "new_drug": "Amlodipine"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "No known major interaction found."
