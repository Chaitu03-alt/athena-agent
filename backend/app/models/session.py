"""Session model definition."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class Session(SQLModel, table=True):
    """Chat session model matching SCHEMA.md §1.1."""

    __tablename__ = "sessions"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    title: str = Field(default="New Chat", nullable=False)
    project_id: Optional[uuid.UUID] = Field(default=None, nullable=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
