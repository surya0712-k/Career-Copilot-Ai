"""Sync columns for DBs created via create_all before Alembic ran

Revision ID: 004
Revises: 003
Create Date: 2026-06-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    memory_cols = {c["name"] for c in inspector.get_columns("memory_chunks")}
    if "goal_id" not in memory_cols:
        op.add_column("memory_chunks", sa.Column("goal_id", sa.UUID(), nullable=True))
        op.create_foreign_key("fk_memory_chunks_goal", "memory_chunks", "goals", ["goal_id"], ["id"])
    if "source_id" not in memory_cols:
        op.add_column("memory_chunks", sa.Column("source_id", sa.String(128), nullable=True))
        op.create_index("ix_memory_chunks_source_id", "memory_chunks", ["source_id"])

    roadmap_cols = {c["name"] for c in inspector.get_columns("roadmaps")}
    if "version" not in roadmap_cols:
        op.add_column("roadmaps", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    if "supersedes_id" not in roadmap_cols:
        op.add_column("roadmaps", sa.Column("supersedes_id", sa.UUID(), nullable=True))
        op.create_foreign_key("fk_roadmaps_supersedes", "roadmaps", "roadmaps", ["supersedes_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_roadmaps_supersedes", "roadmaps", type_="foreignkey")
    op.drop_column("roadmaps", "supersedes_id")
    op.drop_column("roadmaps", "version")
    op.drop_index("ix_memory_chunks_source_id", "memory_chunks")
    op.drop_constraint("fk_memory_chunks_goal", "memory_chunks", type_="foreignkey")
    op.drop_column("memory_chunks", "source_id")
    op.drop_column("memory_chunks", "goal_id")
