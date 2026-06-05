"""Drop pgvector embedding column (vectors now in Qdrant)

Revision ID: 002
Revises: 001
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("memory_chunks")]
    if "embedding" in columns:
        op.drop_column("memory_chunks", "embedding")


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("memory_chunks", sa.Column("embedding", sa.Text(), nullable=True))
