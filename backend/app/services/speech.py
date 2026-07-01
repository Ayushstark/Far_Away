"""In-memory gTTS output for CareOS voice responses."""

import asyncio
import re
from io import BytesIO

from gtts import gTTS


def sanitize_tts_text(text: str) -> str:
    """Convert assistant text into natural speech text before it reaches gTTS."""
    cleaned = text
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"[*_~#>`]+", " ", cleaned)
    cleaned = re.sub(r"^\s*[-•]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+[.)]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", cleaned)
    cleaned = cleaned.replace("|", ", ")
    cleaned = cleaned.replace("OPQRST", "O P Q R S T")
    cleaned = cleaned.replace("OLD CART", "O L D C A R T")

    # Keep CareOS persona phrasing gender-neutral for Hindi speech.
    neutral_phrases = {
        "मैं ठीक हूँ": "CareOS आपकी सहायता के लिए तैयार है",
        "मैं आपकी सहायता कर सकता हूँ": "CareOS आपकी सहायता के लिए तैयार है",
        "मैं आपकी मदद कर सकता हूँ": "CareOS आपकी मदद के लिए तैयार है",
        "मैं आपसे हिंदी में बात कर सकता हूँ": "CareOS से हिंदी में बात हो सकती है",
        "CareOS आपसे हिंदी में बात कर सकता है": "CareOS से हिंदी में बात हो सकती है",
        "मैं सही CareOS एजेंट चुन सकूँ": "CareOS सही एजेंट चुन पाए",
        "मैं आपकी बात सही तरह समझना चाहता हूँ": "CareOS को आपकी बात सही तरह समझनी है",
        "CareOS आपकी बात सही तरह समझना चाहता है": "CareOS को आपकी बात सही तरह समझनी है",
        "मैं इस लक्षण को ठीक हुआ दर्ज कर रहा हूँ": "CareOS में यह लक्षण ठीक हुआ दर्ज हो जाएगा",
        "CareOS इस लक्षण को ठीक हुआ दर्ज कर रहा है": "CareOS में यह लक्षण ठीक हुआ दर्ज हो जाएगा",
    }
    for phrase, replacement in neutral_phrases.items():
        cleaned = cleaned.replace(phrase, replacement)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "CareOS response is available on screen."


async def generate_speech(text: str, lang: str = "hi") -> BytesIO:
    """Generate Indian-domain Hindi or English MP3 audio without touching disk."""

    def synthesize() -> BytesIO:
        audio = BytesIO()
        gTTS(text=sanitize_tts_text(text), lang=lang, tld="co.in").write_to_fp(audio)
        audio.seek(0)
        return audio

    # gTTS performs blocking network I/O, so keep it off FastAPI's event loop.
    return await asyncio.to_thread(synthesize)
