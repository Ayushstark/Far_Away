import hashlib
import math
import re

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from backend.app.config import settings


class GeminiEmbeddingFunction(EmbeddingFunction[Documents]):
    """Gemini embeddings with a deterministic offline development fallback."""

    dimensions = 768
    synonym_groups = (
        ("medicine", "medication", "drug", "tablet", "pill", "dose", "prescription"),
        ("report", "lab", "test", "bloodwork", "result", "scan"),
        ("pain", "ache", "sore", "hurt"),
        ("breathing", "breath", "breathless", "dyspnea"),
        ("doctor", "physician", "specialist", "clinic", "appointment"),
        ("fever", "temperature", "hot", "chills"),
        ("heart", "cardiac", "chest"),
    )

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        if settings.gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=settings.gemini_api_key)
                response = client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=list(input),
                    config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
                )
                return [embedding.values for embedding in response.embeddings]
            except Exception:
                pass
        return [self._offline_embed(document) for document in input]

    @staticmethod
    def name() -> str:
        return "careos-gemini-embedding-v1"

    def get_config(self) -> dict[str, int]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict[str, int]) -> "GeminiEmbeddingFunction":
        return GeminiEmbeddingFunction()

    def _offline_embed(self, document: str) -> list[float]:
        tokens = re.findall(r"[a-z0-9]+", document.lower())
        expanded = list(tokens)
        token_set = set(tokens)
        for group in self.synonym_groups:
            if token_set.intersection(group):
                expanded.extend(group)

        vector = [0.0] * self.dimensions
        for token in expanded:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]
