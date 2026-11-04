"""off_topic_flags

Revision ID: d9f3a7b1c2e4
Revises: c4d8e1f2a3b5
Create Date: 2026-11-04 09:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9f3a7b1c2e4"
down_revision: Union[str, Sequence[str], None] = "c4d8e1f2a3b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "off_topic_flags",
        sa.Column("topic_slug", sa.String(length=64), nullable=False),
        sa.Column("flagged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("topic_slug"),
    )


def downgrade() -> None:
    op.drop_table("off_topic_flags")
