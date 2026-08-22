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

    def in_(self, column: str, values: list[Any]) -> "FakeQuery":
        self.client.calls.append((self.table, "in", column, values))
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

    def update(self, payload: dict[str, Any]) -> "FakeQuery":
        self.client.calls.append((self.table, "update", payload))
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
    assert ("health_events", "in", "lifecycle_status", ["active"]) in client.calls


def test_get_medications_scopes_family_member(monkeypatch) -> None:
    rows = [{"drug_name": "Metformin", "dose": "500 mg"}]
    client = FakeClient({"medications": rows})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.get_medications("user-1", "family-1")

    assert result == rows
    assert ("medications", "eq", "is_active", True) in client.calls
    assert ("medications", "in", "lifecycle_status", ["active"]) in client.calls
    assert ("medications", "eq", "family_member_id", "family-1") in client.calls


def test_get_profile_switches_to_selected_family_member(monkeypatch) -> None:
    rows = [{"id": "family-1", "owner_id": "user-1", "name": "Sita Devi"}]
    client = FakeClient({"family_members": rows})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.get_profile("user-1", "family-1")

    assert result["name"] == "Sita Devi"
    assert ("family_members", "eq", "owner_id", "user-1") in client.calls
    assert ("family_members", "eq", "id", "family-1") in client.calls


def test_create_authenticated_user_sets_required_profile_defaults(monkeypatch) -> None:
    client = FakeClient({"users": []})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.create_authenticated_user("auth-1", "Avinash", "avi@example.com")

    assert result["age"] == 0
    assert result["known_conditions"] == []
    assert result["allergies"] == []
    assert result["emergency_contacts"] == ""
    assert 20_000_000 <= result["id"] < 1_920_000_000
    assert ("users", "insert", result) in client.calls


def test_create_authenticated_user_normalizes_live_array_columns(monkeypatch) -> None:
    client = FakeClient({"users": []})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.create_authenticated_user(
        "auth-2",
        "Radha Desai",
        "radha@example.com",
        known_conditions="diabetes, hypertension",
        allergies="None",
        emergency_contact="6387442482",
    )

    assert result["known_conditions"] == ["diabetes", "hypertension"]
    assert result["allergies"] == []
    assert result["emergency_contacts"] == "6387442482"


def test_get_recent_health_events_returns_structured_context(monkeypatch) -> None:
    rows = [{"id": "event-1", "description": "Headache", "resolved": False}]
    client = FakeClient({"health_events": rows})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.get_recent_health_events("user-1", limit=5)

    assert result == rows
    assert ("health_events", "is", "family_member_id", "null") in client.calls
    assert ("health_events", "limit", 5) in client.calls


def test_unresolved_events_and_resolution_update(monkeypatch) -> None:
    rows = [{"id": "event-1", "description": "Headache", "resolved": False}]
    client = FakeClient({"health_events": rows})
    monkeypatch.setattr(db, "get_client", lambda: client)

    assert db.get_unresolved_events("user-1") == rows
    assert db.mark_event_resolved("event-1") == {"resolved": True}
    assert ("health_events", "eq", "resolved", False) in client.calls
    assert ("health_events", "update", {"resolved": True}) in client.calls


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
    assert ("reports", "in", "lifecycle_status", ["active"]) in client.calls
    assert ("reports", "eq", "family_member_id", "family-1") in client.calls
    assert ("reports", "order", "uploaded_at", True) in client.calls
    assert ("reports", "limit", 3) in client.calls


def test_get_reports_status_filter_archived(monkeypatch) -> None:
    client = FakeClient({"reports": []})
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.get_reports("user-1", status="archived")

    assert ("reports", "in", "lifecycle_status", ["archived"]) in client.calls
    assert ("reports", "in", "lifecycle_status", ["active"]) not in client.calls


def test_get_reports_status_filter_all_skips_lifecycle_filter(monkeypatch) -> None:
    client = FakeClient({"reports": []})
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.get_reports("user-1", status="all")

    assert not any(call[0] == "reports" and call[1] == "in" for call in client.calls)


def test_get_medications_status_filter_archived_and_all(monkeypatch) -> None:
    client = FakeClient({"medications": []})
    monkeypatch.setattr(db, "get_client", lambda: client)

    db.get_medications("user-1", status="archived")
    assert ("medications", "in", "lifecycle_status", ["archived"]) in client.calls

    client.calls.clear()
    db.get_medications("user-1", status="all")
    assert not any(call[0] == "medications" and call[1] == "in" for call in client.calls)


def test_lifecycle_action_archives_and_audits_record(monkeypatch) -> None:
    rows = {
        "reports": [{"id": "report-1", "user_id": "user-1", "lifecycle_status": "active"}],
        "data_lifecycle_events": [],
    }
    client = FakeClient(rows)
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.lifecycle_action(
        user_id="user-1",
        target_table="reports",
        target_id="report-1",
        action="archive",
        reason="Old report",
    )

    assert result["completion_status"] == "complete"
    assert result["lifecycle_status"] == "archived"
    update_call = next(call for call in client.calls if call[0] == "reports" and call[1] == "update")
    assert update_call[2]["retention_reason"] == "Old report"
    assert update_call[2]["lifecycle_status"] == "archived"
    assert update_call[2]["archived_at"]
    audit_call = next(call for call in client.calls if call[0] == "data_lifecycle_events" and call[1] == "insert")
    assert audit_call[2]["completion_status"] == "complete"
    assert audit_call[2]["previous_status"] == "active"
    assert audit_call[2]["next_status"] == "archived"


def test_lifecycle_action_blocks_unowned_record(monkeypatch) -> None:
    client = FakeClient({"reports": []})
    monkeypatch.setattr(db, "get_client", lambda: client)

    result = db.lifecycle_action("user-1", "reports", "missing", "delete")

    assert result["completion_status"] == "blocked"
    assert result["lifecycle_status"] == "delete_failed"
    audit_call = next(call for call in client.calls if call[0] == "data_lifecycle_events" and call[1] == "insert")
    assert audit_call[2]["completion_status"] == "blocked"
