from io import BytesIO
from textwrap import wrap

from backend.app.services.llm import complete
from memory.store import HealthMemory


async def create_care_brief(
    user_id: str,
    memory: HealthMemory | None = None,
    health_history: str | None = None,
    current_medications: list[dict] | None = None,
    user_profile: dict | None = None,
) -> str:
    history = health_history or (
        "\n".join(memory.history(user_id)) if memory else "No history available."
    )
    recent_symptoms = (
        memory.recall(user_id, "recent symptoms complaint", limit=8)
        if memory
        else []
    )
    medication_list = current_medications or []
    response = await complete(
        "You create clear, printer-friendly doctor visit briefs. Never diagnose.",
        f"""
Patient profile: {user_profile or "Not available"}
Health history: {history}
Current medications: {medication_list}
Recent complaints: {recent_symptoms}

Format as:
1. Patient summary
2. Current medications
3. Timeline of recent symptoms
4. Specific questions to ask the doctor
5. Things to monitor after the visit
""",
        max_tokens=1600,
        provider="reasoning",
    )
    return response or (
        "PATIENT SUMMARY\nNo generated summary is available until a Gemini or Groq "
        "API key is configured.\n\nCURRENT MEDICATIONS\n"
        + MedicationRepositoryText.format(medication_list)
        + "\n\nRECENT HEALTH MEMORY\n"
        + ("\n".join(f"- {item}" for item in recent_symptoms) or "- None saved")
    )


class MedicationRepositoryText:
    @staticmethod
    def format(items: list[dict]) -> str:
        return (
            "\n".join(
                f"- {item.get('drug_name') or item.get('drug')} {item.get('dose')}"
                for item in items
            )
            or "- None saved"
        )


def brief_to_pdf(brief: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 54
    page.setTitle("CareOS Doctor Visit Brief")
    page.setFont("Helvetica-Bold", 16)
    page.drawString(48, y, "CareOS Doctor Visit Brief")
    y -= 30
    page.setFont("Helvetica", 10)
    for paragraph in brief.splitlines():
        for line in wrap(paragraph, width=95) or [""]:
            if y < 48:
                page.showPage()
                page.setFont("Helvetica", 10)
                y = height - 48
            page.drawString(48, y, line)
            y -= 14
    page.save()
    return buffer.getvalue()
