from typing import Any

from backend.app.config import settings


class MedicationRepository:
    def __init__(self) -> None:
        self.local: dict[str, list[dict[str, Any]]] = {}
        self.supabase = None
        if settings.supabase_url and settings.supabase_key:
            try:
                from supabase import create_client

                self.supabase = create_client(settings.supabase_url, settings.supabase_key)
            except Exception:
                self.supabase = None

    def add(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        medication = {
            "user_id": user_id,
            "drug": str(data.get("name") or data.get("drug") or "").strip(),
            "dose": str(data.get("dose") or "").strip(),
            "times": data.get("times") or [],
        }
        if not medication["drug"]:
            raise ValueError("Medication name is required.")

        if self.supabase:
            try:
                result = self.supabase.table("medications").insert(medication).execute()
                if result.data:
                    return result.data[0]
            except Exception:
                pass

        self.local.setdefault(user_id, []).append(medication)
        return medication

    def list(self, user_id: str) -> list[dict[str, Any]]:
        if self.supabase:
            try:
                result = (
                    self.supabase.table("medications")
                    .select("*")
                    .eq("user_id", user_id)
                    .execute()
                )
                return result.data or []
            except Exception:
                pass
        return self.local.get(user_id, [])
