"""In-memory gTTS output for CareOS voice responses."""

import asyncio
from io import BytesIO

from gtts import gTTS


async def generate_speech(text: str, lang: str = "hi") -> BytesIO:
    """Generate Indian-domain Hindi or English MP3 audio without touching disk."""

    def synthesize() -> BytesIO:
        audio = BytesIO()
        gTTS(text=text, lang=lang, tld="co.in").write_to_fp(audio)
        audio.seek(0)
        return audio

    # gTTS performs blocking network I/O, so keep it off FastAPI's event loop.
    return await asyncio.to_thread(synthesize)
