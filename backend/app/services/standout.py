"""Deterministic standout dashboard helpers.

These helpers turn existing Supabase data into useful demo surfaces without
spending LLM tokens. Agents still handle reasoning; this layer helps users see
what CareOS already knows at a glance.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.app import db
from backend.app.schemas import DailyPlanItem, TimelineItem


def build_daily_plan(user_id: str, family_member_id: str | None = None) -> list[DailyPlanItem]:
    events = _safe(lambda: db.get_recent_health_events(user_id, family_member_id, limit=8), [])
    unresolved = _safe(lambda: db.get_unresolved_events(user_id, family_member_id, limit=1), [])
    medications = _safe(lambda: db.get_medications(user_id, family_member_id), [])
    reports = _safe(lambda: db.get_reports(user_id, family_member_id, limit=3), [])

    items: list[DailyPlanItem] = []

    if unresolved:
        event = unresolved[0]
        concern = _short(event.get("description"), "Recent symptom")
        items.append(DailyPlanItem(
            type="symptom",
            title=f"Check: {concern}",
            detail="Tell CareOS if it is better, worse, or about the same.",
            priority=_priority_from_severity(event.get("severity")),
            action_text=f"How is this feeling now: {concern}?",
        ))
    elif events:
        event = events[0]
        concern = _short(event.get("description"), "Recent health update")
        items.append(DailyPlanItem(
            type="symptom",
            title=f"Latest concern: {concern}",
            detail="Track any change in severity, timing, or triggers today.",
            priority=_priority_from_severity(event.get("severity")),
            action_text=f"Give me follow-up advice for: {concern}",
        ))

    if medications:
        med = medications[0]
        timing = _as_text(med.get("timing")) or med.get("frequency") or "as prescribed"
        items.append(DailyPlanItem(
            type="medicine",
            title=f"Medicine: {med.get('drug_name') or 'Active medication'}",
            detail=f"{med.get('dose') or 'Dose not listed'} - {timing}.",
            priority="high",
            action_text=f"Explain how to take {med.get('drug_name') or 'this medicine'} safely.",
        ))

    report = _latest_flagged_report(reports) or (reports[0] if reports else None)
    if report:
        flagged_count = len(_flagged_values(report))
        items.append(DailyPlanItem(
            type="report",
            title=report.get("report_type") or "Latest report",
            detail=(
                f"{flagged_count} flagged value{'s' if flagged_count != 1 else ''} need review."
                if flagged_count
                else _short(report.get("ai_summary"), "No flagged values in the latest summary.")
            ),
            priority="high" if flagged_count else "low",
            action_text="Summarize my latest report and what I should ask the doctor.",
        ))

    if len(items) < 3:
        items.append(DailyPlanItem(
            type="habit",
            title="Today: small health check",
            detail="Note sleep, water intake, BP/sugar if relevant, and any symptom trigger.",
            priority="low",
            action_text="Help me make a simple health checklist for today.",
        ))

    return items[:4]


def build_health_timeline(user_id: str, family_member_id: str | None = None) -> list[TimelineItem]:
    events = _safe(lambda: db.get_recent_health_events(user_id, family_member_id, limit=10), [])
    reports = _safe(lambda: db.get_reports(user_id, family_member_id, limit=8), [])
    medications = _safe(lambda: db.get_medications(user_id, family_member_id), [])
    items: list[dict[str, Any]] = []

    for event in events:
        items.append({
            "sort": event.get("created_at") or "",
            "item": TimelineItem(
                date=_date_label(event.get("created_at")),
                category="symptom",
                title=_title(event.get("event_type"), "Health event"),
                detail=_short(event.get("description"), "No description recorded.", 140),
                severity=event.get("severity"),
                status="resolved" if event.get("resolved") else "open",
            ),
        })

    for report in reports:
        flags = _flagged_values(report)
        items.append({
            "sort": report.get("report_date") or report.get("uploaded_at") or "",
            "item": TimelineItem(
                date=_date_label(report.get("report_date") or report.get("uploaded_at")),
                category="report",
                title=report.get("report_type") or "Report",
                detail=_short(report.get("ai_summary"), "Report saved.", 150),
                severity="flagged" if flags else "normal",
                status=f"{len(flags)} flagged" if flags else "reviewed",
            ),
        })

    for med in medications[:5]:
        items.append({
            "sort": med.get("start_date") or med.get("created_at") or "",
            "item": TimelineItem(
                date=_date_label(med.get("start_date") or med.get("created_at")),
                category="medication",
                title=med.get("drug_name") or "Medication",
                detail=f"{med.get('dose') or 'Dose not listed'} - {_as_text(med.get('timing')) or med.get('frequency') or 'as prescribed'}",
                severity=None,
                status="active",
            ),
        })

    items.sort(key=lambda entry: entry["sort"], reverse=True)
    return [entry["item"] for entry in items[:14]]


def _safe(call, fallback):
    try:
        return call()
    except Exception:
        return fallback


def _short(value: Any, fallback: str, limit: int = 90) -> str:
    text = " ".join(str(value or fallback).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "").strip()


def _flagged_values(report: dict[str, Any]) -> dict[str, Any]:
    flagged = report.get("flagged_values")
    return flagged if isinstance(flagged, dict) else {}


def _latest_flagged_report(reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((report for report in reports if _flagged_values(report)), None)


def _priority_from_severity(severity: Any) -> str:
    if str(severity or "").lower() in {"high", "critical", "severe"}:
        return "high"
    if str(severity or "").lower() in {"moderate", "medium"}:
        return "medium"
    return "low"


def _date_label(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if text else date.today().isoformat()


def _title(value: Any, fallback: str) -> str:
    return str(value or fallback).replace("_", " ").strip().title()
