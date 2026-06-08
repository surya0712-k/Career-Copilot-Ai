"""progress tracking and second brain fields

Revision ID: 003
Revises: 002
Create Date: 2026-06-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roadmaps", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("roadmaps", sa.Column("supersedes_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_roadmaps_supersedes", "roadmaps", "roadmaps", ["supersedes_id"], ["id"])

    op.add_column("memory_chunks", sa.Column("goal_id", sa.UUID(), nullable=True))
    op.add_column("memory_chunks", sa.Column("source_id", sa.String(128), nullable=True))
    op.create_foreign_key("fk_memory_chunks_goal", "memory_chunks", "goals", ["goal_id"], ["id"])
    op.create_index("ix_memory_chunks_source_id", "memory_chunks", ["source_id"])

    op.create_table(
        "user_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("completed_topics", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("weak_areas", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("total_study_hours", sa.Float(), server_default="0", nullable=False),
        sa.Column("last_interview_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("current_week", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "goal_id", name="uq_user_progress_goal"),
    )

    op.create_table(
        "completed_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("roadmap_id", sa.UUID(), nullable=False),
        sa.Column("milestone_id", sa.UUID(), nullable=False),
        sa.Column("task_title", sa.String(512), nullable=False),
        sa.Column("topic", sa.String(256), nullable=True),
        sa.Column("study_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"]),
        sa.ForeignKeyConstraint(["roadmap_id"], ["roadmaps.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "study_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.String(256), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "weak_areas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.String(256), nullable=False),
        sa.Column("source", sa.String(64), server_default="interview", nullable=False),
        sa.Column("severity", sa.String(32), server_default="medium", nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "goal_id", "topic", name="uq_weak_area_topic"),
    )


def downgrade() -> None:
    op.drop_table("weak_areas")
    op.drop_table("study_sessions")
    op.drop_table("completed_tasks")
    op.drop_table("user_progress")
    op.drop_index("ix_memory_chunks_source_id", "memory_chunks")
    op.drop_constraint("fk_memory_chunks_goal", "memory_chunks", type_="foreignkey")
    op.drop_column("memory_chunks", "source_id")
    op.drop_column("memory_chunks", "goal_id")
    op.drop_constraint("fk_roadmaps_supersedes", "roadmaps", type_="foreignkey")
    op.drop_column("roadmaps", "supersedes_id")
    op.drop_column("roadmaps", "version")
