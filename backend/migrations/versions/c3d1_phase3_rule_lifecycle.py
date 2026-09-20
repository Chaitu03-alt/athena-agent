"""add_rule_lifecycle_and_versioning

Revision ID: c3d1e0fa5678
Revises: b2a1c0de45f1
Create Date: 2026-09-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d1e0fa5678'
down_revision: Union[str, Sequence[str], None] = 'b2a1c0de45f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active and version columns to memory_procedural and memory_semantic."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. memory_procedural updates
    if "memory_procedural" in existing_tables:
        proc_columns = [c["name"] for c in inspector.get_columns("memory_procedural")]
        if "is_active" not in proc_columns:
            op.add_column(
                "memory_procedural",
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            )
        if "version" not in proc_columns:
            op.add_column(
                "memory_procedural",
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            )

        proc_indexes = [idx["name"] for idx in inspector.get_indexes("memory_procedural")]
        if "ix_memory_procedural_active_category" not in proc_indexes:
            op.create_index(
                "ix_memory_procedural_active_category",
                "memory_procedural",
                ["is_active", "category"],
            )

    # 2. memory_semantic updates
    if "memory_semantic" in existing_tables:
        sem_columns = [c["name"] for c in inspector.get_columns("memory_semantic")]
        if "is_active" not in sem_columns:
            op.add_column(
                "memory_semantic",
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            )
        if "version" not in sem_columns:
            op.add_column(
                "memory_semantic",
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            )

        sem_indexes = [idx["name"] for idx in inspector.get_indexes("memory_semantic")]
        if "ix_memory_semantic_active_category" not in sem_indexes:
            op.create_index(
                "ix_memory_semantic_active_category",
                "memory_semantic",
                ["is_active", "category"],
            )


def downgrade() -> None:
    """Downgrade rule lifecycle schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "memory_procedural" in existing_tables:
        proc_indexes = [idx["name"] for idx in inspector.get_indexes("memory_procedural")]
        if "ix_memory_procedural_active_category" in proc_indexes:
            op.drop_index("ix_memory_procedural_active_category", table_name="memory_procedural")
        proc_columns = [c["name"] for c in inspector.get_columns("memory_procedural")]
        if "version" in proc_columns:
            op.drop_column("memory_procedural", "version")
        if "is_active" in proc_columns:
            op.drop_column("memory_procedural", "is_active")

    if "memory_semantic" in existing_tables:
        sem_indexes = [idx["name"] for idx in inspector.get_indexes("memory_semantic")]
        if "ix_memory_semantic_active_category" in sem_indexes:
            op.drop_index("ix_memory_semantic_active_category", table_name="memory_semantic")
        sem_columns = [c["name"] for c in inspector.get_columns("memory_semantic")]
        if "version" in sem_columns:
            op.drop_column("memory_semantic", "version")
        if "is_active" in sem_columns:
            op.drop_column("memory_semantic", "is_active")
