from datetime import UTC, datetime
from io import BytesIO

from pypdf import PdfReader

from backend.app.services.llm import complete, complete_pdf
from memory.store import HealthMemory


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


async def read_report(
    content: bytes,
    user_id: str,
    memory: HealthMemory,
) -> str:
    text = extract_pdf_text(content)
    past_reports = memory.recall(user_id, "blood report lab test", memory_type="report")
    response = await complete_pdf(
        "You explain medical reports to non-clinicians. Never diagnose.",
        f"""
Previous reports:
{chr(10).join(past_reports) or "None available"}

Read the attached current medical report PDF directly, including tables, charts,
and scanned content when visible.

Do the following:
1. List test values in a simple table: Test | Your value | Normal range | Status.
2. Explain abnormal values in plain language.
3. Compare with previous reports when available.
4. Give 3 cautious lifestyle suggestions based on the findings.
5. Clearly identify values that need prompt doctor attention.

Use simple language and mention that reference ranges can vary by laboratory.
""",
        content,
        max_tokens=1800,
    )
    if not response and text:
        response = await complete(
            "You explain medical reports to non-clinicians. Never diagnose.",
            f"""
Gemini PDF vision was unavailable. Interpret this extracted report text:
{text[:20_000]}

Previous reports:
{chr(10).join(past_reports) or "None available"}

List values in a simple table, explain abnormalities, compare prior reports,
give cautious lifestyle suggestions, and identify prompt doctor-attention needs.
""",
            max_tokens=1800,
            provider="fast",
        )
    if text:
        memory.remember(
            user_id,
            text,
            {"type": "report", "date": datetime.now(UTC).date().isoformat()},
        )
    return response or (
        "CareOS could not interpret this PDF. Check your Gemini or Groq API key "
        "and try again."
    )
