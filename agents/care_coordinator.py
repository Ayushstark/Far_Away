from io import BytesIO
from textwrap import wrap

from backend.app import db
from backend.app.services.llm import complete
from backend.app.services.llm import complete_json
from memory.store import HealthMemory


async def generate_proactive_greeting(
    user_id: str,
    family_member_id: str | None = None,
    preferred_language: str = "en",
) -> str:
    """Generate the short, contextual message CareOS uses to speak first."""
    unresolved_events = db.get_unresolved_events(user_id, family_member_id, limit=1)
    recent_events = db.get_recent_health_events(user_id, family_member_id, limit=5)
    medications = db.get_medications(user_id, family_member_id)
    profile = db.get_user(user_id) or {}
    name = profile.get("name") or "there"
    if unresolved_events:
        event = unresolved_events[0]
        description = event.get("description") or "the symptom you mentioned"
        if preferred_language == "hi":
            return f"नमस्ते {name}। पिछली बार आपने {description} बताया था। अब आप बेहतर, बदतर या पहले जैसे महसूस कर रहे हैं?"
        return f"Hello {name}. Last time you mentioned {description}. Are you feeling better, worse, or about the same?"
    response = await complete(
        "You are CareOS, a warm proactive health companion. Never diagnose.",
        f"""
The user just opened the app.
User: {profile}
Last 5 health events: {recent_events}
Active medications: {medications}

Generate ONE proactive greeting of only 1-2 short sentences.
- If an unresolved symptom exists, ask how it is feeling now.
- If a medication or checkup seems due based on dates, mention it.
- Otherwise, warmly reference a known condition or recent health context.
- Sound caring, natural, and respectful, not clinical or patronizing.
- Never call the user beta, son, daughter, uncle, aunty, or another familial title.
- Vary the phrasing. Do not include headings, bullets, or a medical disclaimer.
- Reply entirely in {"fluent Hindi using Devanagari" if preferred_language == "hi" else "natural English"}.
""",
        max_tokens=120,
        provider="reasoning",
    )
    # A model occasionally returns only "Hello"; reject that so speaking first
    # always feels meaningfully proactive.
    if response and len(response.split()) >= 7:
        return response.strip()

    return _fallback_proactive_greeting(name, recent_events, medications, preferred_language)


async def generate_daily_digest(
    user_id: str,
    family_member_id: str | None = None,
    preferred_language: str = "en",
) -> list[dict]:
    events = db.get_recent_health_events(user_id, family_member_id, limit=10)
    medications = db.get_medications(user_id, family_member_id)
    reports = db.get_reports(user_id, family_member_id, limit=3)
    fallback = _daily_digest_fallback(events, medications, reports, preferred_language)
    result = await complete_json(
        "You create short, useful daily health insight cards without diagnosing.",
        f"""
Recent health events: {events}
Active medications: {medications}
Recent reports: {reports}

Generate 1-3 insight cards for today. Each card must use exactly one type:
medication_reminder, trend_positive, followup_question, or report_alert.
Each text must be one short sentence. Reply in
{"fluent Hindi using Devanagari" if preferred_language == "hi" else "natural English"}.
Return JSON array: [{{"type": "...", "icon_emoji": "...", "text": "..."}}]
""",
        fallback,
        provider="reasoning",
    )
    if not isinstance(result, list):
        return fallback
    valid_types = {
        "medication_reminder",
        "trend_positive",
        "followup_question",
        "report_alert",
    }
    cards = [
        {
            "type": item.get("type"),
            "icon_emoji": str(item.get("icon_emoji") or "•"),
            "text": str(item.get("text") or "").strip(),
        }
        for item in result[:3]
        if isinstance(item, dict)
        and item.get("type") in valid_types
        and str(item.get("text") or "").strip()
    ]
    return cards or fallback


def _daily_digest_fallback(
    events: list[dict],
    medications: list[dict],
    reports: list[dict],
    preferred_language: str,
) -> list[dict]:
    cards: list[dict] = []
    if medications:
        drug = medications[0].get("drug_name") or "your medicine"
        cards.append({
            "type": "medication_reminder",
            "icon_emoji": "💊",
            "text": f"आज {drug} समय पर लें।" if preferred_language == "hi" else f"Take {drug} on time today.",
        })
    unresolved = next((event for event in events if event.get("resolved") is False), None)
    if unresolved:
        description = unresolved.get("description") or "your recent symptom"
        cards.append({
            "type": "followup_question",
            "icon_emoji": "💬",
            "text": f"आज {description} कैसा है?" if preferred_language == "hi" else f"How is {description} today?",
        })
    flagged = next((report for report in reports if report.get("flagged_values")), None)
    if flagged:
        cards.append({
            "type": "report_alert",
            "icon_emoji": "📋",
            "text": "अपनी हाल की रिपोर्ट के चिन्हित मान डॉक्टर से साझा करें।" if preferred_language == "hi" else "Review the flagged values in your recent report with your doctor.",
        })
    return cards[:3] or [{
        "type": "trend_positive",
        "icon_emoji": "✓",
        "text": "आज अपनी सेहत पर एक छोटा ध्यान दें।" if preferred_language == "hi" else "Take one small moment to check in with your health today.",
    }]


def _fallback_proactive_greeting(
    name: str,
    recent_events: list[dict],
    medications: list[dict],
    preferred_language: str = "en",
) -> str:
    unresolved = next(
        (event for event in recent_events if event.get("resolved") is False),
        None,
    )
    if unresolved:
        description = unresolved.get("description") or "the symptom you mentioned"
        if preferred_language == "hi":
            return f"नमस्ते {name}। पिछली बार आपने {description} बताया था। अब आप कैसा महसूस कर रहे हैं?"
        return f"Hello {name}. How are you feeling now after {description.lower()}?"
    if medications:
        drug = medications[0].get("drug_name") or "your medicine"
        if preferred_language == "hi":
            return f"नमस्ते {name}। आज आप कैसा महसूस कर रहे हैं, और क्या आपने {drug} समय पर ली?"
        return f"Hello {name}. How are you feeling today, and are you on track with {drug}?"
    if preferred_language == "hi":
        return f"नमस्ते {name}। पिछली CareOS बातचीत के बाद से आपकी तबीयत कैसी रही है?"
    return f"Hello {name}. How have you been feeling since your last CareOS check-in?"


async def specialist_advice(
    message: str,
    health_history: str,
    preferred_language: str = "en",
) -> str:
    response = await complete(
        "You help patients choose an appropriate doctor without diagnosing.",
        f"""
Recurring symptom: {message}
Recent history: {health_history}

Suggest the most appropriate specialist or care setting and explain why in
2-3 concise sentences. Reply entirely in
{"fluent Hindi using Devanagari" if preferred_language == "hi" else "natural English"}.
""",
        max_tokens=220,
        provider="reasoning",
    )
    if response:
        return response
    return (
        "बार-बार होने वाले लक्षण के लिए प्राथमिक चिकित्सक से समय लें; वे जरूरत के अनुसार विशेषज्ञ के पास भेज सकते हैं।"
        if preferred_language == "hi"
        else "Because this symptom is recurring, arrange a primary-care visit; they can refer you to the right specialist."
    )


async def create_care_brief(
    user_id: str,
    memory: HealthMemory | None = None,
    health_history: str | None = None,
    current_medications: list[dict] | None = None,
    user_profile: dict | None = None,
    preferred_language: str = "en",
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
Reply entirely in {"fluent Hindi using Devanagari" if preferred_language == "hi" else "natural English"}.
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
