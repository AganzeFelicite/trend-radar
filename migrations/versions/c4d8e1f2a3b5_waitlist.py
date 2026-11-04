"""waitlist

Revision ID: c4d8e1f2a3b5
Revises: b7e1c2d9a4f0
Create Date: 2026-11-04 05:40:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e1f2a3b5"
down_revision: Union[str, Sequence[str], None] = "b7e1c2d9a4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "waitlist",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("email"),
    )


def downgrade() -> None:
    op.drop_table("waitlist")
