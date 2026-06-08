from uuid import uuid4

from backend.app.config import settings


class HealthMemory:
    def __init__(self) -> None:
        self.collection = None
        try:
            import chromadb

            client = chromadb.PersistentClient(path=settings.chroma_path)
            self.collection = client.get_or_create_collection("health_memory")
        except Exception:
            # The API remains usable before local memory dependencies are installed.
            self.collection = None

    def remember(self, profile_id: str, text: str, metadata: dict[str, str]) -> None:
        if self.collection:
            try:
                self.collection.add(
                    ids=[str(uuid4())],
                    documents=[text],
                    metadatas=[{"profile_id": profile_id, **metadata}],
                )
            except Exception:
                self.collection = None

    def recall(self, profile_id: str, query: str, limit: int = 4) -> list[str]:
        if not self.collection:
            return []
        try:
            result = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where={"profile_id": profile_id},
            )
            return result.get("documents", [[]])[0]
        except Exception:
            self.collection = None
            return []
