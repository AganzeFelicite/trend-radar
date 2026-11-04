"""published_videos

Revision ID: a3c5e7f9b1d2
Revises: f2b5d7e9a1c3
Create Date: 2026-11-04 11:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f9b1d2"
down_revision: Union[str, Sequence[str], None] = "f2b5d7e9a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "published_videos",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("package_id", sa.String(length=64), nullable=True),
        sa.Column("views_24h", sa.BigInteger(), nullable=True),
        sa.Column("views_7d", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("published_videos")
