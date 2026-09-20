"""Embedding Provider abstraction and hosted/local switch."""

from abc import ABC, abstractmethod
from typing import List, Optional
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding models."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding vector dimension."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings."""
        pass


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI hosted embedding provider (voyage-3 default: 1024 dims)."""

    def __init__(self, api_key: str, model: str = "voyage-3") -> None:
        self.api_key = api_key
        self.model = model
        self._dim = 1024

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> List[float]:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": [text], "model": self.model},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.model},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider (bge-base-en-v1.5: 768 dims)."""

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5") -> None:
        self.model_name = model_name
        self._dim = 768

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> List[float]:
        # Local model inference placeholder for Phase 2 integration
        return [0.0] * self._dim

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * self._dim for _ in texts]


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock embedding provider for tests and development."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_text(self, text: str) -> List[float]:
        # Deterministic dummy vector based on string hash
        h = abs(hash(text)) % 1000
        return [float((h + i) % 100) / 100.0 for i in range(self._dim)]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_text(t) for t in texts]


def get_embedding_provider() -> EmbeddingProvider:
    """Factory to retrieve configured embedding provider."""
    mode = settings.EMBEDDING_MODE.lower()
    api_key = settings.VOYAGE_API_KEY

    if mode == "hosted" and api_key and not api_key.startswith("your_voyage_api"):
        logger.info("Using VoyageEmbeddingProvider")
        return VoyageEmbeddingProvider(api_key=api_key)
    elif mode == "local":
        logger.info("Using LocalEmbeddingProvider")
        return LocalEmbeddingProvider()

    logger.info("Using MockEmbeddingProvider")
    return MockEmbeddingProvider()
