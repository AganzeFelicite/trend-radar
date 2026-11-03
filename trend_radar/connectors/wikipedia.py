"""Wikimedia Pageviews: daily views of hand-picked GTA articles. Slow signal (daily, ~1 day lag), no key needed."""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors.common import retry_http, upsert_items, upsert_signals
from trend_radar.db import RawResponse, connector_run

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
SOURCE = "wikipedia"
log = logging.getLogger(__name__)


class _Day(BaseModel):
    timestamp: str  # YYYYMMDD00
    views: int


class PageviewsResponse(BaseModel):
    items: list[_Day] = []


def client() -> httpx.Client:
    # Wikimedia blocks requests without a descriptive User-Agent.
    return httpx.Client(base_url=API, headers={"User-Agent": config.WIKIMEDIA_USER_AGENT}, timeout=30)


@retry_http
def _get(s: Session, http: httpx.Client, article: str, start: str, end: str) -> dict | None:
    r = http.get(f"{quote(article, safe='')}/daily/{start}/{end}")
    if r.status_code == 404:  # no views in range, or the article name is wrong
        return None
    r.raise_for_status()
    data = r.json()
    s.add(RawResponse(source=SOURCE, endpoint="per-article", payload=data))
    return data


def collect(http: httpx.Client | None = None) -> None:
    """Re-fetches the last WIKIPEDIA_BACKFILL_DAYS every run: cheap (1 call per article) and fills any gaps."""
    http = http or client()
    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=config.WIKIPEDIA_BACKFILL_DAYS)).strftime("%Y%m%d")
    end = (today - timedelta(days=1)).strftime("%Y%m%d")
    with connector_run(SOURCE, "collect") as (s, run):
        for article in config.WIKIPEDIA_ARTICLES:
            data = _get(s, http, article, start, end)
            if data is None:
                log.warning("wikipedia: no pageviews for %r (check the article name)", article)
                continue
            upsert_items(s, [dict(source=SOURCE, item_id=article, item_type="article",
                                  title=article.replace("_", " "),
                                  url=f"https://en.wikipedia.org/wiki/{quote(article)}")])
            upsert_signals(s, [
                dict(source=SOURCE, item_id=article, metric_name="pageviews", metric_value=d.views,
                     captured_at=datetime.strptime(d.timestamp, "%Y%m%d%H").replace(tzinfo=timezone.utc))
                for d in PageviewsResponse.model_validate(data).items
            ])
            run.items_count += 1
            s.commit()
