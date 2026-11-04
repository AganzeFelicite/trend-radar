from contextlib import contextmanager
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from trend_radar import config

engine = create_engine(config.DATABASE_URL)


class Base(DeclarativeBase):
    pass


class RawResponse(Base):
    """Every API response body, so we can re-process without re-fetching. Deleted after 30 days."""

    __tablename__ = "raw_responses"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    endpoint: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class Item(Base):
    """One video / stream / clip / article, from any source."""

    __tablename__ = "items"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    item_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    channel_id: Mapped[str | None] = mapped_column(String(128))
    channel_title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signal(Base):
    """A metric reading for an item. captured_at is bucketed (hour or day), so re-runs upsert instead of duplicating."""

    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    item_id: Mapped[str] = mapped_column(String(128))
    metric_name: Mapped[str] = mapped_column(String(32))
    metric_value: Mapped[int] = mapped_column(BigInteger)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["source", "item_id"], ["items.source", "items.item_id"], ondelete="CASCADE"),
        UniqueConstraint("source", "item_id", "metric_name", "captured_at"),
    )


class ConnectorRun(Base):
    """One job execution. quota_used is summed per day by the quota guard."""

    __tablename__ = "connector_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    job: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")
    items_count: Mapped[int] = mapped_column(default=0)
    quota_used: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_connector_runs_source_started_at", "source", "started_at"),)


EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2


class ItemEmbedding(Base):
    """One multilingual sentence embedding per item title. Written once (titles rarely change); rebuilt if the model changes."""

    __tablename__ = "item_embeddings"
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    model: Mapped[str] = mapped_column(String(96))
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["source", "item_id"], ["items.source", "items.item_id"], ondelete="CASCADE"),
    )


class AiTopic(Base):
    """Registry of clusters the AI step has seen, so topic IDs stay stable: a new cluster whose centroid is within
    cosine 0.8 of a registered one reuses it, with no new LLM call. status: active (a topic of its own) · merged (same
    subject as merged_into) · noise (no shared subject) · spam (its items are left out of scoring)."""

    __tablename__ = "ai_topics"
    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    merged_into: Mapped[str | None] = mapped_column(String(64))
    centroid = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    items_count: Mapped[int] = mapped_column(default=0)
    examples: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Waitlist(Base):
    """Emails from the site's waitlist form (daily digest, P5.1). Stored lowercased; one row per address."""

    __tablename__ = "waitlist"
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OffTopicFlag(Base):
    """Topics the owner marked as off-topic buzz (memes, non-game). dbt keeps them out of the public ranking and
    lists them separately. Set by hand for now (scripts/radar.sh offtopic), by /admin later (P6.1)."""

    __tablename__ = "off_topic_flags"
    topic_slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    flagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyBrief(Base):
    """One verified data snapshot per day (trend_radar/brief.py). Re-running the same day adds a version; drafts,
    emails and content packages are written only from an approved one (P9.3). status: draft · approved · published."""

    __tablename__ = "daily_briefs"
    brief_date: Mapped[date] = mapped_column(Date, primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Draft(Base):
    """AI-written copy for one brief (trend_radar/writer.py). template = the model's text with {{placeholders}};
    text = the same with every fact filled in from the brief by code. status: draft · flagged (failed the grounding
    check twice; problems says why). approved / rejected come with the approval page (P9.3)."""

    __tablename__ = "drafts"
    brief_date: Mapped[date] = mapped_column(Date, primary_key=True)
    brief_version: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    template: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    problems: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["brief_date", "brief_version"], ["daily_briefs.brief_date", "daily_briefs.version"],
                             ondelete="CASCADE"),
    )


class PublishedVideo(Base):
    """One video the owner published (P9.7 tracking; entered by hand for now: scripts/radar.sh published). New package
    titles must differ from the last 7. Views filled in later (manual, then YouTube Analytics for our own channel)."""

    __tablename__ = "published_videos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    platform: Mapped[str] = mapped_column(String(32))
    format: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    package_id: Mapped[str | None] = mapped_column(String(64))
    views_24h: Mapped[int | None] = mapped_column(BigInteger)
    views_7d: Mapped[int | None] = mapped_column(BigInteger)


@contextmanager
def connector_run(source: str, job: str):
    """Yields (session, run). Records ok/error and finish time no matter how the job ends."""
    with Session(engine, expire_on_commit=False) as s:
        run = ConnectorRun(source=source, job=job, items_count=0, quota_used=0)
        s.add(run)
        s.commit()
        try:
            yield s, run
            if run.status == "running":  # a job may set its own status, e.g. "waiting"
                run.status = "ok"
        except Exception as e:
            s.rollback()
            run.status, run.error = "error", repr(e)[:2000]
            raise
        finally:
            run.finished_at = func.now()
            s.add(run)
            s.commit()
