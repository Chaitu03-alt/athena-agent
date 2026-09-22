"""Project, ToolCallLog, and FeedbackEvent models matching SCHEMA.md §1.7, 1.8, 1.9."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import Column, JSON
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    """Registered project model matching SCHEMA.md §1.7."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "projects"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    name: str = Field(nullable=False)
    path: str = Field(nullable=False)
    last_indexed_at: Optional[datetime] = Field(default=None, nullable=True)
    watch_enabled: bool = Field(default=True, nullable=False)
    file_count: Optional[int] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ToolCallLog(SQLModel, table=True):
    """Tool execution log model matching SCHEMA.md §1.8."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "tool_calls_log"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    message_id: uuid.UUID = Field(
        foreign_key="messages.id",
        index=True,
        nullable=False,
    )
    tool_name: str = Field(nullable=False)
    args_json: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False, default=dict)
    )
    risk_level: str = Field(nullable=False)  # 'safe', 'destructive'
    confirmed: Optional[bool] = Field(default=None, nullable=True)
    result_json: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    status: str = Field(
        default="success", nullable=False
    )  # 'success', 'error', 'rejected'
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class FeedbackEvent(SQLModel, table=True):
    """User feedback event model matching SCHEMA.md §1.9."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "feedback_events"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    episodic_id: uuid.UUID = Field(
        foreign_key="memory_episodic.id",
        index=True,
        nullable=False,
    )
    feedback_type: str = Field(
        nullable=False
    )  # 'thumbs_up', 'thumbs_down', 'explicit_correction', 'implicit_edit'
    detail: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
