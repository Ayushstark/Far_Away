from backend.app import db
from backend.app.services import standout


def test_build_health_timeline_merges_lifecycle_events(monkeypatch) -> None:
    monkeypatch.setattr(db, "get_recent_health_events", lambda *args, **kwargs: [])
    monkeypatch.setattr(db, "get_reports", lambda *args, **kwargs: [])
    monkeypatch.setattr(db, "get_medications", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        db,
        "get_lifecycle_audit",
        lambda *args, **kwargs: [
            {
                "created_at": "2026-06-20T10:00:00Z",
                "target_table": "reports",
                "action": "archive",
                "completion_status": "complete",
                "reason": "Old report",
            },
            {
                "created_at": "2026-06-19T09:00:00Z",
                "target_table": "medications",
                "action": "restore",
                "completion_status": "complete",
                "reason": "",
            },
            {
                "created_at": "2026-06-18T08:00:00Z",
                "target_table": "health_events",
                "action": "delete",
                "completion_status": "blocked",
                "reason": "",
                "error_message": "Record not found for this profile.",
            },
        ],
    )

    items = standout.build_health_timeline("user-1")

    assert [item.category for item in items] == ["lifecycle", "lifecycle", "lifecycle"]
    assert items[0].title == "Report archived"
    assert items[0].detail == "Completed. Reason noted: Old report"
    assert items[1].title == "Medication restored"
    assert items[2].title == "Health event deleted"
    assert items[2].status == "blocked"
    assert items[2].detail == "Record not found for this profile."


def test_build_health_timeline_sorts_lifecycle_alongside_health_data(monkeypatch) -> None:
    monkeypatch.setattr(
        db,
        "get_recent_health_events",
        lambda *args, **kwargs: [
            {"created_at": "2026-06-25T00:00:00Z", "event_type": "symptom", "description": "Headache"}
        ],
    )
    monkeypatch.setattr(db, "get_reports", lambda *args, **kwargs: [])
    monkeypatch.setattr(db, "get_medications", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        db,
        "get_lifecycle_audit",
        lambda *args, **kwargs: [
            {
                "created_at": "2026-06-27T00:00:00Z",
                "target_table": "reports",
                "action": "archive",
                "completion_status": "complete",
            }
        ],
    )

    items = standout.build_health_timeline("user-1")

    assert items[0].category == "lifecycle"
    assert items[1].category == "symptom"
