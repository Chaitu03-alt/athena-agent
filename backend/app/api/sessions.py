"""FastAPI router for sessions and message streaming."""

import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session as SQLModelSession, select, col

from app.db.session import get_session
from app.models.session import Session
from app.models.message import Message
from app.models.memory import MemoryEpisodic
from app.orchestrator.agent import AgentOrchestrator

router = APIRouter(prefix="/sessions", tags=["Sessions"])
orchestrator = AgentOrchestrator()


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"
    project_id: Optional[uuid.UUID] = None


class SendMessageRequest(BaseModel):
    content: str


class SessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    project_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    token_count: Optional[int] = None


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: Optional[CreateSessionRequest] = None,
    db: SQLModelSession = Depends(get_session),
) -> SessionResponse:
    """Create a new chat session."""
    title = (payload.title if payload and payload.title else "New Chat")
    project_id = payload.project_id if payload else None

    session_obj = Session(
        id=uuid.uuid4(),
        title=title,
        project_id=project_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)

    return SessionResponse(
        id=session_obj.id,
        title=session_obj.title,
        project_id=session_obj.project_id,
        created_at=session_obj.created_at,
        updated_at=session_obj.updated_at,
        message_count=0,
    )


@router.get("", response_model=List[SessionResponse])
def list_sessions(
    db: SQLModelSession = Depends(get_session),
) -> List[SessionResponse]:
    """List all chat sessions ordered by most recently updated."""
    statement = select(Session).order_by(col(Session.updated_at).desc())
    sessions = db.exec(statement).all()

    result = []
    for s in sessions:
        msg_count_statement = select(Message).where(Message.session_id == s.id)
        msg_count = len(db.exec(msg_count_statement).all())
        result.append(
            SessionResponse(
                id=s.id,
                title=s.title,
                project_id=s.project_id,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=msg_count,
            )
        )
    return result


@router.get("/{session_id}", response_model=SessionResponse)
def get_session_detail(
    session_id: uuid.UUID,
    db: SQLModelSession = Depends(get_session),
) -> SessionResponse:
    """Get metadata for a specific session."""
    session_obj = db.get(Session, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_count_statement = select(Message).where(Message.session_id == session_id)
    msg_count = len(db.exec(msg_count_statement).all())

    return SessionResponse(
        id=session_obj.id,
        title=session_obj.title,
        project_id=session_obj.project_id,
        created_at=session_obj.created_at,
        updated_at=session_obj.updated_at,
        message_count=msg_count,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: uuid.UUID,
    db: SQLModelSession = Depends(get_session),
) -> None:
    """Delete a chat session and its associated messages."""
    session_obj = db.get(Session, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    # 1. Delete associated episodic memories first to satisfy foreign key constraints
    episodic_records = db.exec(select(MemoryEpisodic).where(MemoryEpisodic.session_id == session_id)).all()
    for ep in episodic_records:
        db.delete(ep)

    # 2. Delete related messages
    messages = db.exec(select(Message).where(Message.session_id == session_id)).all()
    for m in messages:
        db.delete(m)

    # 3. Delete session
    db.delete(session_obj)
    db.commit()


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
def get_session_messages(
    session_id: uuid.UUID,
    db: SQLModelSession = Depends(get_session),
) -> List[MessageResponse]:
    """Retrieve all messages for a session in chronological order."""
    session_obj = db.get(Session, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    statement = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(col(Message.created_at).asc())
    )
    messages = db.exec(statement).all()

    return [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            token_count=m.token_count,
        )
        for m in messages
    ]


@router.post("/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    payload: SendMessageRequest,
    db: SQLModelSession = Depends(get_session),
) -> StreamingResponse:
    """Send a user message to the session and receive streamed Server-Sent Events."""
    session_obj = db.get(Session, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    user_content = payload.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    async def event_generator():
        try:
            async for event in orchestrator.handle_turn_stream(session_id, user_content, db):
                data = json.dumps(event)
                yield f"data: {data}\n\n"
        except Exception as e:
            err = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
