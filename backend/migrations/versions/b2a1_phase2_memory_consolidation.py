"""create_phase2_memory_tables

Revision ID: b2a1c0de45f1
Revises: 83941aef8ee5
Create Date: 2026-09-19 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'b2a1c0de45f1'
down_revision: Union[str, Sequence[str], None] = '83941aef8ee5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Phase 2 memory consolidation."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. memory_semantic
    if "memory_semantic" not in existing_tables:
        op.create_table(
            "memory_semantic",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("statement", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("embedding_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
            sa.Column("source_episodic_ids", sa.JSON(), nullable=False),
            sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("superseded_by", sa.Uuid(), nullable=True),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("memory_semantic", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_memory_semantic_id"), ["id"], unique=False)

    # 2. memory_procedural
    if "memory_procedural" not in existing_tables:
        op.create_table(
            "memory_procedural",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("rule_statement", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="other"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="explicit_user"),
            sa.Column("source_episodic_ids", sa.JSON(), nullable=False),
            sa.Column("superseded_by", sa.Uuid(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("memory_procedural", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_memory_procedural_id"), ["id"], unique=False)

    # 3. consolidated column and index on memory_episodic
    if "memory_episodic" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("memory_episodic")]
        if "consolidated" not in columns:
            op.add_column(
                "memory_episodic",
                sa.Column("consolidated", sa.Boolean(), nullable=False, server_default="false"),
            )

        indexes = [idx["name"] for idx in inspector.get_indexes("memory_episodic")]
        if "ix_memory_episodic_consolidated_score" not in indexes:
            op.create_index(
                "ix_memory_episodic_consolidated_score",
                "memory_episodic",
                ["consolidated", "importance_score"],
            )


def downgrade() -> None:
    """Downgrade Phase 2 memory schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "memory_episodic" in existing_tables:
        indexes = [idx["name"] for idx in inspector.get_indexes("memory_episodic")]
        if "ix_memory_episodic_consolidated_score" in indexes:
            op.drop_index("ix_memory_episodic_consolidated_score", table_name="memory_episodic")

    if "memory_semantic" in existing_tables:
        op.drop_table("memory_semantic")

    if "memory_procedural" in existing_tables:
        op.drop_table("memory_procedural")
