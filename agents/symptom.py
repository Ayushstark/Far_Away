from backend.app.services.llm import complete


async def analyze_symptoms(message: str, health_history: list[str]) -> str:
    history = "\n".join(health_history) or "No relevant history available."
    response = await complete(
        "You are a careful clinical information assistant. Never diagnose.",
        f"""
Patient history:
{history}

Patient says: {message!r}

Do the following:
1. Ask 2-3 focused follow-up questions.
2. List possible causes with brief reasoning, clearly framed as possibilities.
3. Suggest what type of doctor or care setting may be appropriate.
4. Give one low-risk practical thing they can do right now.

Use simple Hindi-English mix when natural. Never be alarming. Always end with:
"This is not a diagnosis. Please see a doctor."
""",
    )
    if response:
        return response
    return (
        "Aapko yeh problem kab se hai, severity kitni hai, aur koi fever, injury, "
        "breathing issue, ya new medicine bhi hai? Common causes context par depend "
        "karte hain, so a primary-care doctor can assess it properly. Abhi rest, "
        "hydration, and symptom timing note karna useful hoga.\n\n"
        "This is not a diagnosis. Please see a doctor."
    )
