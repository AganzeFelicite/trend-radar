from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
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


@contextmanager
def connector_run(source: str, job: str):
    """Yields (session, run). Records ok/error and finish time no matter how the job ends."""
    with Session(engine, expire_on_commit=False) as s:
        run = ConnectorRun(source=source, job=job, items_count=0, quota_used=0)
        s.add(run)
        s.commit()
        try:
            yield s, run
            run.status = "ok"
        except Exception as e:
            s.rollback()
            run.status, run.error = "error", repr(e)[:2000]
            raise
        finally:
            run.finished_at = func.now()
            s.add(run)
            s.commit()
