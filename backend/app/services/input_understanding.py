import re
from dataclasses import dataclass
from typing import Literal

from backend.app.services.language import wants_hindi


InputKind = Literal["casual", "language_request", "healthcare", "unclear"]

LANGUAGE_REQUEST_PATTERNS = (
    r"\b(can|could|will|would)\s+(we|you)\s+(talk|speak|reply|respond)\s+in\s+hindi\b",
    r"\b(reply|respond|talk|speak)\s+in\s+hindi\b",
    r"\bhindi\s+(mein|me)\s+(baat|bolo|boliye|jawab)\b",
)

CASUAL_PATTERNS = (
    r"^(hi+|hello|hey)[!. ]*$",
    r"^(hi+|hello|hey)[, ]+(how are you|what can you do)[?.! ]*$",
    r"^(how are you|who are you|what can you do)[?.! ]*$",
    r"^(thanks|thank you|ok|okay|bye)[!. ]*$",
    r"^(नमस्ते|हैलो|हाय)[।!. ]*$",
    r"^(आप कैसे हैं|तुम कैसे हो)[?।!. ]*$",
)

HEALTHCARE_TERMS = {
    "ache", "allergy", "anxiety", "bleeding", "blood", "breathe", "breathing",
    "cancer", "chest", "cold", "cough", "diabetes", "diagnosis", "diarrhea",
    "dizzy", "doctor", "dose", "fever", "glucose", "headache", "health",
    "heart", "hurt", "injury", "lab", "medicine", "medication", "nausea",
    "pain", "pill", "prescription", "rash", "report", "scan", "sick",
    "stomach", "symptom", "tablet", "test", "tired", "tingling", "vomit",
    "weak", "wound",
}


@dataclass(frozen=True)
class InputUnderstanding:
    kind: InputKind
    wants_hindi: bool = False


def understand_input(message: str) -> InputUnderstanding:
    text = " ".join(message.strip().lower().split())
    hindi = wants_hindi(message)

    if any(re.search(pattern, text) for pattern in LANGUAGE_REQUEST_PATTERNS):
        return InputUnderstanding("language_request", wants_hindi=True)

    if any(re.search(pattern, text) for pattern in CASUAL_PATTERNS):
        return InputUnderstanding("casual", wants_hindi=hindi)

    words = set(re.findall(r"[a-z]+", text))
    if words & HEALTHCARE_TERMS or re.search(r"[\u0900-\u097f]", message):
        return InputUnderstanding("healthcare", wants_hindi=hindi)

    return InputUnderstanding("unclear", wants_hindi=hindi)
