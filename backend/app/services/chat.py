import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union
import structlog
from sqlalchemy import func, update
from sqlmodel import Session as SQLModelSession, col, select

from app.db.session import engine, run_db
from app.models.memory import MemoryProcedural
from app.db.qdrant import (
    update_memory_payload,
    get_qdrant_client,
    search_memory_vectors,
    DEFAULT_COLLECTION_NAME,
)
from app.providers.embedding_provider import get_embedding_provider

logger = structlog.get_logger(__name__)


def _fetch_active_rules() -> List[MemoryProcedural]:
    """Fetch active procedural rules in a dedicated sync session (safe for thread offload)."""
    with SQLModelSession(engine) as session:
        stmt = select(MemoryProcedural).where(MemoryProcedural.is_active == True)  # noqa: E712
        return list(session.exec(stmt).all())


def _execute_reinforcement(
    session: SQLModelSession,
    unique_ids: List[uuid.UUID],
    boost_amount: float,
    now: datetime,
) -> List[MemoryProcedural]:
    """Execute atomic reinforcement updates within a session, committing immediately."""
    if not unique_ids:
        return []

    update_stmt = (
        update(MemoryProcedural)
        .where(col(MemoryProcedural.id).in_(unique_ids))
        .where(MemoryProcedural.is_active == True)  # noqa: E712
        .values(
            access_count=func.coalesce(MemoryProcedural.access_count, 0) + 1,
            confidence=func.least(1.0, MemoryProcedural.confidence + boost_amount),
            last_accessed_at=now,
            updated_at=now,
        )
    )
    session.exec(update_stmt)
    session.commit()

    fetch_stmt = (
        select(MemoryProcedural)
        .where(col(MemoryProcedural.id).in_(unique_ids))
        .where(MemoryProcedural.is_active == True)  # noqa: E712
    )
    rules = list(session.exec(fetch_stmt).all())
    return rules


def reinforce_rule_access(
    db: Optional[SQLModelSession] = None,
    rule_ids: Optional[List[Union[uuid.UUID, str]]] = None,
    boost_amount: float = 0.05,
) -> List[MemoryProcedural]:
    """Isolate and execute reinforcement on procedural rules, committing immediately and syncing to Qdrant."""
    if not rule_ids:
        return []

    # Safe UUID parsing and deduplication
    parsed_ids: Set[uuid.UUID] = set()
    for rid in rule_ids:
        if isinstance(rid, uuid.UUID):
            parsed_ids.add(rid)
        elif isinstance(rid, str):
            try:
                parsed_ids.add(uuid.UUID(rid.strip()))
            except (ValueError, TypeError, AttributeError):
                pass

    if not parsed_ids:
        return []

    unique_ids = list(parsed_ids)
    now = datetime.now(timezone.utc)
    refreshed_rules: List[MemoryProcedural] = []

    # Perform update in dedicated/provided session with rollback guard
    if db is not None:
        try:
            refreshed_rules = _execute_reinforcement(db, unique_ids, boost_amount, now)
        except Exception as exc:
            db.rollback()
            logger.error("Error executing reinforcement on session; rolled back", error=str(exc))
            return []
    else:
        try:
            with SQLModelSession(engine) as session:
                refreshed_rules = _execute_reinforcement(session, unique_ids, boost_amount, now)
        except Exception as exc:
            logger.error("Error executing isolated reinforcement", error=str(exc))
            return []

    if not refreshed_rules:
        return []

    # Synchronize updated confidence and access metadata to Qdrant point payloads
    try:
        client = get_qdrant_client()
        for rule in refreshed_rules:
            conf_val = round(float(rule.confidence), 4)
            accessed_str = (
                rule.last_accessed_at.isoformat()
                if rule.last_accessed_at
                else now.isoformat()
            )
            payload_data = {
                "confidence": conf_val,
                "access_count": rule.access_count,
                "last_accessed_at": accessed_str,
            }
            try:
                client.set_payload(
                    collection_name=DEFAULT_COLLECTION_NAME,
                    payload=payload_data,
                    points=[str(rule.id)],
                )
            except Exception:
                update_memory_payload(str(rule.id), payload_data)
    except Exception as exc:
        logger.warning("Failed to sync Qdrant payloads on reinforcement", error=str(exc))

    logger.info(
        "Reinforced procedural rules upon retrieval",
        reinforced_count=len(refreshed_rules),
        rule_ids=[str(r.id) for r in refreshed_rules],
    )

    return refreshed_rules


async def retrieve_memory_context(
    query_text: str,
    db: Optional[SQLModelSession] = None,
    limit: int = 5,
    timeout_seconds: float = 3.0,
) -> Dict[str, Any]:
    """Resiliently retrieve active procedural rules and semantic vector memories.

    If vector search fails, times out, or encounters any network/database exception,
    the pipeline degrades gracefully by returning active DB rules without failing the turn.
    """
    active_rules: List[MemoryProcedural] = []

    # 1. Fetch active procedural rules from relational database
    try:
        if db is not None:
            stmt = select(MemoryProcedural).where(MemoryProcedural.is_active == True)  # noqa: E712
            active_rules = list(db.exec(stmt).all())
        else:
            # Offload blocking SQLModel I/O to a thread pool so the event loop
            # is not stalled while waiting for the DB round-trip.
            active_rules = await run_db(_fetch_active_rules)
    except Exception as db_exc:
        logger.error("Failed to query active procedural rules from DB; continuing gracefully", error=str(db_exc))
        active_rules = []

    # 2. Resilient Vector Retrieval with timeout and exception containment
    retrieved_memories: List[Dict[str, Any]] = []
    try:
        embedding_provider = get_embedding_provider()
        query_vector = await asyncio.wait_for(
            embedding_provider.embed_text(query_text),
            timeout=timeout_seconds,
        )

        # Offload the blocking Qdrant gRPC/HTTP call to a thread pool so the
        # async event loop is not stalled during network I/O.
        retrieved_memories = await run_db(
            search_memory_vectors,
            query_vector=query_vector,
            limit=limit,
            collection_name=DEFAULT_COLLECTION_NAME,
            active_only=True,
        )
        logger.info(
            "Retrieved memory context for turn",
            active_rules_count=len(active_rules),
            vector_hits=len(retrieved_memories),
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Vector memory retrieval timed out; degrading gracefully to active DB rules",
            timeout=timeout_seconds,
        )
        retrieved_memories = []
    except Exception as vec_exc:
        logger.warning(
            "Vector memory retrieval failed; degrading gracefully to active DB rules",
            error=str(vec_exc),
        )
        retrieved_memories = []

    # 3. Reinforce retrieved and injected procedural rules safely in isolated session
    target_rule_ids: List[uuid.UUID] = [r.id for r in active_rules]
    for mem in retrieved_memories:
        try:
            target_rule_ids.append(uuid.UUID(str(mem.get("id"))))
        except (ValueError, TypeError):
            pass

    if target_rule_ids:
        try:
            # reinforce_rule_access uses an isolated session with rollback protection
            # Offload the blocking DB write + Qdrant payload sync to a thread
            # pool.  reinforce_rule_access opens its own isolated session so
            # it is safe to run outside the calling async context.
            reinforced = await run_db(reinforce_rule_access, rule_ids=target_rule_ids)
            if reinforced:
                active_rules = reinforced
        except Exception as reinf_exc:
            logger.warning("Failed to reinforce procedural rules gracefully", error=str(reinf_exc))

    return {
        "active_rules": active_rules,
        "retrieved_memories": retrieved_memories,
    }

