from anthropic import AsyncAnthropic

from backend.app.config import settings


async def complete(system: str, prompt: str) -> str:
    if not settings.anthropic_api_key:
        return (
            "The agent route is working. Add ANTHROPIC_API_KEY to .env to "
            "generate a personalized response."
        )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=700,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")

