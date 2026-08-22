"""Small Supabase data-access layer for CareOS.

Keeping database calls here gives the API and agents one consistent view of the
final Supabase schema, while leaving orchestration code focused on healthcare
workflows.
"""

from datetime import date, datetime, timezone
import re
import secrets
from typing import Any

from supabase import Client, create_client

from backend.app.config import settings

_client: Client | None = None
MISSING_COLUMN = re.compile(r"Could not find the '([^']+)' column")
MALFORMED_ARRAY_LITERAL = re.compile(r'malformed array literal: "([^"]*)"')
TEXT_ARRAY_COLUMNS = {
    "users": {"known_conditions", "allergies"},
    "family_members": {"known_conditions"},
    "medications": {"timing"},
}
RETENTION_TABLES = {"health_events", "reports", "medications"}
LIFECYCLE_STATUSES = ("active", "archived", "pending_deletion", "deleted")
COMPLETION_STATUSES = ("complete", "partial", "blocked", "unresolved")
RECORD_STATUS_FILTERS = ("active", "archived", "all")


def get_client() -> Client:
    """Return one service-role Supabase client for the backend process."""
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured.")
        _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def get_user(user_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_user_by_auth_id(auth_user_id: str) -> dict[str, Any] | None:
    """Resolve a Supabase Auth identity to its isolated CareOS profile."""
    response = (
        get_client()
        .table("users")
        .select("*")
        .eq("auth_user_id", auth_user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_authenticated_user(
    auth_user_id: str,
    name: str,
    email: str,
    age: int = 0,
    gender: str = "",
    blood_group: str = "",
    known_conditions: str | list[str] = "",
    allergies: str | list[str] = "",
    emergency_contact: str = "",
) -> dict[str, Any]:
    """Create the CareOS profile paired with a newly authenticated account."""
    existing = get_user_by_auth_id(auth_user_id)
    if existing:
        return existing

    # The live hackathon schema has used both bigint and regular integer IDs.
    # Stay below Postgres int4 max so authenticated profiles work on either.
    last_error: Exception | None = None
    for _ in range(20):
        profile_id = 20_000_000 + secrets.randbelow(1_900_000_000)
        payload = {
            "id": profile_id,
            "auth_user_id": auth_user_id,
            "name": name,
            "email": email,
            "age": age,
            "gender": gender,
            "blood_group": blood_group,
            "known_conditions": _list_value(known_conditions),
            "allergies": _list_value(allergies),
            "emergency_contacts": emergency_contact,
            "emergency_contact": emergency_contact,
        }
        try:
            response = _insert_skipping_missing_columns("users", payload)
            return _first_row(response.data)
        except Exception as exc:
            # A concurrent first login or the extremely unlikely ID collision
            # can be resolved by checking the auth mapping before retrying.
            existing = get_user_by_auth_id(auth_user_id)
            if existing:
                return existing
            last_error = exc
    raise RuntimeError(f"Could not create CareOS profile: {last_error}")


def _insert_skipping_missing_columns(table: str, payload: dict[str, Any]) -> Any:
    current = dict(payload)
    while True:
        try:
            return get_client().table(table).insert(current).execute()
        except Exception as exc:
            message = str(exc)
            missing_match = MISSING_COLUMN.search(message)
            if missing_match:
                missing = missing_match.group(1)
                if missing not in current:
                    raise
                current.pop(missing)
                continue

            array_match = MALFORMED_ARRAY_LITERAL.search(message)
            if array_match and _retry_scalar_as_array(current, array_match.group(1)):
                continue

            if _retry_declared_arrays(table, current):
                continue

                raise


def get_family_member(owner_id: str, family_member_id: str) -> dict[str, Any] | None:
    response = (
        get_client()
        .table("family_members")
        .select("*")
        .eq("owner_id", owner_id)
        .eq("id", family_member_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_profile(user_id: str, family_member_id: str | None = None) -> dict[str, Any] | None:
    """Return the selected person's profile without leaking the owner's context."""
    return (
        get_family_member(user_id, family_member_id)
        if family_member_id
        else get_user(user_id)
    )


def get_health_history(
    user_id: str,
    family_member_id: str | None = None,
    limit: int = 20,
) -> str:
    query = (
        get_client()
        .table("health_events")
        .select(
            "event_type,description,ai_response,severity,body_part,resolved,created_at"
        )
        .eq("user_id", user_id)
    )
    response = (
        _active_lifecycle(_scope_family_member(query, family_member_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    if not response.data:
        return "No previous health events found."

    events = []
    for event in response.data:
        created_at = _display_date(event.get("created_at"))
        heading = (
            f"{created_at} | {event.get('event_type', 'health event')} | "
            f"severity: {event.get('severity') or 'not recorded'}"
        )
        if event.get("body_part"):
            heading += f" | body part: {event['body_part']}"
        detail = event.get("description") or "No description."
        if event.get("ai_response"):
            detail += f"\nCareOS response: {event['ai_response']}"
        events.append(f"{heading}\n{detail}")
    return "\n\n".join(events)


def get_recent_health_events(
    user_id: str,
    family_member_id: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return raw recent events when an agent needs structured context."""
    query = (
        get_client()
        .table("health_events")
        .select(
            "id,event_type,description,ai_response,severity,body_part,resolved,created_at"
        )
        .eq("user_id", user_id)
    )
    response = (
        _active_lifecycle(_scope_family_member(query, family_member_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def get_unresolved_events(
    user_id: str,
    family_member_id: str | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Return recent unresolved symptoms so CareOS can close the loop later."""
    query = (
        get_client()
        .table("health_events")
        .select("id,event_type,description,severity,body_part,resolved,created_at")
        .eq("user_id", user_id)
        .in_("event_type", ["symptom", "symptom_analysis"])
        .eq("resolved", False)
    )
    response = (
        _active_lifecycle(_scope_family_member(query, family_member_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def mark_event_resolved(event_id: str | int) -> dict[str, Any]:
    response = (
        get_client()
        .table("health_events")
        .update({"resolved": True})
        .eq("id", event_id)
        .execute()
    )
    return _first_row(response.data)


def save_health_event(
    user_id: str,
    event_type: str,
    description: str,
    ai_response: str,
    severity: str,
    body_part: str | None,
    family_member_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "event_type": event_type,
        "description": description,
        "ai_response": ai_response,
        "severity": severity,
        "body_part": body_part,
        "family_member_id": family_member_id,
    }
    response = get_client().table("health_events").insert(payload).execute()
    return _first_row(response.data)


def get_medications(
    user_id: str,
    family_member_id: str | None = None,
    *,
    status: str = "active",
) -> list[dict[str, Any]]:
    """Return medications for the profile.

    `status` is a display-layer filter for the Medications screen
    (active/archived/all). AI-context callers should keep calling this with
    the default "active" so archived medications never re-enter chat,
    daily-plan, or doctor-brief context.
    """
    query = (
        get_client()
        .table("medications")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
    )
    response = (
        _apply_status_filter(_scope_family_member(query, family_member_id), status)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def add_medication(
    user_id: str,
    drug_name: str,
    dose: str,
    frequency: str,
    timing: list[str] | str,
    with_food: bool,
    family_member_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "family_member_id": family_member_id,
        "drug_name": drug_name,
        "dose": dose,
        "frequency": frequency,
        "timing": _list_value(timing),
        "with_food": with_food,
        "is_active": True,
    }
    response = _insert_skipping_missing_columns("medications", payload)
    return _first_row(response.data)


def save_report(
    user_id: str,
    report_type: str,
    file_url: str,
    ai_summary: str,
    flagged_values: dict[str, Any] | list[Any],
    family_member_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "family_member_id": family_member_id,
        "report_type": report_type,
        "file_url": file_url,
        "report_date": date.today().isoformat(),
        "ai_summary": ai_summary,
        "flagged_values": flagged_values,
        "uploaded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    response = get_client().table("reports").insert(payload).execute()
    return _first_row(response.data)


def get_past_reports_summary(
    user_id: str,
    family_member_id: str | None = None,
) -> str:
    query = (
        get_client()
        .table("reports")
        .select("report_type,report_date,lab_name,ai_summary,flagged_values,uploaded_at")
        .eq("user_id", user_id)
    )
    response = (
        _active_lifecycle(_scope_family_member(query, family_member_id))
        .order("uploaded_at", desc=True)
        .limit(3)
        .execute()
    )
    if not response.data:
        return "No previous report summaries found."

    summaries = []
    for report in response.data:
        label = report.get("report_type") or "Medical report"
        report_date = _display_date(report.get("report_date") or report.get("uploaded_at"))
        lab = f" from {report['lab_name']}" if report.get("lab_name") else ""
        summaries.append(
            f"{report_date} | {label}{lab}\n"
            f"{report.get('ai_summary') or 'No AI summary available.'}"
        )
    return "\n\n".join(summaries)


def get_reports(
    user_id: str,
    family_member_id: str | None = None,
    limit: int = 20,
    *,
    status: str = "active",
) -> list[dict[str, Any]]:
    """Return reports for the profile.

    `status` is a display-layer filter for the Reports screen
    (active/archived/all). AI-context callers should keep calling this with
    the default "active" so archived reports never re-enter chat,
    daily-plan, or doctor-brief context.
    """
    query = get_client().table("reports").select("*").eq("user_id", user_id)
    query = _apply_status_filter(_scope_family_member(query, family_member_id), status)
    response = (
        query
        .order("uploaded_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def create_family_member(
    owner_id: str,
    name: str,
    relation: str,
    age: int,
    blood_group: str,
    known_conditions: list[str] | str,
) -> dict[str, Any]:
    payload = {
        "owner_id": owner_id,
        "name": name,
        "relation": relation,
        "age": age,
        "blood_group": blood_group,
        "known_conditions": _list_value(known_conditions),
    }
    response = _insert_skipping_missing_columns("family_members", payload)
    return _first_row(response.data)


def get_family_members(owner_id: str) -> list[dict[str, Any]]:
    response = (
        get_client()
        .table("family_members")
        .select("*")
        .eq("owner_id", owner_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def upload_report_file(user_id: str, filename: str, content: bytes) -> str:
    """Upload a PDF to the reports bucket and return its stored URL."""
    safe_name = filename.replace("\\", "_").replace("/", "_")
    path = f"{user_id}/{date.today().isoformat()}-{safe_name}"
    storage = get_client().storage
    if not any(bucket.name == "reports" for bucket in storage.list_buckets()):
        storage.create_bucket(
            "reports",
            options={
                "public": False,
                "allowed_mime_types": ["application/pdf"],
                "file_size_limit": 10 * 1024 * 1024,
            },
        )
    bucket = storage.from_("reports")
    bucket.upload(
        path,
        content,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def lifecycle_action(
    user_id: str,
    target_table: str,
    target_id: str | int,
    action: str,
    reason: str = "",
    family_member_id: str | None = None,
) -> dict[str, Any]:
    """Archive, restore, or soft-delete a scoped record and write an audit row."""
    if target_table not in RETENTION_TABLES:
        return _blocked_lifecycle_result(target_table, target_id, action, "Unsupported retention table.")
    if action not in {"archive", "restore", "delete"}:
        return _blocked_lifecycle_result(target_table, target_id, action, "Unsupported lifecycle action.")

    record = _get_retention_record(user_id, target_table, target_id, family_member_id)
    if not record:
        result = _blocked_lifecycle_result(target_table, target_id, action, "Record not found for this profile.")
        _insert_lifecycle_event(
            user_id,
            family_member_id,
            target_table,
            target_id,
            action,
            "blocked",
            None,
            None,
            reason,
            result["error_message"],
            None,
        )
        return result

    previous_status = record.get("lifecycle_status") or "active"
    timestamp = _now()
    payload = {"retention_reason": reason}
    if action == "archive":
        next_status = "archived"
        payload.update({"lifecycle_status": next_status, "archived_at": timestamp})
    elif action == "restore":
        next_status = "active"
        payload.update({"lifecycle_status": next_status, "restored_at": timestamp})
    else:
        next_status = "deleted"
        payload.update({"lifecycle_status": next_status, "deleted_at": timestamp})

    completion_status = "complete"
    error_message = None
    try:
        response = (
            get_client()
            .table(target_table)
            .update(payload)
            .eq("id", target_id)
            .eq("user_id", user_id)
            .execute()
        )
        updated = _first_row(response.data)
    except Exception as exc:
        completion_status = "blocked"
        error_message = str(exc)
        next_status = f"{action}_failed"
        updated = {**record, "lifecycle_status": next_status}

    _insert_lifecycle_event(
        user_id,
        family_member_id,
        target_table,
        target_id,
        action,
        completion_status,
        previous_status,
        next_status,
        reason,
        error_message,
        record,
    )
    return {
        "target_table": target_table,
        "target_id": str(target_id),
        "action": action,
        "lifecycle_status": updated.get("lifecycle_status") or next_status,
        "completion_status": completion_status,
        "message": _lifecycle_message(action, target_table, completion_status),
        "error_message": error_message,
    }


def get_retention_summary(
    user_id: str,
    family_member_id: str | None = None,
) -> dict[str, Any]:
    summary = {status: 0 for status in LIFECYCLE_STATUSES}
    completion = {status: 0 for status in COMPLETION_STATUSES}
    for table in RETENTION_TABLES:
        for row in _retention_rows(user_id, table, family_member_id):
            status = row.get("lifecycle_status") or "active"
            if status in summary:
                summary[status] += 1

    events = get_lifecycle_audit(user_id, family_member_id, limit=100)
    for event in events:
        status = event.get("completion_status")
        if status in completion:
            completion[status] += 1

    capability_status = "no_actions"
    if completion["blocked"]:
        capability_status = "blocked"
    elif completion["unresolved"]:
        capability_status = "unresolved"
    elif completion["partial"]:
        capability_status = "partial"
    elif completion["complete"]:
        capability_status = "complete"

    return {
        **summary,
        **completion,
        "capability_status": capability_status,
        "latest_event": events[0] if events else None,
    }


def get_retention_items(
    user_id: str,
    family_member_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "health_events": _retention_rows(user_id, "health_events", family_member_id),
        "reports": _retention_rows(user_id, "reports", family_member_id),
        "medications": _retention_rows(user_id, "medications", family_member_id),
        "events": get_lifecycle_audit(user_id, family_member_id, limit=50),
    }


def get_lifecycle_audit(
    user_id: str,
    family_member_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("data_lifecycle_events")
        .select("*")
        .eq("user_id", user_id)
    )
    response = (
        _scope_family_member(query, family_member_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


def _scope_family_member(query: Any, family_member_id: str | None) -> Any:
    # Null means the owner's own record; a UUID switches to a dependent profile.
    if family_member_id:
        return query.eq("family_member_id", family_member_id)
    return query.is_("family_member_id", "null")


def _active_lifecycle(query: Any) -> Any:
    return query.in_("lifecycle_status", ["active"])


def _apply_status_filter(query: Any, status: str) -> Any:
    """Filter a reports/medications query by display-layer lifecycle status.

    "active" (default) and "archived" narrow to that single lifecycle state;
    an unrecognized value falls back to "active" so a bad query param from
    the frontend can never accidentally widen what AI context or a screen
    sees. "all" applies no lifecycle filter at all, matching what the Data
    Control tab already shows.
    """
    if status == "all":
        return query
    if status == "archived":
        return query.in_("lifecycle_status", ["archived"])
    return _active_lifecycle(query)


def _retention_rows(
    user_id: str,
    table: str,
    family_member_id: str | None = None,
) -> list[dict[str, Any]]:
    query = get_client().table(table).select("*").eq("user_id", user_id)
    response = (
        _scope_family_member(query, family_member_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return response.data or []


def _get_retention_record(
    user_id: str,
    table: str,
    target_id: str | int,
    family_member_id: str | None = None,
) -> dict[str, Any] | None:
    query = (
        get_client()
        .table(table)
        .select("*")
        .eq("user_id", user_id)
        .eq("id", target_id)
    )
    response = _scope_family_member(query, family_member_id).limit(1).execute()
    return response.data[0] if response.data else None


def _insert_lifecycle_event(
    user_id: str,
    family_member_id: str | None,
    target_table: str,
    target_id: str | int,
    action: str,
    completion_status: str,
    previous_status: str | None,
    next_status: str | None,
    reason: str,
    error_message: str | None,
    snapshot: dict[str, Any] | None,
) -> None:
    payload = {
        "user_id": user_id,
        "family_member_id": family_member_id,
        "target_table": target_table,
        "target_id": target_id,
        "action": action,
        "completion_status": completion_status,
        "previous_status": previous_status,
        "next_status": next_status,
        "reason": reason,
        "error_message": error_message,
        "snapshot": snapshot,
        "completed_at": _now() if completion_status in {"complete", "partial", "blocked"} else None,
    }
    get_client().table("data_lifecycle_events").insert(payload).execute()


def _blocked_lifecycle_result(
    target_table: str,
    target_id: str | int,
    action: str,
    error_message: str,
) -> dict[str, Any]:
    return {
        "target_table": target_table,
        "target_id": str(target_id),
        "action": action,
        "lifecycle_status": f"{action}_failed",
        "completion_status": "blocked",
        "message": "Lifecycle action was blocked.",
        "error_message": error_message,
    }


def _lifecycle_message(action: str, table: str, completion_status: str) -> str:
    label = table.replace("_", " ")
    if completion_status == "complete":
        return f"{label.title()} {action} completed and lifecycle state is visible."
    return f"{label.title()} {action} did not fully complete."


def _text_value(value: str | list[str] | tuple[str, ...] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return ", ".join(str(item).strip() for item in value if str(item).strip())


def _list_value(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize user-entered comma text for Supabase text[] columns."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    else:
        parts = [str(item).strip() for item in value]
    empty_markers = {"", "none", "nothing", "nil", "no", "n/a", "na"}
    return [part for part in parts if part.lower() not in empty_markers]


def _retry_scalar_as_array(payload: dict[str, Any], literal: str) -> bool:
    changed = False
    for key, value in list(payload.items()):
        if value == literal:
            payload[key] = _list_value(value)
            changed = True
    return changed


def _retry_declared_arrays(table: str, payload: dict[str, Any]) -> bool:
    changed = False
    for key in TEXT_ARRAY_COLUMNS.get(table, set()):
        if key in payload and isinstance(payload[key], str):
            payload[key] = _list_value(payload[key])
            changed = True
    return changed


def _first_row(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not rows:
        raise RuntimeError("Supabase insert succeeded without returning a row.")
    return rows[0]


def _display_date(value: Any) -> str:
    if not value:
        return "Unknown date"
    return str(value)[:10]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
