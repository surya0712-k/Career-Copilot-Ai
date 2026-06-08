"""Add preferred_dsa_language and practice_projects

Revision ID: 005
Revises: 004
Create Date: 2026-06-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("preferred_dsa_language", sa.String(32), nullable=False, server_default="python"),
    )
    op.add_column(
        "goals",
        sa.Column("practice_projects", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("goals", "practice_projects")
    op.drop_column("profiles", "preferred_dsa_language")
