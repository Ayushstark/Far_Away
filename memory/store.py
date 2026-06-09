from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.config import settings
from memory.embeddings import GeminiEmbeddingFunction


class HealthMemory:
    def __init__(self, path: str | None = None, persistent: bool = True) -> None:
        self.collection = None
        self.path = path or settings.chroma_path
        try:
            import chromadb

            if persistent:
                Path(self.path).mkdir(parents=True, exist_ok=True)
                client = chromadb.PersistentClient(path=self.path)
            else:
                client = chromadb.EphemeralClient()
            self.collection = client.get_or_create_collection(
                "health_memory_v3",
                embedding_function=GeminiEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            self.collection = None

    @property
    def available(self) -> bool:
        return self.collection is not None

    def remember(
        self,
        profile_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if not self.collection or not text.strip():
            return None

        memory_id = f"{profile_id}_{datetime.now(UTC).timestamp()}_{uuid4().hex[:8]}"
        clean_metadata = {
            "profile_id": profile_id,
            "created_at": datetime.now(UTC).isoformat(),
            **self._clean_metadata(metadata or {}),
        }
        try:
            self.collection.add(
                ids=[memory_id],
                documents=[text],
                metadatas=[clean_metadata],
            )
            return memory_id
        except Exception:
            return None

    def recall(
        self,
        profile_id: str,
        query: str,
        limit: int = 5,
        memory_type: str | None = None,
    ) -> list[str]:
        if not self.collection:
            return []

        where: dict[str, Any] = {"profile_id": profile_id}
        if memory_type:
            where = {"$and": [where, {"type": memory_type}]}
        try:
            result = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
            )
            return result.get("documents", [[]])[0]
        except Exception:
            return []

    def history(self, profile_id: str, limit: int = 50) -> list[str]:
        if not self.collection:
            return []
        try:
            result = self.collection.get(
                where={"profile_id": profile_id},
                limit=limit,
                include=["documents"],
            )
            return result.get("documents", [])
        except Exception:
            return []

    @staticmethod
    def _clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
        allowed = (str, int, float, bool)
        return {
            key: value if isinstance(value, allowed) else str(value)
            for key, value in metadata.items()
            if value is not None
        }
