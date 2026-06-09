from typing import Any

from backend.app.services.llm import complete
from backend.app.services.medication_repository import MedicationRepository


class MedicationManager:
    def __init__(self, repository: MedicationRepository) -> None:
        self.repository = repository

    async def run(self, action: str, data: dict[str, Any], user_id: str) -> str:
        if action == "add":
            medication = self.repository.add(user_id, data)
            return f"Saved {medication['drug']} {medication['dose']} to the medication list."

        if action == "list":
            medications = self.repository.list(user_id)
            return self._format_list(medications)

        if action == "check_interactions":
            medications = self.repository.list(user_id)
            new_drug = str(data.get("new_drug") or "").strip()
            response = await complete(
                "You provide cautious medication safety information. Never prescribe.",
                f"""
Current medication list: {medications}
Medicine the patient wants to add: {new_drug}

Identify potentially important interactions or duplicate therapies in simple
language. Tell the user to confirm with a pharmacist or doctor before taking it.
Do not claim the list is exhaustive.
""",
            )
            return response or (
                "Interaction checking needs a configured Gemini or Groq API key. Please "
                "confirm the combination with a pharmacist or doctor before taking it."
            )

        if action == "explain":
            drug = str(data.get("drug") or "").strip()
            response = await complete(
                "You explain medicines in simple language without prescribing.",
                f"""
Explain what {drug} commonly does in 3 simple sentences. Include why it may be
prescribed, common side effects to watch for, and a reminder to follow the
prescriber's instructions.
""",
            )
            return response or (
                f"{drug or 'This medicine'} should be taken only as directed by the "
                "prescriber. Add a Gemini or Groq API key for a detailed explanation."
            )

        raise ValueError(f"Unsupported medication action: {action}")

    @staticmethod
    def _format_list(medications: list[dict[str, Any]]) -> str:
        if not medications:
            return "No medications are saved for this profile."
        return "\n".join(
            f"- {item.get('drug', '')} {item.get('dose', '')} at {item.get('times', [])}"
            for item in medications
        )
