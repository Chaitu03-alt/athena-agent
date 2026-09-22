import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session as SQLModelSession, select, col

from app.db.session import get_session
from app.db.qdrant import get_qdrant_client, get_qdrant_health, update_memory_payload, DEFAULT_COLLECTION_NAME
from app.models.memory import MemoryEpisodic, MemoryProcedural, MemorySemantic
from app.services.reflection import ReflectionService
from app.memory.kv_store import KeyValueStore
from app.memory.soul import SoulPromptManager

router = APIRouter()
reflection_service = ReflectionService()


class ConsolidateRequest(BaseModel):
    importance_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum importance score required for episodic memory consolidation.",
    )


class ConsolidateResponse(BaseModel):
    status: str
    message: str
    processed_episodic_count: int
    procedural_created_count: int
    semantic_created_count: int
    memories: List[Dict[str, Any]]


@router.post(
    "/consolidate",
    response_model=ConsolidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger memory consolidation and reflection",
)
async def trigger_consolidation(
    payload: Optional[ConsolidateRequest] = None,
    threshold: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: SQLModelSession = Depends(get_session),
) -> ConsolidateResponse:
    """Consolidate unconsolidated high-importance episodic memories into procedural/semantic tables and Qdrant."""
    effective_threshold = (
        threshold
        if threshold is not None
        else (payload.importance_threshold if payload else 0.5)
    )
    result = await reflection_service.consolidate(
        db=db,
        importance_threshold=effective_threshold,
    )
    return ConsolidateResponse(**result)


class DecayRequest(BaseModel):
    inactivity_hours: float = Field(default=24.0, ge=0.0, description="Hours of inactivity before decaying rule confidence.")
    decay_rate: float = Field(default=0.05, ge=0.0, le=1.0, description="Confidence reduction amount per decay pass.")
    minimum_active_confidence: float = Field(default=0.40, ge=0.0, le=1.0, description="Confidence threshold below which rule is archived.")


@router.post(
    "/decay",
    summary="Trigger procedural memory decay pass",
    status_code=status.HTTP_200_OK,
)
def trigger_memory_decay(
    payload: Optional[DecayRequest] = None,
    inactivity_hours: Optional[float] = Query(None, ge=0.0),
    db: SQLModelSession = Depends(get_session),
) -> Dict[str, Any]:
    """Execute confidence decay on inactive procedural rules and archive those below 0.40 confidence."""
    hours = inactivity_hours if inactivity_hours is not None else (payload.inactivity_hours if payload else 24.0)
    rate = payload.decay_rate if payload else 0.05
    min_conf = payload.minimum_active_confidence if payload else 0.40

    return reflection_service.decay_inactive_rules(
        db=db,
        inactivity_hours=hours,
        decay_rate=rate,
        minimum_active_confidence=min_conf,
    )


class RuleUpdateRequest(BaseModel):
    is_active: bool = Field(description="Desired activation state for the procedural rule.")


@router.get("/rules", summary="List learned procedural rules")
def list_rules(
    active_only: bool = Query(True, description="Filter for active rules only or include archived/inactive"),
    category: Optional[str] = None,
    db: SQLModelSession = Depends(get_session),
) -> List[MemoryProcedural]:
    """Retrieve procedural rules learned from user interactions (Phase 3 & Phase 4)."""
    stmt = select(MemoryProcedural)
    if active_only:
        stmt = stmt.where(MemoryProcedural.is_active == True)  # noqa: E712
    if category:
        stmt = stmt.where(MemoryProcedural.category == category)
    stmt = stmt.order_by(col(MemoryProcedural.version).desc(), col(MemoryProcedural.updated_at).desc())
    return list(db.exec(stmt).all())


@router.patch("/rules/{rule_id}", summary="Update rule status (activate / deactivate)")
def update_rule_status(
    rule_id: uuid.UUID,
    payload: RuleUpdateRequest,
    db: SQLModelSession = Depends(get_session),
) -> Dict[str, Any]:
    """Toggle a procedural rule's is_active state and synchronize Qdrant payload."""
    rule = db.get(MemoryProcedural, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")

    rule.is_active = payload.is_active
    rule.active = payload.is_active
    rule.updated_at = datetime.now(timezone.utc)
    db.add(rule)
    db.commit()
    db.refresh(rule)

    # Immediately update corresponding point's payload in Qdrant
    try:
        client = get_qdrant_client()
        client.set_payload(
            collection_name=DEFAULT_COLLECTION_NAME,
            payload={"is_active": rule.is_active},
            points=[str(rule.id)],
        )
    except Exception:
        update_memory_payload(str(rule.id), {"is_active": rule.is_active})

    return {
        "status": "success",
        "message": f"Rule {rule_id} is_active updated to {rule.is_active}.",
        "rule_id": str(rule.id),
        "rule_statement": rule.rule_statement,
        "category": rule.category,
        "confidence": rule.confidence,
        "source": rule.source,
        "is_active": rule.is_active,
        "version": rule.version,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.delete("/rules/{rule_id}", summary="Deactivate / archive a learned rule")
def deactivate_rule(
    rule_id: uuid.UUID,
    db: SQLModelSession = Depends(get_session),
) -> Dict[str, Any]:
    """Soft-delete/deactivate a procedural rule in Postgres and update Qdrant payload."""
    rule = db.get(MemoryProcedural, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule {rule_id} not found")

    rule.is_active = False
    rule.active = False
    rule.updated_at = datetime.now(timezone.utc)
    db.add(rule)
    db.commit()
    db.refresh(rule)

    # Immediately update the corresponding point's payload in Qdrant
    try:
        client = get_qdrant_client()
        client.set_payload(
            collection_name=DEFAULT_COLLECTION_NAME,
            payload={"is_active": False},
            points=[str(rule.id)],
        )
    except Exception:
        # Fallback helper call
        update_memory_payload(str(rule.id), {"is_active": False})

    return {
        "status": "success",
        "message": f"Rule {rule_id} has been deactivated.",
        "rule_id": str(rule.id),
        "rule_statement": rule.rule_statement,
        "is_active": rule.is_active,
        "version": rule.version,
    }


@router.post("/sync-qdrant", summary="Synchronize Postgres rule statuses to Qdrant vector store")
async def sync_qdrant_status(
    db: SQLModelSession = Depends(get_session),
) -> Dict[str, Any]:
    """Ensure all deactivated Postgres procedural rules have is_active: false inside Qdrant."""
    return await reflection_service.sync_all_rules_to_qdrant(db)


@router.get("/procedural", summary="List consolidated procedural rules")
def list_procedural_memories(
    active_only: bool = Query(True),
    category: Optional[str] = None,
    db: SQLModelSession = Depends(get_session),
) -> List[MemoryProcedural]:
    """Retrieve procedural rules learned from user interactions."""
    stmt = select(MemoryProcedural)
    if active_only:
        stmt = stmt.where(MemoryProcedural.is_active == True)  # noqa: E712
    if category:
        stmt = stmt.where(MemoryProcedural.category == category)
    stmt = stmt.order_by(col(MemoryProcedural.version).desc(), col(MemoryProcedural.created_at).desc())
    return list(db.exec(stmt).all())


@router.get("/semantic", summary="List consolidated semantic facts")
def list_semantic_memories(
    active_only: bool = Query(True),
    category: Optional[str] = None,
    db: SQLModelSession = Depends(get_session),
) -> List[MemorySemantic]:
    """Retrieve semantic facts extracted from conversation history."""
    stmt = select(MemorySemantic)
    if active_only:
        stmt = stmt.where(MemorySemantic.is_active == True)  # noqa: E712
    if category:
        stmt = stmt.where(MemorySemantic.category == category)
    stmt = stmt.order_by(col(MemorySemantic.version).desc(), col(MemorySemantic.created_at).desc())
    return list(db.exec(stmt).all())


@router.get("/episodic", summary="List raw episodic interaction logs")
def list_episodic_memories(
    consolidated: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    db: SQLModelSession = Depends(get_session),
) -> List[MemoryEpisodic]:
    """Retrieve raw episodic conversation turns."""
    stmt = select(MemoryEpisodic)
    if consolidated is not None:
        stmt = stmt.where(MemoryEpisodic.consolidated == consolidated)
    stmt = stmt.order_by(col(MemoryEpisodic.created_at).desc()).limit(limit)
    return list(db.exec(stmt).all())


@router.get("/status", summary="Vector DB and memory subsystem health")
def memory_status() -> Dict[str, Any]:
    """Check status of Qdrant vector store and memory collections."""
    health = get_qdrant_health()
    return {
        "vector_db": health,
        "default_collection": DEFAULT_COLLECTION_NAME,
    }

class KVSetRequest(BaseModel):
    value: Dict[str, Any]

@router.get("/kv", summary="Get all Key-Value profile memories")
async def get_all_kv() -> Dict[str, Any]:
    """Inspect all KV store memory keys."""
    # Retrieve all keys - assuming we can fetch them via a raw query since KVStore might only have get/set.
    # Alternatively just use execute_read_async from db/connection.
    from app.db.connection import execute_read_async
    import json
    rows = await execute_read_async("SELECT key, value FROM user_kv")
    result = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except Exception:
            result[row["key"]] = row["value"]
    return result

@router.post("/kv/{key}", summary="Update a Key-Value profile memory")
async def set_kv(key: str, payload: KVSetRequest) -> Dict[str, str]:
    await KeyValueStore.set(key, payload.value)
    return {"status": "success", "key": key}

class SoulPromptUpdateRequest(BaseModel):
    prompt_text: str

@router.get("/soul", summary="Get current active soul prompt")
async def get_soul() -> Dict[str, Any]:
    soul = await SoulPromptManager.get_active_soul()
    return {"status": "success", "prompt": soul}

@router.post("/soul", summary="Update active soul prompt")
async def update_soul(payload: SoulPromptUpdateRequest) -> Dict[str, str]:
    await SoulPromptManager.set_soul_prompt(payload.prompt_text)
    return {"status": "success", "message": "Soul prompt updated and versioned."}
