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
        _scope_family_member(query, family_member_id)
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
        _scope_family_member(query, family_member_id)
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
        _scope_family_member(query, family_member_id)
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
) -> list[dict[str, Any]]:
    query = (
        get_client()
        .table("medications")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
    )
    response = (
        _scope_family_member(query, family_member_id)
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
        _scope_family_member(query, family_member_id)
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
) -> list[dict[str, Any]]:
    query = get_client().table("reports").select("*").eq("user_id", user_id)
    response = (
        _scope_family_member(query, family_member_id)
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


def _scope_family_member(query: Any, family_member_id: str | None) -> Any:
    # Null means the owner's own record; a UUID switches to a dependent profile.
    if family_member_id:
        return query.eq("family_member_id", family_member_id)
    return query.is_("family_member_id", "null")


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
