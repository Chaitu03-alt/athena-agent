"""Qdrant vector database client and collection management."""

from typing import Any, Dict, List, Optional
import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.providers.embedding_provider import get_embedding_provider

logger = structlog.get_logger(__name__)

# Default collection name for consolidated agent memories
DEFAULT_COLLECTION_NAME = "agent_memories"

_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """Provide singleton QdrantClient instance connected to configured QDRANT_URL."""
    global _client
    if _client is None:
        logger.info("Initializing Qdrant client", url=settings.QDRANT_URL)
        _client = QdrantClient(url=settings.QDRANT_URL, check_compatibility=False)
    return _client


def ensure_qdrant_collections(
    collection_name: str = DEFAULT_COLLECTION_NAME,
    vector_size: Optional[int] = None,
) -> bool:
    """Ensure the target memory collection exists in Qdrant with appropriate vector dimension."""
    client = get_qdrant_client()
    embedding_provider = get_embedding_provider()
    dimension = vector_size or embedding_provider.dimension

    try:
        collections = client.get_collections().collections
        existing_names = [col.name for col in collections]

        if collection_name not in existing_names:
            logger.info(
                "Creating Qdrant collection",
                collection=collection_name,
                dimension=dimension,
            )
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(
                    size=dimension,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info("Successfully created Qdrant collection", collection=collection_name)
        else:
            logger.debug("Qdrant collection already exists", collection=collection_name)

        # Ensure payload indexes for high-speed filtered queries
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="is_active",
                field_schema=qmodels.PayloadSchemaType.BOOL,
            )
        except Exception:
            pass

        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="category",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass

        return True
    except Exception as exc:
        logger.error("Failed to initialize Qdrant collection", error=str(exc))
        return False


def upsert_memory_vector(
    point_id: str,
    vector: List[float],
    payload: Dict[str, Any],
    collection_name: str = DEFAULT_COLLECTION_NAME,
    max_retries: int = 3,
) -> bool:
    """Upsert a vector embedding and payload into Qdrant collection with retry mechanism."""
    client = get_qdrant_client()
    payload.setdefault("is_active", True)
    payload.setdefault("version", 1)
    point = qmodels.PointStruct(
        id=point_id,
        vector=vector,
        payload=payload,
    )
    for attempt in range(max_retries):
        try:
            client.upsert(
                collection_name=collection_name,
                points=[point],
            )
            logger.info("Upserted point to Qdrant", point_id=point_id, collection=collection_name)
            return True
        except Exception as exc:
            logger.warning(
                "Failed attempt to upsert vector to Qdrant",
                point_id=point_id,
                attempt=attempt + 1,
                error=str(exc),
            )
            if attempt == max_retries - 1:
                logger.error("All retries exhausted for Qdrant upsert", point_id=point_id, error=str(exc))
                raise


def update_memory_payload(
    point_id: str,
    payload_update: Dict[str, Any],
    collection_name: str = DEFAULT_COLLECTION_NAME,
    max_retries: int = 3,
) -> bool:
    """Update metadata payload for an existing point in Qdrant with retry mechanism."""
    client = get_qdrant_client()
    for attempt in range(max_retries):
        try:
            client.set_payload(
                collection_name=collection_name,
                payload=payload_update,
                points=[str(point_id)],
            )
            logger.info("Updated Qdrant payload", point_id=str(point_id), payload_update=payload_update)
            return True
        except Exception as exc:
            logger.warning(
                "Failed attempt to update Qdrant payload",
                point_id=str(point_id),
                attempt=attempt + 1,
                error=str(exc),
            )
            if attempt == max_retries - 1:
                logger.error("All retries exhausted for Qdrant payload update", point_id=str(point_id), error=str(exc))
                return False
    return False


def search_memory_vectors(
    query_vector: List[float],
    limit: int = 5,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    score_threshold: Optional[float] = None,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    """Query Qdrant collection by cosine vector similarity with strict active_only filter."""
    client = get_qdrant_client()
    query_filter = None
    if active_only:
        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="is_active",
                    match=qmodels.MatchValue(value=True),
                )
            ]
        )

    try:
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )
            points = response.points
        else:
            points = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )
        results = []
        for hit in points:
            payload = hit.payload or {}
            # Strict safety check: if active_only requested, ignore any points where is_active is not True
            if active_only and payload.get("is_active") is not True:
                continue
            results.append({
                "id": str(hit.id),
                "score": float(hit.score),
                "payload": payload,
            })
        return results
    except Exception as exc:
        logger.error("Failed to search Qdrant", error=str(exc))
        return []


def get_qdrant_health() -> Dict[str, Any]:
    """Retrieve Qdrant connection and collection status."""
    try:
        client = get_qdrant_client()
        collections_resp = client.get_collections()
        col_names = [col.name for col in collections_resp.collections]
        return {
            "status": "connected",
            "url": settings.QDRANT_URL,
            "collections": col_names,
        }
    except Exception as exc:
        return {
            "status": "unreachable",
            "url": settings.QDRANT_URL,
            "error": str(exc),
        }
