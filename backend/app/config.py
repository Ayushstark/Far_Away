import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def secret(name: str) -> str:
    value = os.getenv(name, "")
    return "" if value in {"your_key", "your_url"} else value


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = secret("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    chroma_path: str = os.getenv("CHROMA_PATH", "memory/chroma")


settings = Settings()
