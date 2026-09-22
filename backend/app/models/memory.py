"""Memory models definition covering episodic, semantic, procedural, and approval queue."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, JSON
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel


class MemoryEpisodic(SQLModel, table=True):
    """Episodic memory model matching SCHEMA.md §1.3."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "memory_episodic"

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
    message_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="messages.id",
        nullable=True,
        index=True,
    )
    content: str = Field(nullable=False)
    embedding_id: Optional[str] = Field(default=None, nullable=True)
    entry_type: str = Field(
        default="turn",
        nullable=False,
    )  # 'turn', 'tool_call', 'decision', 'correction', 'daily_summary'
    importance_score: float = Field(default=0.5, nullable=False)
    feedback: str = Field(
        default="none",
        nullable=False,
    )  # 'none', 'positive', 'negative', 'corrected'
    pinned: bool = Field(default=False, nullable=False)
    consolidated: bool = Field(default=False, nullable=False)
    project_id: Optional[uuid.UUID] = Field(default=None, nullable=True, index=True)
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    archived_at: Optional[datetime] = Field(default=None, nullable=True)


class MemorySemantic(SQLModel, table=True):
    """Semantic memory model matching SCHEMA.md §1.4."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "memory_semantic"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    statement: str = Field(nullable=False)
    embedding_id: Optional[str] = Field(default=None, nullable=True)
    confidence: float = Field(default=0.8, nullable=False)
    source_episodic_ids: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    category: Optional[str] = Field(default=None, nullable=True)
    superseded_by: Optional[uuid.UUID] = Field(default=None, nullable=True)
    pinned: bool = Field(default=False, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class MemoryProcedural(SQLModel, table=True):
    """Procedural memory model matching SCHEMA.md §1.5."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "memory_procedural"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    rule_statement: str = Field(nullable=False)
    category: str = Field(
        default="other",
        nullable=False,
    )  # 'coding_style', 'communication_style', 'workflow', 'tooling', 'other'
    confidence: float = Field(default=0.8, nullable=False)
    source: str = Field(
        default="explicit_user",
        nullable=False,
    )  # 'explicit_user', 'implicit_correction', 'consolidation_inference'
    source_episodic_ids: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    superseded_by: Optional[uuid.UUID] = Field(default=None, nullable=True)
    active: bool = Field(default=True, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    version: int = Field(default=1, nullable=False)
    last_accessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    access_count: int = Field(default=1, nullable=False)
    archived_reason: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ApprovalQueueItem(SQLModel, table=True):
    """Approval queue model matching SCHEMA.md §1.6."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "approval_queue"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    proposal_type: str = Field(
        nullable=False
    )  # 'semantic_add', 'semantic_update', 'procedural_add', 'procedural_update', 'conflict'
    payload_json: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False, default=dict)
    )
    status: str = Field(
        default="pending", nullable=False
    )  # 'pending', 'approved', 'rejected', 'edited_approved'
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    resolved_at: Optional[datetime] = Field(default=None, nullable=True)
