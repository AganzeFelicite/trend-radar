"""drafts

Revision ID: f2b5d7e9a1c3
Revises: e1a4c6d8f0b2
Create Date: 2026-11-04 10:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b5d7e9a1c3"
down_revision: Union[str, Sequence[str], None] = "e1a4c6d8f0b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("brief_date", sa.Date(), nullable=False),
        sa.Column("brief_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("problems", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brief_date", "brief_version"], ["daily_briefs.brief_date", "daily_briefs.version"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("brief_date", "brief_version", "kind"),
    )


def downgrade() -> None:
    op.drop_table("drafts")
