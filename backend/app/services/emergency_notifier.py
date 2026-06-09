from backend.app.config import settings
from backend.app.schemas import EmergencyAssessment


class EmergencyNotifier:
    def __init__(self) -> None:
        self.supabase = None
        if settings.supabase_url and settings.supabase_key:
            try:
                from supabase import create_client

                self.supabase = create_client(settings.supabase_url, settings.supabase_key)
            except Exception:
                self.supabase = None

    def notify_family(
        self,
        profile_id: str,
        message: str,
        assessment: EmergencyAssessment,
    ) -> bool:
        if not self.supabase:
            return False
        try:
            self.supabase.table("emergency_alerts").insert(
                {
                    "user_id": profile_id,
                    "message": message,
                    "severity": assessment.severity,
                    "suspected": assessment.suspected,
                }
            ).execute()
            return True
        except Exception:
            return False
