"""Message model definition."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Column, JSON
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    """Message model matching SCHEMA.md §1.2."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "messages"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    session_id: uuid.UUID = Field(
        foreign_key="sessions.id",
        index=True,
        nullable=False,
    )
    role: str = Field(nullable=False)  # 'user', 'assistant', 'tool', 'system'
    content: str = Field(nullable=False)
    tool_call_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    token_count: Optional[int] = Field(default=None, nullable=True)
