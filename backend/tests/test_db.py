from dataclasses import dataclass
from typing import Any

from backend.app import db


@dataclass
class FakeResponse:
    data: list[dict[str, Any]]


class FakeQuery:
    def __init__(
        self,
        client: "FakeClient",
        table: str,
        rows: list[dict[str, Any]],
    ) -> None:
        self.client = client
        self.table = table
        self.rows = rows
        self.inserted: dict[str, Any] | None = None

    def select(self, columns: str) -> "FakeQuery":
        self.client.calls.append((self.table, "select", columns))
        return self

    def eq(self, column: str, value: Any) -> "FakeQuery":
        self.client.calls.append((self.table, "eq", column, value))
        return self

    def is_(self, column: str, value: Any) -> "FakeQuery":
        self.client.calls.append((self.table, "is", column, value))
        return self

    def order(self, column: str, desc: bool) -> "FakeQuery":
        self.client.calls.append((self.table, "order", column, desc))
        return self

    def limit(self, count: int) -> "FakeQuery":
        self.client.calls.append((self.table, "limit", count))
        return self

    def insert(self, payload: dict[str, Any]) -> "FakeQuery":
        self.client.calls.append((self.table, "insert", payload))
        self.inserted = payload
        return self

    def execute(self) -> FakeResponse:
        return FakeResponse([self.inserted] if self.inserted else self.rows)


class FakeClient:
    def __init__(self, rows: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.rows = rows or {}
        self.calls: list[tuple[Any, ...]] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name, self.rows.get(name, []))


def test_get_health_history_formats_events_and_scopes_owner(monkeypatch) -> None:
    client = FakeClient(
        {
            "health_events": [
                {
                    "event_type": "symptom",
                    "description": "Headache since morning",
                    "ai_response": "Track hydration and severity.",
                    "severity": "mild",
                    "body_part": "head",
                    "created_at": "2026-06-11T10:30:00Z",
                }
            ]
        }
    )
    monkeypatch.setattr(db, "get_client", lambda: client)

    history = db.get_health_history("user-1")

    assert "2026-06-11 | symptom | severity: mild | body part: head" in history
    assert "CareOS response: Track hydration and severity." in history
    assert ("health_events", "is", "family_member_id", "null") in client.calls


def test_get_medications_scopes_family_member(monkeypatch) -> None:
    rows = [{"drug_name": "Metformin", "dose": "500 mg"}]
    client = FakeClient({"medications": rows})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.get_medications("user-1", "family-1")

    assert result == rows
    assert ("medications", "eq", "is_active", True) in client.calls
    assert ("medications", "eq", "family_member_id", "family-1") in client.calls


def test_add_medication_uses_final_supabase_schema(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(db, "get_client", lambda: client)

    medication = db.add_medication(
        "user-1",
        "Metformin",
        "500 mg",
        "twice daily",
        ["8am", "8pm"],
        True,
    )

    assert medication["drug_name"] == "Metformin"
    assert medication["timing"] == ["8am", "8pm"]
    assert medication["with_food"] is True
    assert medication["is_active"] is True


def test_save_report_and_create_family_member(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(db, "get_client", lambda: client)

    report = db.save_report(
        "user-1",
        "blood test",
        "https://example.test/report.pdf",
        "HbA1c is above target.",
        {"HbA1c": "8.1%"},
    )
    family = db.create_family_member(
        "user-1",
        "Anita Gupta",
        "spouse",
        49,
        "B+",
        ["hypertension"],
    )

    assert report["flagged_values"] == {"HbA1c": "8.1%"}
    assert report["report_date"]
    assert family["owner_id"] == "user-1"
    assert family["known_conditions"] == ["hypertension"]


def test_get_reports_returns_recent_family_reports(monkeypatch) -> None:
    rows = [{"id": "report-1", "ai_summary": "HbA1c improved."}]
    client = FakeClient({"reports": rows})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.get_reports("user-1", "family-1", limit=3)

    assert result == rows
    assert ("reports", "eq", "user_id", "user-1") in client.calls
    assert ("reports", "eq", "family_member_id", "family-1") in client.calls
    assert ("reports", "order", "uploaded_at", True) in client.calls
    assert ("reports", "limit", 3) in client.calls
