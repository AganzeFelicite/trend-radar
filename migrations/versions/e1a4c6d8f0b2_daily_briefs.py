"""daily_briefs

Revision ID: e1a4c6d8f0b2
Revises: d9f3a7b1c2e4
Create Date: 2026-11-04 09:30:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1a4c6d8f0b2"
down_revision: Union[str, Sequence[str], None] = "d9f3a7b1c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_briefs",
        sa.Column("brief_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("brief_date", "version"),
    )


def downgrade() -> None:
    op.drop_table("daily_briefs")
