"""item_embeddings, ai_topics (pgvector)

Revision ID: b7e1c2d9a4f0
Revises: 5642a39c07f4
Create Date: 2026-11-04 02:30:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "b7e1c2d9a4f0"
down_revision: Union[str, Sequence[str], None] = "5642a39c07f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.create_table(
        "item_embeddings",
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("item_id", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=96), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source", "item_id"], ["items.source", "items.item_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source", "item_id"),
    )
    op.create_table(
        "ai_topics",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("merged_into", sa.String(length=64), nullable=True),
        sa.Column("centroid", Vector(384), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("examples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("slug"),
    )


def downgrade() -> None:
    op.drop_table("ai_topics")
    op.drop_table("item_embeddings")  # the vector extension stays: other databases on the server may use it
