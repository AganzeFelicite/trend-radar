"""Shared by every connector: HTTP retry policy, time buckets, idempotent upserts."""

from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from trend_radar.db import Item, Signal


def retryable(e: BaseException) -> bool:
    """Retry rate limits, server errors and network failures. Other 4xx won't fix themselves."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code == 429 or e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)


def retry_http(fn):
    return retry(
        retry=retry_if_exception(retryable),
        wait=wait_exponential(multiplier=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )(fn)


def this_hour() -> datetime:
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def upsert_items(s: Session, rows: list[dict]) -> int:
    """Insert new items; on re-discovery refresh the title (streams get renamed mid-broadcast)."""
    rows = list({(r["source"], r["item_id"]): {"channel_id": None, "channel_title": None,
                                               "published_at": None, **r} for r in rows}.values())
    if rows:
        stmt = insert(Item).values(rows)
        s.execute(stmt.on_conflict_do_update(index_elements=["source", "item_id"],
                                             set_={"title": stmt.excluded.title}))
    return len(rows)


def upsert_signals(s: Session, rows: list[dict]) -> int:
    """captured_at is a bucket (hour/day), so a re-run in the same bucket overwrites instead of duplicating."""
    rows = list({(r["source"], r["item_id"], r["metric_name"], r["captured_at"]): r for r in rows}.values())
    if rows:
        stmt = insert(Signal).values(rows)
        s.execute(stmt.on_conflict_do_update(
            index_elements=["source", "item_id", "metric_name", "captured_at"],
            set_={"metric_value": stmt.excluded.metric_value},
        ))
    return len(rows)
