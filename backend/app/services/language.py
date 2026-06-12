import re


HINDI_REQUESTS = (
    "hindi",
    "हिंदी",
    "हिन्दी",
)


def wants_hindi(message: str) -> bool:
    text = message.lower()
    return any(token in text for token in HINDI_REQUESTS) or bool(
        re.search(r"[\u0900-\u097f]", message)
    )


def response_language_instruction(message: str) -> str:
    if wants_hindi(message):
        return (
            "Reply in fluent, respectful Hindi written in Devanagari. Use natural "
            "Indian phrasing and avoid unnecessary English words."
        )
    return "Reply in clear, concise English."
