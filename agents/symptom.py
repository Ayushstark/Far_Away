from backend.app.services.llm import complete
from backend.app.services.language import response_language_instruction


async def analyze_symptoms(message: str, health_history: list[str]) -> str:
    history = "\n".join(health_history) or "No relevant history available."
    response = await complete(
        (
            "You are a careful clinical information assistant. Never diagnose. "
            "Use respectful, age-neutral language. In English, address the patient "
            "as 'you'. In Hindi, address the patient as 'आप'. Never use familial "
            "labels such as beta, beti, uncle, or aunty."
        ),
        f"""
Patient history:
{history}

Patient says: {message!r}

Do the following:
1. Ask 2-3 focused follow-up questions.
2. List possible causes with brief reasoning, clearly framed as possibilities.
3. Suggest what type of doctor or care setting may be appropriate.
4. Give one low-risk practical thing they can do right now.

{response_language_instruction(message)}
Do not mix Hindi and English unless the user explicitly asks for Hinglish.
Be concise and never alarming.
Never use familial labels such as beta, beti, uncle, or aunty. Always end with:
the equivalent of "This is not a diagnosis. Please see a doctor." in the
selected response language.
""",
    )
    if response:
        return response
    return (
        "When did this start, how severe is it, and do you have fever, injury, "
        "breathing difficulty, or a new medicine? A primary-care doctor can assess "
        "the cause. For now, rest, hydrate, and note when symptoms occur.\n\n"
        "This is not a diagnosis. Please see a doctor."
    )
