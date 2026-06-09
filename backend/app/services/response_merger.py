from backend.app.schemas import AgentResult
from backend.app.services.llm import complete


async def merge_responses(results: list[AgentResult]) -> str:
    if not results:
        return "Please share a little more detail so CareOS can route your request."
    if len(results) == 1:
        return results[0].summary

    combined = "\n\n".join(f"{item.agent}: {item.summary}" for item in results)
    response = await complete(
        "Merge specialist healthcare-assistant results without adding new claims.",
        f"""
Combine these specialist responses into one concise, organized answer. Preserve
all safety disclaimers and avoid diagnosis:

{combined}
""",
        max_tokens=1400,
        provider="reasoning",
    )
    return response or combined
