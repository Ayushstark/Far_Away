from backend.app.services.llm import complete
from backend.app.services.language import response_language_instruction


async def analyze_symptoms(message: str, health_history: list[str]) -> str:
    history = "\n".join(health_history) or "No relevant history available."
    response = await complete(
        (
            "You are a proactive clinical information assistant. Never claim a "
            "confirmed diagnosis. Use OPQRST and OLD CART to structure symptom "
            "assessment before offering a cautious differential. "
            "Use respectful, age-neutral language. In English, address the patient "
            "as 'you'. In Hindi, address the patient as 'आप'. Never use familial "
            "labels such as beta, beti, uncle, or aunty."
        ),
        f"""
Patient history:
{history}

Patient says: {message!r}

Proactively assess the symptom using OPQRST / OLD CART:
- Onset: when and how it started
- Provocation/Palliation: what worsens or relieves it
- Quality/Character: what it feels like
- Region/Radiation: where it is and whether it spreads
- Severity: 0-10 and effect on normal activity
- Timing: constant/intermittent, duration, pattern, and progression
- Associated symptoms and relevant context

Use the patient message and history to identify what is already known. Ask only
the 2-4 most important MISSING questions, in a natural conversational style.
Then provide:
1. A short "What this could mean" section with 2-3 plausible possibilities and
   why, clearly labeled as a differential rather than a diagnosis.
2. The most appropriate doctor/care setting and urgency.
3. One low-risk action they can take now.
4. Specific red flags that should trigger urgent care.

{response_language_instruction(message)}
Do not mix Hindi and English unless the user explicitly asks for Hinglish.
Be concise and never alarming.
Never use familial labels such as beta, beti, uncle, or aunty. Always end with:
the equivalent of "This is not a diagnosis. Please see a doctor." in the
selected response language.
""",
        max_tokens=1500,
        provider="reasoning",
    )
    if response and len(response) >= 250 and ("?" in response or "？" in response):
        return _ensure_complete_symptom_response(response, message)
    if response:
        return _ensure_complete_symptom_response(response.rstrip() + "\n\n" + _opqrst_fallback(message), message)
    return _opqrst_fallback(message)


def _opqrst_fallback(message: str) -> str:
    if response_language_instruction(message).startswith("Reply in fluent"):
        return (
            "इसे ठीक से समझने के लिए कृपया बताएँ: यह कब और कैसे शुरू हुआ? "
            "किस चीज़ से बढ़ता या कम होता है? यह कैसा महसूस होता है और कहाँ है, "
            "क्या कहीं फैलता है? इसकी तीव्रता 0-10 में कितनी है, और यह लगातार है "
            "या आता-जाता है? साथ में कोई अन्य लक्षण भी बताएँ। संभावित कारणों में "
            "मांसपेशी/नस की समस्या, दवा का प्रभाव, या किसी मौजूदा स्थिति से जुड़ा "
            "लक्षण शामिल हो सकता है; डॉक्टर सही कारण की जाँच कर सकते हैं। यदि दर्द "
            "अचानक बहुत तेज हो, कमजोरी, बेहोशी, सीने में दर्द या सांस की तकलीफ हो "
            "तो तुरंत चिकित्सा सहायता लें।\n\nयह निदान नहीं है। कृपया डॉक्टर से मिलें।"
        )
    return (
        "To understand this properly: when did it start, what makes it better or "
        "worse, what does it feel like, where exactly is it, and how severe is it "
        "from 0-10? Please also mention whether it is constant or comes and goes, "
        "and any other symptoms. Possibilities may include a muscle or nerve issue, "
        "a medication effect, or a symptom related to an existing condition; a "
        "doctor can assess the cause. Seek urgent help for sudden severe pain, new "
        "weakness, fainting, chest pain, or breathing difficulty.\n\n"
        "This is not a diagnosis. Please see a doctor."
    )


def _ensure_complete_symptom_response(response: str, message: str) -> str:
    text = response.strip()
    english_disclaimer = "This is not a diagnosis. Please see a doctor."
    hindi_disclaimer = "यह निदान नहीं है। कृपया डॉक्टर से मिलें।"
    disclaimer = (
        hindi_disclaimer
        if response_language_instruction(message).startswith("Reply in fluent")
        else english_disclaimer
    )

    for fragment in ("This", "This is", "This is not", "This is not a", "This is not a diagnosis"):
        if text.endswith(fragment):
            text = text[: -len(fragment)].rstrip()
            break

    if disclaimer not in text:
        text = f"{text}\n\n{disclaimer}".strip()
    return text
