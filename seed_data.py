"""Populate Supabase with a repeatable CareOS hackathon demo profile."""

from datetime import date, datetime, timedelta, timezone
import re
from typing import Any

from backend.app.db import get_client
from postgrest.exceptions import APIError


DEMO_USER_ID = 9_000_001
MISSING_COLUMN = re.compile(r"Could not find the '([^']+)' column")


def iso_days_ago(days: int, hour: int = 9) -> str:
    value = datetime.now(timezone.utc) - timedelta(days=days)
    return value.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def upsert_compatible(client: Any, table: str, rows: dict | list[dict]) -> None:
    """Skip optional demo fields that have not yet been added to a live schema."""
    payload = rows
    while True:
        try:
            client.table(table).upsert(payload, on_conflict="id").execute()
            return
        except APIError as exc:
            match = MISSING_COLUMN.search(str(exc))
            if not match:
                raise
            missing = match.group(1)
            print(f"Skipping unavailable {table}.{missing} column.")
            if isinstance(payload, list):
                payload = [{key: value for key, value in row.items() if key != missing} for row in payload]
            else:
                payload = {key: value for key, value in payload.items() if key != missing}


def seed() -> None:
    client = get_client()

    # Stable IDs and upserts make the demo safe to refresh before each presentation.
    user = {
        "id": DEMO_USER_ID,
        "name": "Ramesh Gupta",
        "age": 52,
        "gender": "male",
        "blood_group": "B+",
        "known_conditions": "type 2 diabetes, hypertension",
        "allergies": "penicillin",
        "emergency_contact": "+91 98765 43210",
        "emergency_contacts": "+91 98765 43210",
    }
    upsert_compatible(client, "users", user)

    events = [
        {
            "id": 9_100_001,
            "user_id": DEMO_USER_ID,
            "event_type": "symptom_analysis",
            "description": "Mild headache and tiredness after a busy workday.",
            "ai_response": "Hydrate, check blood pressure, and seek care if the headache becomes severe.",
            "severity": "mild",
            "body_part": "head",
            "resolved": True,
            "created_at": iso_days_ago(82),
        },
        {
            "id": 9_100_002,
            "user_id": DEMO_USER_ID,
            "event_type": "medication_management",
            "description": "Asked whether metformin should be taken with breakfast.",
            "ai_response": "Take it with food as prescribed to reduce stomach upset.",
            "severity": "none",
            "body_part": None,
            "resolved": True,
            "created_at": iso_days_ago(64),
        },
        {
            "id": 9_100_003,
            "user_id": DEMO_USER_ID,
            "event_type": "report_reading",
            "description": "Reviewed April diabetes and lipid blood report.",
            "ai_response": "HbA1c and LDL were above target; discuss the trend at the next appointment.",
            "severity": "moderate",
            "body_part": None,
            "resolved": True,
            "created_at": iso_days_ago(45),
        },
        {
            "id": 9_100_004,
            "user_id": DEMO_USER_ID,
            "event_type": "symptom_analysis",
            "description": "Occasional tingling in both feet, mostly at night.",
            "ai_response": "Track frequency and arrange a diabetes review to discuss possible nerve irritation.",
            "severity": "moderate",
            "body_part": "feet",
            "resolved": False,
            "created_at": iso_days_ago(24),
        },
        {
            "id": 9_100_005,
            "user_id": DEMO_USER_ID,
            "event_type": "care_coordination",
            "description": "Prepared questions for a follow-up with the physician.",
            "ai_response": "Ask about HbA1c targets, home blood-pressure readings, and foot screening.",
            "severity": "none",
            "body_part": None,
            "resolved": True,
            "created_at": iso_days_ago(9),
        },
    ]
    upsert_compatible(client, "health_events", events)

    medications = [
        {
            "id": 9_200_001,
            "user_id": DEMO_USER_ID,
            "drug_name": "Metformin",
            "dose": "500 mg",
            "frequency": "twice daily",
            "timing": "8:00 AM, 8:00 PM",
            "with_food": True,
            "prescribed_by": "Dr. Neha Verma",
            "start_date": (date.today() - timedelta(days=365)).isoformat(),
            "is_active": True,
        },
        {
            "id": 9_200_002,
            "user_id": DEMO_USER_ID,
            "drug_name": "Telmisartan",
            "dose": "40 mg",
            "frequency": "once daily",
            "timing": "8:00 AM",
            "with_food": False,
            "prescribed_by": "Dr. Neha Verma",
            "start_date": (date.today() - timedelta(days=280)).isoformat(),
            "is_active": True,
        },
        {
            "id": 9_200_003,
            "user_id": DEMO_USER_ID,
            "drug_name": "Atorvastatin",
            "dose": "10 mg",
            "frequency": "once daily",
            "timing": "9:00 PM",
            "with_food": False,
            "prescribed_by": "Dr. Neha Verma",
            "start_date": (date.today() - timedelta(days=180)).isoformat(),
            "is_active": True,
        },
        {
            "id": 9_200_004,
            "user_id": DEMO_USER_ID,
            "drug_name": "Vitamin D3",
            "dose": "60,000 IU",
            "frequency": "once weekly",
            "timing": "Sunday, 1:00 PM",
            "with_food": True,
            "prescribed_by": "Dr. Neha Verma",
            "start_date": (date.today() - timedelta(days=60)).isoformat(),
            "is_active": True,
        },
    ]
    upsert_compatible(client, "medications", medications)

    reports = [
        {
            "id": 9_300_001,
            "user_id": DEMO_USER_ID,
            "report_type": "Diabetes and lipid panel",
            "file_url": "https://example.com/careos-demo/january-labs.pdf",
            "report_date": (date.today() - timedelta(days=88)).isoformat(),
            "lab_name": "Lucknow Diagnostic Centre",
            "ai_summary": (
                "HbA1c is 8.4%, above the usual diabetes target. Fasting glucose is "
                "154 mg/dL and LDL is 132 mg/dL. Kidney markers are within range."
            ),
            "flagged_values": {
                "HbA1c": {"value": "8.4%", "status": "high"},
                "fasting_glucose": {"value": "154 mg/dL", "status": "high"},
                "LDL": {"value": "132 mg/dL", "status": "high"},
            },
            "uploaded_at": iso_days_ago(88),
        },
        {
            "id": 9_300_002,
            "user_id": DEMO_USER_ID,
            "report_type": "Diabetes follow-up panel",
            "file_url": "https://example.com/careos-demo/april-labs.pdf",
            "report_date": (date.today() - timedelta(days=32)).isoformat(),
            "lab_name": "Lucknow Diagnostic Centre",
            "ai_summary": (
                "HbA1c improved to 7.8% but remains above target. Fasting glucose "
                "improved to 138 mg/dL. Vitamin D is low at 18 ng/mL."
            ),
            "flagged_values": {
                "HbA1c": {"value": "7.8%", "status": "high, improving"},
                "fasting_glucose": {"value": "138 mg/dL", "status": "high, improving"},
                "vitamin_D": {"value": "18 ng/mL", "status": "low"},
            },
            "uploaded_at": iso_days_ago(32),
        },
    ]
    upsert_compatible(client, "reports", reports)

    print("CareOS demo data is ready for Ramesh Gupta.")
    print(f"Demo user ID: {DEMO_USER_ID}")


if __name__ == "__main__":
    seed()
