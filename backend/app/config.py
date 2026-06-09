import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def secret(name: str) -> str:
    value = os.getenv(name, "")
    return "" if not value or value.startswith("your_") else value


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = secret("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_embedding_model: str = os.getenv(
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-001",
    )
    groq_api_key: str = secret("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    chroma_path: str = os.getenv("CHROMA_PATH", "memory/chroma")
    supabase_url: str = secret("SUPABASE_URL")
    supabase_key: str = secret("SUPABASE_KEY")


settings = Settings()
