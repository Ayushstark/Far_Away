import json
import re
from typing import Any, Literal

from backend.app.config import settings

Provider = Literal["reasoning", "fast"]


def is_configured() -> bool:
    return bool(settings.gemini_api_key or settings.groq_api_key)


async def complete(
    system: str,
    prompt: str,
    max_tokens: int = 900,
    provider: Provider = "fast",
) -> str:
    providers = (
        (_gemini_complete, _groq_complete)
        if provider == "reasoning"
        else (_groq_complete, _gemini_complete)
    )
    for generate in providers:
        response = await generate(system, prompt, max_tokens)
        if response:
            return response
    return ""


async def complete_json(
    system: str,
    prompt: str,
    fallback: dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any]:
    response = await complete(
        f"{system} Return valid JSON only, without markdown fences or commentary.",
        prompt,
        provider="reasoning",
    )
    if not response:
        return fallback

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", response, re.DOTALL)
        if not match:
            return fallback
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return fallback


async def complete_pdf(system: str, prompt: str, content: bytes, max_tokens: int = 1800) -> str:
    if not settings.gemini_api_key:
        return ""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=[
                prompt,
                types.Part.from_bytes(data=content, mime_type="application/pdf"),
            ],
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text or ""
    except Exception:
        return ""


async def _gemini_complete(system: str, prompt: str, max_tokens: int) -> str:
    if not settings.gemini_api_key:
        return ""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text or ""
    except Exception:
        return ""


async def _groq_complete(system: str, prompt: str, max_tokens: int) -> str:
    if not settings.groq_api_key:
        return ""
    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.groq_api_key)
        response = await client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception:
        return ""
