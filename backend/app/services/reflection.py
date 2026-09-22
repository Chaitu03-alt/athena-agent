"""Memory reflection and consolidation service."""

import asyncio
import difflib
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import structlog
from sqlmodel import Session as SQLModelSession, select, col

from app.config import settings
from app.db.qdrant import (
    ensure_qdrant_collections,
    get_qdrant_client,
    upsert_memory_vector,
    update_memory_payload,
    search_memory_vectors,
    DEFAULT_COLLECTION_NAME,
)
from app.models.memory import MemoryEpisodic, MemoryProcedural, MemorySemantic
from app.providers.embedding_provider import get_embedding_provider
from app.providers.llm_provider import get_llm_provider

logger = structlog.get_logger(__name__)

CONSOLIDATION_SYSTEM_PROMPT = """You are the Memory Reflection & Consolidation Engine of an adaptive AI agent.
Analyze the provided high-importance episodic conversation turns in the context of existing active rules and extract durable, actionable knowledge:
1. Procedural Rules: User coding conventions, tool preferences (arguments, CLI flags, default configurations), communication styles, rules, or workflows.
2. Semantic Facts: Specific facts about the user's projects, architecture, environments, or domain facts.

Important Instructions:
- Tool Calling & Preferences: Pay special attention to tool invocations, shell commands, and developer CLI workflows. If the user specifies or repeatedly uses particular arguments, flags (e.g. -v, --strict), output formats (JSON vs YAML), or command tools (pytest, ripgrep, git), extract these as procedural rules with category "tool_preference".
- Avoid duplicate rules: If a candidate rule expresses essentially the same preference or fact as an existing active rule, mark it with "duplicate_of_id": "<id of existing rule>".
- Detect contradictions/supersessions: If a candidate rule directly conflicts with, updates, or overrides an existing active rule in the same domain (for example, switching from functional programming to object-oriented class-based style, or dynamic typing to strict typing), mark it with "supersedes_id": "<id of existing rule>" or "supersedes_statement": "<statement of existing rule>".

Return ONLY a valid JSON array of objects with the following schema:
[
  {
    "type": "procedural" | "semantic",
    "statement": "Clear, standalone rule or fact statement",
    "category": "coding_style" | "communication_style" | "workflow" | "tooling" | "tool_preference" | "other" | "project_fact" | "personal_fact",
    "confidence": 0.85,
    "supersedes_id": "<uuid of superseded existing rule if conflicting, else null>",
    "supersedes_statement": "<statement of superseded rule if conflicting, else null>",
    "duplicate_of_id": "<uuid of existing rule if duplicate, else null>",
    "source_episodic_ids": ["<uuid of source turn>"]
  }
]
Do not include any conversational preamble or explanation, only raw valid JSON.
"""

# 64-bit integer advisory lock key for cross-process PostgreSQL worker coordination
POSTGRES_CONSOLIDATION_LOCK_ID = 982347102


class ReflectionService:
    """Consolidates high-importance episodic interactions into procedural and semantic memory."""

    def __init__(self) -> None:
        self.embedding_provider = get_embedding_provider()
        self.llm_provider = get_llm_provider(model=settings.LLM_MODEL_LIGHT)
        self._consolidation_lock = asyncio.Lock()

    def _compute_text_similarity(self, a: str, b: str) -> float:
        """Compute string & token overlap similarity between two statements."""
        clean_a = re.sub(r"[^\w\s]", "", a.lower()).strip()
        clean_b = re.sub(r"[^\w\s]", "", b.lower()).strip()
        if not clean_a or not clean_b:
            return 0.0
        if clean_a == clean_b:
            return 1.0

        ratio = difflib.SequenceMatcher(None, clean_a, clean_b).ratio()
        words_a = set(clean_a.split())
        words_b = set(clean_b.split())
        if words_a and words_b:
            jaccard = len(words_a & words_b) / len(words_a | words_b)
            return max(ratio, jaccard)
        return ratio

    def deduplicate_and_clean_active_rules(self, db: SQLModelSession) -> int:
        """Scan active rules in PostgreSQL, deactivate duplicates, and ensure Qdrant active state."""
        active_proc = list(
            db.exec(
                select(MemoryProcedural)
                .where(MemoryProcedural.is_active == True)  # noqa: E712
                .order_by(col(MemoryProcedural.updated_at).desc(), col(MemoryProcedural.created_at).desc())
            ).all()
        )
        seen_statements: Dict[str, MemoryProcedural] = {}
        cleaned_count = 0
        now_utc = datetime.now(timezone.utc)

        # Phase 1: Deduplicate near-identical statements
        for rule in active_proc:
            norm = re.sub(r"[^\w\s]", "", rule.rule_statement.lower()).strip()
            matched_dup: Optional[MemoryProcedural] = None
            if norm in seen_statements:
                matched_dup = seen_statements[norm]
            else:
                for seen_norm, seen_rule in seen_statements.items():
                    if self._compute_text_similarity(norm, seen_norm) > 0.88:
                        matched_dup = seen_rule
                        break

            if matched_dup:
                # Deactivate older duplicate
                logger.info(
                    "Deactivating duplicate active rule in database",
                    duplicate_id=str(rule.id),
                    canonical_id=str(matched_dup.id),
                    statement=rule.rule_statement,
                )
                rule.is_active = False
                rule.active = False
                rule.updated_at = now_utc
                db.add(rule)
                update_memory_payload(str(rule.id), {"is_active": False})
                cleaned_count += 1
            else:
                seen_statements[norm] = rule

        # Phase 2: Check for contradictions/conflicts among active rules (newer supersedes older)
        surviving_rules: List[MemoryProcedural] = []
        for rule in list(seen_statements.values()):
            is_conflicted = False
            for survivor in surviving_rules:
                if self._is_conflict(survivor.rule_statement, rule.rule_statement):
                    # Survivor is newer; soft-deprecate this older rule
                    logger.info(
                        "Found conflicting active rule during cleanup; deactivating older rule",
                        older_id=str(rule.id),
                        older_statement=rule.rule_statement,
                        survivor_id=str(survivor.id),
                        survivor_statement=survivor.rule_statement,
                    )
                    rule.is_active = False
                    rule.active = False
                    rule.superseded_by = survivor.id
                    rule.updated_at = now_utc
                    db.add(rule)
                    update_memory_payload(str(rule.id), {"is_active": False})
                    cleaned_count += 1
                    is_conflicted = True
                    break
            if not is_conflicted:
                surviving_rules.append(rule)
                update_memory_payload(str(rule.id), {"is_active": True})

        if cleaned_count > 0:
            db.commit()
            logger.info("Cleaned up duplicate and conflicting active rules", cleaned_count=cleaned_count)
        return cleaned_count

    async def sync_all_rules_to_qdrant(self, db: SQLModelSession) -> Dict[str, Any]:
        """Synchronize all Postgres procedural and semantic rule states to Qdrant."""
        ensure_qdrant_collections()
        client = get_qdrant_client()
        proc_rules = list(db.exec(select(MemoryProcedural)).all())
        sem_facts = list(db.exec(select(MemorySemantic)).all())

        synced_active = 0
        synced_inactive = 0
        upserted_missing = 0

        # Sync procedural rules
        for rule in proc_rules:
            point_id = str(rule.id)
            is_act = rule.is_active
            try:
                client.set_payload(
                    collection_name=DEFAULT_COLLECTION_NAME,
                    payload={"is_active": is_act, "rule_statement": rule.rule_statement, "version": rule.version},
                    points=[point_id],
                )
                if is_act:
                    synced_active += 1
                else:
                    synced_inactive += 1
            except Exception:
                if is_act:
                    try:
                        vec = await self.embedding_provider.embed_text(rule.rule_statement)
                        upsert_memory_vector(
                            point_id=point_id,
                            vector=vec,
                            payload={
                                "memory_id": point_id,
                                "memory_type": "procedural",
                                "rule_statement": rule.rule_statement,
                                "category": rule.category,
                                "confidence": rule.confidence,
                                "version": rule.version,
                                "is_active": True,
                                "created_at": rule.created_at.isoformat(),
                            },
                        )
                        upserted_missing += 1
                    except Exception as up_err:
                        logger.error("Failed to upsert missing rule into Qdrant", id=point_id, error=str(up_err))

        # Sync semantic facts
        for fact in sem_facts:
            point_id = str(fact.id)
            is_act = fact.is_active
            try:
                client.set_payload(
                    collection_name=DEFAULT_COLLECTION_NAME,
                    payload={"is_active": is_act, "statement": fact.statement, "version": fact.version},
                    points=[point_id],
                )
                if is_act:
                    synced_active += 1
                else:
                    synced_inactive += 1
            except Exception:
                pass

        # Also scroll Qdrant points and set is_active=False on any points matching inactive rules
        try:
            points, _ = client.scroll(DEFAULT_COLLECTION_NAME, limit=200, with_payload=True)
            inactive_statements = [
                r.rule_statement.lower().strip() for r in proc_rules if not r.is_active
            ]
            for p in points:
                payload = p.payload or {}
                p_text = (payload.get("rule_statement") or payload.get("statement") or payload.get("content") or "").lower().strip()
                for inact in inactive_statements:
                    if inact and (inact in p_text or p_text in inact):
                        client.set_payload(DEFAULT_COLLECTION_NAME, {"is_active": False}, points=[p.id])
                        break
        except Exception as scroll_err:
            logger.warning("Could not scroll Qdrant points during sync", error=str(scroll_err))

        logger.info(
            "Qdrant synchronization complete",
            synced_active=synced_active,
            synced_inactive=synced_inactive,
            upserted_missing=upserted_missing,
        )
        return {
            "status": "success",
            "synced_active": synced_active,
            "synced_inactive": synced_inactive,
            "upserted_missing": upserted_missing,
        }

    async def consolidate(
        self,
        db: SQLModelSession,
        importance_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Execute consolidation pass with PostgreSQL advisory lock and asyncio concurrency locking."""
        if self._consolidation_lock.locked():
            logger.warning("Consolidation already in progress in this process; skipping concurrent invocation")
            return {
                "status": "in_progress",
                "message": "A consolidation cycle is already running.",
                "processed_episodic_count": 0,
                "semantic_created_count": 0,
                "procedural_created_count": 0,
                "memories": [],
            }

        async with self._consolidation_lock:
            # Check if connected to PostgreSQL for cross-process worker coordination
            is_postgres = False
            try:
                bind = db.get_bind()
                if bind and hasattr(bind, "dialect") and bind.dialect.name == "postgresql":
                    is_postgres = True
            except Exception:
                is_postgres = False

            if is_postgres:
                from sqlalchemy import text
                lock_stmt = text("SELECT pg_try_advisory_lock(:lock_id)")
                conn = db.connection()
                lock_acquired = conn.execute(lock_stmt, {"lock_id": POSTGRES_CONSOLIDATION_LOCK_ID}).scalar()
                if not lock_acquired:
                    logger.warning(
                        "Another worker process holds PostgreSQL consolidation advisory lock; skipping concurrent cycle",
                        lock_id=POSTGRES_CONSOLIDATION_LOCK_ID,
                    )
                    return {
                        "status": "in_progress",
                        "message": "Consolidation cycle is running in another worker process.",
                        "processed_episodic_count": 0,
                        "semantic_created_count": 0,
                        "procedural_created_count": 0,
                        "memories": [],
                    }
                try:
                    return await self._execute_consolidation(db=db, importance_threshold=importance_threshold)
                finally:
                    try:
                        unlock_stmt = text("SELECT pg_advisory_unlock(:lock_id)")
                        conn.execute(unlock_stmt, {"lock_id": POSTGRES_CONSOLIDATION_LOCK_ID})
                    except Exception as unlock_err:
                        logger.warning("Failed to release PostgreSQL advisory lock", error=str(unlock_err))
            else:
                return await self._execute_consolidation(db=db, importance_threshold=importance_threshold)

    async def _execute_consolidation(
        self,
        db: SQLModelSession,
        importance_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """Execute consolidation pass over unconsolidated episodic memories meeting importance threshold."""
        # Ensure Qdrant collection is ready
        ensure_qdrant_collections()

        # Deduplicate existing active rules first to keep memory clean
        self.deduplicate_and_clean_active_rules(db)

        # 1. Fetch unconsolidated candidates
        statement = (
            select(MemoryEpisodic)
            .where(MemoryEpisodic.consolidated == False)  # noqa: E712
            .where(MemoryEpisodic.importance_score >= importance_threshold)
            .order_by(col(MemoryEpisodic.created_at).asc())
        )
        candidates: List[MemoryEpisodic] = list(db.exec(statement).all())

        if not candidates:
            logger.info("No unconsolidated episodic entries met threshold", threshold=importance_threshold)
            return {
                "status": "success",
                "message": "No unconsolidated episodic entries meeting threshold found.",
                "processed_episodic_count": 0,
                "semantic_created_count": 0,
                "procedural_created_count": 0,
                "memories": [],
            }

        logger.info(
            "Found candidate episodic memories for consolidation",
            count=len(candidates),
            threshold=importance_threshold,
        )

        # 2. Fetch existing active rules to ground LLM extraction context
        active_proc_rules: List[MemoryProcedural] = list(
            db.exec(select(MemoryProcedural).where(MemoryProcedural.is_active == True)).all()  # noqa: E712
        )
        active_sem_facts: List[MemorySemantic] = list(
            db.exec(select(MemorySemantic).where(MemorySemantic.is_active == True)).all()  # noqa: E712
        )

        active_context_lines = [
            f"- [ID: {r.id}] [Procedural/{r.category}]: {r.rule_statement}"
            for r in active_proc_rules
        ] + [
            f"- [ID: {s.id}] [Semantic/{s.category}]: {s.statement}"
            for s in active_sem_facts
        ]
        active_rules_text = "\n".join(active_context_lines) if active_context_lines else "None"

        # Format candidates for prompt
        formatted_turns = []
        for cand in candidates:
            formatted_turns.append(
                f"[ID: {cand.id}] [Score: {cand.importance_score}] [Tags: {', '.join(cand.tags)}]\n{cand.content}"
            )
        turns_text = "\n\n---\n\n".join(formatted_turns)

        # 3. Request LLM extraction with existing context
        messages = [
            {
                "role": "user",
                "content": (
                    f"Current Active Rules:\n{active_rules_text}\n\n"
                    f"Conversation Turns to Consolidate ({len(candidates)}):\n\n{turns_text}"
                ),
            }
        ]

        raw_llm_response = await self.llm_provider.generate(
            messages=messages,
            system_prompt=CONSOLIDATION_SYSTEM_PROMPT,
        )

        extracted_items = self._parse_llm_json(raw_llm_response, candidates)

        # 4. Persist extracted memories, deduplicate, resolve conflicts, and embed into Qdrant
        procedural_records: List[MemoryProcedural] = []
        semantic_records: List[MemorySemantic] = []
        created_summaries: List[Dict[str, Any]] = []

        now_utc = datetime.now(timezone.utc)
        candidate_id_strings = [str(c.id) for c in candidates]

        for item in extracted_items:
            mem_type = item.get("type", "procedural").lower()
            statement_text = item.get("statement", "").strip()
            if not statement_text:
                continue

            category = item.get("category", "coding_style" if mem_type == "procedural" else "project_fact")
            confidence = float(item.get("confidence", 0.85))
            source_ids = item.get("source_episodic_ids") or candidate_id_strings

            # Compute embedding vector
            vector = await self.embedding_provider.embed_text(statement_text)

            if mem_type == "procedural":
                current_active_proc = list(
                    db.exec(select(MemoryProcedural).where(MemoryProcedural.is_active == True)).all()  # noqa: E712
                )

                llm_supersedes_id = item.get("supersedes_id")
                llm_supersedes_stmt = item.get("supersedes_statement")

                # Check if this rule conflicts with any active rule
                conflicting_rules: List[MemoryProcedural] = []
                for existing in current_active_proc:
                    is_conflict = (
                        (llm_supersedes_id and str(existing.id) == str(llm_supersedes_id))
                        or (
                            llm_supersedes_stmt
                            and (
                                llm_supersedes_stmt.lower() in existing.rule_statement.lower()
                                or existing.rule_statement.lower() in llm_supersedes_stmt.lower()
                            )
                        )
                        or self._is_conflict(existing.rule_statement, statement_text)
                    )
                    if is_conflict:
                        conflicting_rules.append(existing)

                if conflicting_rules:
                    # Contradiction detected! This is a paradigm/preference shift.
                    mem_id = uuid.uuid4()
                    point_id = str(mem_id)
                    item_version = 1
                    superseded_id: Optional[uuid.UUID] = None

                    for conflict_rule in conflicting_rules:
                        superseded_id = conflict_rule.id
                        if conflict_rule.version >= item_version:
                            item_version = conflict_rule.version + 1
                        logger.info(
                            "Conflict detected! Deprecating older procedural rule",
                            older_id=str(conflict_rule.id),
                            older_rule=conflict_rule.rule_statement,
                            new_rule=statement_text,
                            new_version=item_version,
                        )
                        conflict_rule.is_active = False
                        conflict_rule.active = False
                        conflict_rule.superseded_by = mem_id
                        conflict_rule.updated_at = now_utc
                        db.add(conflict_rule)
                        update_memory_payload(str(conflict_rule.id), {"is_active": False})

                    # Also deactivate any pre-existing duplicate row of this same statement
                    for existing in current_active_proc:
                        if existing not in conflicting_rules:
                            if self._compute_text_similarity(statement_text, existing.rule_statement) > 0.88:
                                existing.is_active = False
                                existing.active = False
                                existing.updated_at = now_utc
                                db.add(existing)
                                update_memory_payload(str(existing.id), {"is_active": False})

                    proc_record = MemoryProcedural(
                        id=mem_id,
                        rule_statement=statement_text,
                        category=category,
                        confidence=confidence,
                        source="consolidation_inference",
                        source_episodic_ids=source_ids,
                        embedding_id=point_id,
                        active=True,
                        is_active=True,
                        version=item_version,
                        superseded_by=None,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    db.add(proc_record)
                    procedural_records.append(proc_record)
                    created_summaries.append({
                        "id": point_id,
                        "type": "procedural",
                        "action": "superseded",
                        "statement": statement_text,
                        "category": category,
                        "confidence": confidence,
                        "version": item_version,
                        "superseded_id": str(superseded_id) if superseded_id else None,
                    })

                    payload = {
                        "memory_id": point_id,
                        "memory_type": mem_type,
                        "content": statement_text,
                        "category": category,
                        "confidence": confidence,
                        "source_episodic_ids": source_ids,
                        "is_active": True,
                        "version": item_version,
                        "created_at": now_utc.isoformat(),
                    }
                    try:
                        upsert_memory_vector(point_id=point_id, vector=vector, payload=payload)
                    except Exception as exc:
                        logger.warning("Vector upsert failed for consolidated item", point_id=point_id, error=str(exc))
                    continue

                # -------------------------------------------------------------
                # NO CONFLICT DETECTED: CHECK DEDUPLICATION (Similarity > 0.88)
                # -------------------------------------------------------------
                duplicate_found = False
                try:
                    qdrant_hits = search_memory_vectors(
                        query_vector=vector,
                        limit=5,
                        active_only=True,
                    )
                    for hit in qdrant_hits:
                        if hit.get("score", 0.0) > 0.88:
                            hit_id = hit.get("id")
                            for ar in current_active_proc:
                                if str(ar.id) == str(hit_id):
                                    duplicate_found = True
                                    ar.confidence = min(1.0, round(max(float(ar.confidence or 0.85), confidence) + 0.05, 2))
                                    ar.updated_at = now_utc
                                    merged_sources = set(ar.source_episodic_ids or [])
                                    for s_id in source_ids:
                                        merged_sources.add(s_id)
                                    ar.source_episodic_ids = list(merged_sources)
                                    db.add(ar)
                                    update_memory_payload(
                                        str(ar.id),
                                        {
                                            "confidence": ar.confidence,
                                            "updated_at": now_utc.isoformat(),
                                            "source_episodic_ids": ar.source_episodic_ids,
                                            "is_active": True,
                                        },
                                    )
                                    logger.info(
                                        "Duplicate rule detected via vector similarity > 0.88. Reinforced rule.",
                                        rule_id=str(ar.id),
                                        statement=ar.rule_statement,
                                        similarity=hit.get("score"),
                                        new_confidence=ar.confidence,
                                    )
                                    created_summaries.append({
                                        "id": str(ar.id),
                                        "type": "procedural",
                                        "action": "reinforced",
                                        "statement": ar.rule_statement,
                                        "confidence": ar.confidence,
                                        "version": ar.version,
                                    })
                                    break
                        if duplicate_found:
                            break
                except Exception as exc:
                    logger.warning("Vector deduplication search failed", error=str(exc))

                if not duplicate_found:
                    dup_id_llm = item.get("duplicate_of_id")
                    for ar in current_active_proc:
                        text_sim = self._compute_text_similarity(statement_text, ar.rule_statement)
                        if text_sim > 0.88 or (dup_id_llm and str(ar.id) == str(dup_id_llm)):
                            duplicate_found = True
                            ar.confidence = min(1.0, round(max(float(ar.confidence or 0.85), confidence) + 0.05, 2))
                            ar.updated_at = now_utc
                            merged_sources = set(ar.source_episodic_ids or [])
                            for s_id in source_ids:
                                merged_sources.add(s_id)
                            ar.source_episodic_ids = list(merged_sources)
                            db.add(ar)
                            update_memory_payload(
                                str(ar.id),
                                {
                                    "confidence": ar.confidence,
                                    "updated_at": now_utc.isoformat(),
                                    "source_episodic_ids": ar.source_episodic_ids,
                                    "is_active": True,
                                },
                            )
                            logger.info(
                                "Duplicate rule detected via text similarity > 0.88. Reinforced rule.",
                                rule_id=str(ar.id),
                                statement=ar.rule_statement,
                                similarity=text_sim,
                                new_confidence=ar.confidence,
                            )
                            created_summaries.append({
                                "id": str(ar.id),
                                "type": "procedural",
                                "action": "reinforced",
                                "statement": ar.rule_statement,
                                "confidence": ar.confidence,
                                "version": ar.version,
                            })
                            break

                if duplicate_found:
                    continue

                # -------------------------------------------------------------
                # BRAND NEW PROCEDURAL RULE (No conflict, no duplicate)
                # -------------------------------------------------------------
                mem_id = uuid.uuid4()
                point_id = str(mem_id)
                proc_record = MemoryProcedural(
                    id=mem_id,
                    rule_statement=statement_text,
                    category=category,
                    confidence=confidence,
                    source="consolidation_inference",
                    source_episodic_ids=source_ids,
                    embedding_id=point_id,
                    active=True,
                    is_active=True,
                    version=1,
                    superseded_by=None,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                db.add(proc_record)
                procedural_records.append(proc_record)
                created_summaries.append({
                    "id": point_id,
                    "type": "procedural",
                    "action": "created",
                    "statement": statement_text,
                    "category": category,
                    "confidence": confidence,
                    "version": 1,
                    "superseded_id": None,
                })

                payload = {
                    "memory_id": point_id,
                    "memory_type": mem_type,
                    "content": statement_text,
                    "category": category,
                    "confidence": confidence,
                    "source_episodic_ids": source_ids,
                    "is_active": True,
                    "version": 1,
                    "created_at": now_utc.isoformat(),
                }
                try:
                    upsert_memory_vector(point_id=point_id, vector=vector, payload=payload)
                except Exception as exc:
                    logger.warning("Vector upsert failed for consolidated item", point_id=point_id, error=str(exc))

            else:
                # Semantic memory handling
                current_active_sem = list(
                    db.exec(select(MemorySemantic).where(MemorySemantic.is_active == True)).all()  # noqa: E712
                )
                llm_supersedes_id = item.get("supersedes_id")
                llm_supersedes_stmt = item.get("supersedes_statement")

                conflicting_facts: List[MemorySemantic] = []
                for existing_s in current_active_sem:
                    is_conflict = (
                        (llm_supersedes_id and str(existing_s.id) == str(llm_supersedes_id))
                        or (
                            llm_supersedes_stmt
                            and (
                                llm_supersedes_stmt.lower() in existing_s.statement.lower()
                                or existing_s.statement.lower() in llm_supersedes_stmt.lower()
                            )
                        )
                        or (existing_s.category == category and self._is_conflict(existing_s.statement, statement_text))
                    )
                    if is_conflict:
                        conflicting_facts.append(existing_s)

                if conflicting_facts:
                    mem_id = uuid.uuid4()
                    point_id = str(mem_id)
                    item_version = 1
                    superseded_id = None

                    for conflict_fact in conflicting_facts:
                        superseded_id = conflict_fact.id
                        if conflict_fact.version >= item_version:
                            item_version = conflict_fact.version + 1
                        logger.info(
                            "Conflict detected! Deprecating older semantic fact",
                            older_id=str(conflict_fact.id),
                            older_statement=conflict_fact.statement,
                            new_statement=statement_text,
                            new_version=item_version,
                        )
                        conflict_fact.is_active = False
                        conflict_fact.superseded_by = mem_id
                        conflict_fact.updated_at = now_utc
                        db.add(conflict_fact)
                        update_memory_payload(str(conflict_fact.id), {"is_active": False})

                    sem_record = MemorySemantic(
                        id=mem_id,
                        statement=statement_text,
                        category=category,
                        confidence=confidence,
                        source_episodic_ids=source_ids,
                        embedding_id=point_id,
                        pinned=False,
                        is_active=True,
                        version=item_version,
                        superseded_by=None,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    db.add(sem_record)
                    semantic_records.append(sem_record)
                    created_summaries.append({
                        "id": point_id,
                        "type": "semantic",
                        "action": "superseded",
                        "statement": statement_text,
                        "category": category,
                        "confidence": confidence,
                        "version": item_version,
                        "superseded_id": str(superseded_id) if superseded_id else None,
                    })

                    payload = {
                        "memory_id": point_id,
                        "memory_type": mem_type,
                        "content": statement_text,
                        "category": category,
                        "confidence": confidence,
                        "source_episodic_ids": source_ids,
                        "is_active": True,
                        "version": item_version,
                        "created_at": now_utc.isoformat(),
                    }
                    try:
                        upsert_memory_vector(point_id=point_id, vector=vector, payload=payload)
                    except Exception as exc:
                        logger.warning("Vector upsert failed for consolidated item", point_id=point_id, error=str(exc))
                    continue

                # Semantic Deduplication
                dup_id_llm = item.get("duplicate_of_id")
                duplicate_found = False
                for as_fact in current_active_sem:
                    text_sim = self._compute_text_similarity(statement_text, as_fact.statement)
                    if text_sim > 0.88 or (dup_id_llm and str(as_fact.id) == str(dup_id_llm)):
                        duplicate_found = True
                        as_fact.confidence = min(1.0, round(max(float(as_fact.confidence or 0.85), confidence) + 0.05, 2))
                        as_fact.updated_at = now_utc
                        merged_sources = set(as_fact.source_episodic_ids or [])
                        for s_id in source_ids:
                            merged_sources.add(s_id)
                        as_fact.source_episodic_ids = list(merged_sources)
                        db.add(as_fact)
                        update_memory_payload(
                            str(as_fact.id),
                            {
                                "confidence": as_fact.confidence,
                                "updated_at": now_utc.isoformat(),
                                "source_episodic_ids": as_fact.source_episodic_ids,
                                "is_active": True,
                            },
                        )
                        logger.info(
                            "Duplicate semantic fact detected. Reinforced fact.",
                            fact_id=str(as_fact.id),
                            statement=as_fact.statement,
                            similarity=text_sim,
                        )
                        created_summaries.append({
                            "id": str(as_fact.id),
                            "type": "semantic",
                            "action": "reinforced",
                            "statement": as_fact.statement,
                            "confidence": as_fact.confidence,
                            "version": as_fact.version,
                        })
                        break

                if duplicate_found:
                    continue

                # Brand new semantic fact
                mem_id = uuid.uuid4()
                point_id = str(mem_id)
                sem_record = MemorySemantic(
                    id=mem_id,
                    statement=statement_text,
                    category=category,
                    confidence=confidence,
                    source_episodic_ids=source_ids,
                    embedding_id=point_id,
                    pinned=False,
                    is_active=True,
                    version=1,
                    superseded_by=None,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                db.add(sem_record)
                semantic_records.append(sem_record)
                created_summaries.append({
                    "id": point_id,
                    "type": "semantic",
                    "action": "created",
                    "statement": statement_text,
                    "category": category,
                    "confidence": confidence,
                    "version": 1,
                    "superseded_id": None,
                })

                payload = {
                    "memory_id": point_id,
                    "memory_type": mem_type,
                    "content": statement_text,
                    "category": category,
                    "confidence": confidence,
                    "source_episodic_ids": source_ids,
                    "is_active": True,
                    "version": 1,
                    "created_at": now_utc.isoformat(),
                }
                try:
                    upsert_memory_vector(point_id=point_id, vector=vector, payload=payload)
                except Exception as exc:
                    logger.warning("Vector upsert failed for consolidated item", point_id=point_id, error=str(exc))

        # 5. Mark candidate episodic rows as consolidated
        for cand in candidates:
            cand.consolidated = True
            db.add(cand)

        # Commit database transaction
        db.commit()

        logger.info(
            "Consolidation pass completed successfully",
            processed_episodic=len(candidates),
            procedural_created=len(procedural_records),
            semantic_created=len(semantic_records),
        )

        return {
            "status": "success",
            "message": f"Successfully consolidated {len(candidates)} episodic turns.",
            "processed_episodic_count": len(candidates),
            "procedural_created_count": len(procedural_records),
            "semantic_created_count": len(semantic_records),
            "memories": created_summaries,
        }

    def _parse_llm_json(
        self,
        raw_text: str,
        candidates: List[MemoryEpisodic],
    ) -> List[Dict[str, Any]]:
        """Safely parse LLM JSON extraction with heuristic fallback."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception as err:
            logger.warning("Could not parse LLM output as JSON, attempting heuristic extraction", error=str(err))

        # Heuristic fallback: extract rule statements directly from candidates
        fallback_items: List[Dict[str, Any]] = []
        for cand in candidates:
            text = cand.content
            for line in text.split("\n"):
                line_str = line.strip()
                if not line_str.lower().startswith("user:"):
                    continue
                lower = line_str.lower()
                if any(k in lower for k in ["prefer", "remember", "always", "never", "typing", "oop", "functional", "docstring", "docstrings", "guideline", "guidelines", "no longer", "stop"]):
                    clean_line = re.sub(r"^(user:\s*|hey athena,?\s*|athena,?\s*|update my guidelines:\s*|remember that\s*|assistant:\s*)", "", line_str, flags=re.IGNORECASE).strip()
                    if clean_line:
                        supersedes_stmt = None
                        if "docstring" in clean_line.lower() or "docstrings" in clean_line.lower():
                            if any(neg in clean_line.lower() for neg in ["no longer", "stop", "do not", "don't", "never", "no "]):
                                stmt = "Do not write docstrings for public functions."
                                supersedes_stmt = "Always write docstrings for public functions."
                            else:
                                stmt = "Always write docstrings for public functions."
                                supersedes_stmt = "Do not write docstrings for public functions."
                        elif "oop" in clean_line.lower() or "object-oriented" in clean_line.lower() or "classes" in clean_line.lower():
                            stmt = "Prefer writing Python code in an object-oriented class-based style."
                            supersedes_stmt = "Prefer writing Python code in a modular functional style."
                        elif "typing" in clean_line.lower() or "strict" in clean_line.lower():
                            stmt = "Prefer strict typing in Python code."
                        elif "functional" in clean_line.lower() or "modular" in clean_line.lower():
                            stmt = "Prefer writing Python code in a modular functional style."
                            supersedes_stmt = "Prefer writing Python code in an object-oriented class-based style."
                        else:
                            stmt = f"Prefer {clean_line}" if not clean_line.lower().startswith("prefer") else clean_line

                        fallback_items.append({
                            "type": "procedural",
                            "statement": stmt,
                            "category": "coding_style",
                            "confidence": 0.85,
                            "supersedes_statement": supersedes_stmt,
                            "source_episodic_ids": [str(cand.id)],
                        })

        if not fallback_items:
            fallback_items.append({
                "type": "procedural",
                "statement": "Maintain modularity and high code quality.",
                "category": "coding_style",
                "confidence": 0.75,
                "source_episodic_ids": [str(c.id) for c in candidates],
            })

        return fallback_items

    def _is_conflict(self, statement_a: str, statement_b: str) -> bool:
        """Detect whether two rule statements contradict or supersede each other."""
        a = statement_a.lower().strip()
        b = statement_b.lower().strip()

        if a == b:
            return False

        # Check for direct docstring negation
        if "docstring" in a and "docstring" in b:
            a_neg = any(term in a for term in ["do not", "don't", "stop", "no longer", "never", "no "])
            b_neg = any(term in b for term in ["do not", "don't", "stop", "no longer", "never", "no "])
            if (a_neg and not b_neg) or (b_neg and not a_neg):
                return True

        opposing_clusters = [
            # Functional vs OOP / Class-based
            (
                {"functional", "modular functional", "pure functions", "pipeline"},
                {"oop", "object-oriented", "classes", "class-based", "class based"},
            ),
            # Strict vs Dynamic typing
            (
                {"strict typing", "type annotations", "typed code", "pydantic"},
                {"dynamic typing", "untyped", "no types"},
            ),
            # Test frameworks
            ({"pytest"}, {"unittest"}),
            # CSS approaches
            ({"tailwind"}, {"vanilla css", "plain css"}),
            # Async vs Sync
            ({"synchronous", "sync"}, {"asynchronous", "async"}),
            # Indentation
            ({"tabs"}, {"spaces"}),
        ]

        for cluster_1, cluster_2 in opposing_clusters:
            a_has_1 = any(term in a for term in cluster_1)
            b_has_1 = any(term in b for term in cluster_1)
            a_has_2 = any(term in a for term in cluster_2)
            b_has_2 = any(term in b for term in cluster_2)

            if (a_has_1 and b_has_2) or (a_has_2 and b_has_1):
                return True

        # Check for direct style overrides within the same programming language
        if "python" in a and "python" in b:
            a_oop = any(t in a for t in ["oop", "object-oriented", "class-based", "classes"])
            b_oop = any(t in b for t in ["oop", "object-oriented", "class-based", "classes"])
            a_func = any(t in a for t in ["functional", "pure functions", "modular functional"])
            b_func = any(t in b for t in ["functional", "pure functions", "modular functional"])
            if (a_oop and b_func) or (a_func and b_oop):
                return True

        return False

    def decay_inactive_rules(
        self,
        db: SQLModelSession,
        inactivity_hours: float = 24.0,
        decay_rate: float = 0.05,
        minimum_active_confidence: float = 0.40,
    ) -> Dict[str, Any]:
        """Decay confidence of active procedural rules not accessed recently, archiving if below minimum_active_confidence."""
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=inactivity_hours)

        stmt = select(MemoryProcedural).where(MemoryProcedural.is_active == True)  # noqa: E712
        active_rules = list(db.exec(stmt).all())

        decayed_rules: List[Dict[str, Any]] = []
        archived_rules: List[Dict[str, Any]] = []

        for rule in active_rules:
            rule_access_time = rule.last_accessed_at or rule.updated_at or rule.created_at
            if rule_access_time.tzinfo is None:
                rule_access_time = rule_access_time.replace(tzinfo=timezone.utc)

            if rule_access_time <= cutoff_time:
                old_conf = rule.confidence
                new_conf = round(max(0.0, old_conf - decay_rate), 4)
                rule.confidence = new_conf
                rule.updated_at = now

                if new_conf < minimum_active_confidence:
                    rule.is_active = False
                    rule.active = False
                    rule.archived_reason = "decay"
                    db.add(rule)
                    archived_rules.append({
                        "id": str(rule.id),
                        "statement": rule.rule_statement,
                        "old_confidence": old_conf,
                        "new_confidence": new_conf,
                        "archived_reason": "decay",
                    })

                    # Sync Qdrant payload: is_active=False
                    try:
                        client = get_qdrant_client()
                        client.set_payload(
                            collection_name=DEFAULT_COLLECTION_NAME,
                            payload={
                                "is_active": False,
                                "confidence": new_conf,
                                "archived_reason": "decay",
                            },
                            points=[str(rule.id)],
                        )
                    except Exception:
                        update_memory_payload(
                            str(rule.id),
                            {
                                "is_active": False,
                                "confidence": new_conf,
                                "archived_reason": "decay",
                            },
                        )
                else:
                    db.add(rule)
                    decayed_rules.append({
                        "id": str(rule.id),
                        "statement": rule.rule_statement,
                        "old_confidence": old_conf,
                        "new_confidence": new_conf,
                    })

                    # Sync Qdrant payload: confidence
                    try:
                        client = get_qdrant_client()
                        client.set_payload(
                            collection_name=DEFAULT_COLLECTION_NAME,
                            payload={"confidence": new_conf},
                            points=[str(rule.id)],
                        )
                    except Exception:
                        update_memory_payload(str(rule.id), {"confidence": new_conf})

        if decayed_rules or archived_rules:
            db.commit()
            logger.info(
                "Completed memory decay pass",
                decayed_count=len(decayed_rules),
                archived_count=len(archived_rules),
            )

        return {
            "status": "success",
            "decayed_count": len(decayed_rules),
            "archived_count": len(archived_rules),
            "decayed_rules": decayed_rules,
            "archived_rules": archived_rules,
        }

