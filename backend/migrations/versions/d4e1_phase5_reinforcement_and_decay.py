"""add_reinforcement_and_decay_attributes_to_memory_procedural

Revision ID: d4e1a2b3c4d5
Revises: c3d1e0fa5678
Create Date: 2026-09-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'c3d1e0fa5678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_accessed_at, access_count, and archived_reason to memory_procedural."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "memory_procedural" in existing_tables:
        proc_columns = [c["name"] for c in inspector.get_columns("memory_procedural")]
        with op.batch_alter_table("memory_procedural") as batch_op:
            if "last_accessed_at" not in proc_columns:
                batch_op.add_column(
                    sa.Column(
                        "last_accessed_at",
                        sa.DateTime(timezone=True),
                        nullable=False,
                        server_default=sa.func.now(),
                    )
                )
            if "access_count" not in proc_columns:
                batch_op.add_column(
                    sa.Column(
                        "access_count",
                        sa.Integer(),
                        nullable=False,
                        server_default="1",
                    )
                )
            if "archived_reason" not in proc_columns:
                batch_op.add_column(
                    sa.Column(
                        "archived_reason",
                        sa.String(length=255),
                        nullable=True,
                    )
                )


def downgrade() -> None:
    """Remove reinforcement and decay attributes from memory_procedural."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "memory_procedural" in existing_tables:
        proc_columns = [c["name"] for c in inspector.get_columns("memory_procedural")]
        with op.batch_alter_table("memory_procedural") as batch_op:
            if "archived_reason" in proc_columns:
                batch_op.drop_column("archived_reason")
            if "access_count" in proc_columns:
                batch_op.drop_column("access_count")
            if "last_accessed_at" in proc_columns:
                batch_op.drop_column("last_accessed_at")
