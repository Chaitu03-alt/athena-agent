"""Agent turn loop orchestrator for multi-turn chat and episodic logging."""

import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List
import structlog
from sqlmodel import Session as SQLModelSession, select

from app.models.session import Session
from app.models.message import Message
from app.models.memory import MemoryEpisodic, MemoryProcedural
from app.db.qdrant import search_memory_vectors
from app.providers.embedding_provider import get_embedding_provider
from app.providers.llm_provider import get_llm_provider
from app.services.chat import reinforce_rule_access, retrieve_memory_context
from app.orchestrator.prompts import get_system_prompt
from app.orchestrator.heuristics import compute_importance_score, extract_tags

logger = structlog.get_logger(__name__)


class AgentOrchestrator:
    """Coordinates prompt construction, LLM streaming, and episodic memory logging."""

    def __init__(self, max_history_turns: int = 20) -> None:
        self.max_history_turns = max_history_turns

    async def handle_turn_stream(
        self,
        session_id: uuid.UUID,
        user_content: str,
        db: SQLModelSession,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a single multi-turn chat step with streaming output and post-turn persistence."""
        # 1. Verify session exists
        session_obj = db.get(Session, session_id)
        if not session_obj:
            yield {"type": "error", "error": f"Session {session_id} not found."}
            return

        # 2. Persist user message
        user_msg = Message(
            id=uuid.uuid4(),
            session_id=session_id,
            role="user",
            content=user_content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # 3. Retrieve Active Procedural Memory and Semantic Context with graceful fallback
        context_data = await retrieve_memory_context(
            query_text=user_content,
            db=db,
            limit=5,
        )
        active_rules = context_data["active_rules"]
        retrieved_memories = context_data["retrieved_memories"]

        # 4. Fetch recent message history
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        all_messages: List[Message] = list(db.exec(statement).all())
        windowed_messages = all_messages[-self.max_history_turns :]

        llm_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in windowed_messages
            if msg.role in ("user", "assistant")
        ]

        system_prompt = get_system_prompt(
            active_rules=active_rules,
            retrieved_memories=retrieved_memories,
        )
        provider = get_llm_provider()

        # 5. Stream response from LLM
        full_response_parts: List[str] = []
        try:
            async for token in provider.stream_chat(llm_messages, system_prompt):
                full_response_parts.append(token)
                yield {"type": "token", "content": token}
        except Exception as exc:
            logger.error("Error during LLM stream", error=str(exc))
            yield {"type": "error", "error": f"LLM error: {str(exc)}"}
            return

        accumulated_response = "".join(full_response_parts)

        # 5. Persist assistant message
        assistant_msg = Message(
            id=uuid.uuid4(),
            session_id=session_id,
            role="assistant",
            content=accumulated_response,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)

        # 6. Post-turn logging: Episodic memory write with heuristic scoring
        importance = compute_importance_score(user_content, accumulated_response)
        tags = extract_tags(user_content)

        episodic_content = f"User: {user_content}\nAssistant: {accumulated_response}"
        episodic_entry = MemoryEpisodic(
            id=uuid.uuid4(),
            session_id=session_id,
            message_id=assistant_msg.id,
            content=episodic_content,
            entry_type="turn",
            importance_score=importance,
            feedback="none",
            pinned=False,
            consolidated=False,
            project_id=session_obj.project_id,
            tags=tags,
            created_at=datetime.now(timezone.utc),
        )
        db.add(episodic_entry)

        # 7. Update session metadata (title auto-generation on first turn)
        if session_obj.title in ("New Chat", "New Session", ""):
            words = user_content.strip().split()
            first_words = " ".join(words[:6])
            session_obj.title = first_words[:50] if first_words else "Chat Session"

        session_obj.updated_at = datetime.now(timezone.utc)
        db.add(session_obj)
        db.commit()
        db.refresh(assistant_msg)
        db.refresh(episodic_entry)

        # 8. Emit completion event
        yield {
            "type": "done",
            "message_id": str(assistant_msg.id),
            "importance_score": importance,
            "tags": tags,
            "session_title": session_obj.title,
        }
