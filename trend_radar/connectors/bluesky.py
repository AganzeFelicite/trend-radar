"""Bluesky: posts mentioning GTA 6 over the last 24h, with like/repost/reply/quote counts. Hourly, app password."""

import hashlib
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors.common import retry_http, this_hour, upsert_items, upsert_signals
from trend_radar.db import RawResponse, connector_run

SOURCE = "bluesky"
METRICS = {"likes": "likeCount", "reposts": "repostCount", "replies": "replyCount", "quotes": "quoteCount"}


class _Author(BaseModel):
    did: str
    handle: str


class _Record(BaseModel):
    text: str = ""


class _Post(BaseModel):
    uri: str  # at://did:plc:…/app.bsky.feed.post/<rkey>
    author: _Author
    record: _Record
    indexedAt: datetime  # server time; createdAt is set by the client and can be anything
    likeCount: int = 0
    repostCount: int = 0
    replyCount: int = 0
    quoteCount: int = 0


class SearchResponse(BaseModel):
    posts: list[_Post] = []
    cursor: str | None = None


def client() -> httpx.Client:
    return httpx.Client(base_url=config.BLUESKY_API, headers={"User-Agent": config.USER_AGENT}, timeout=30)


@retry_http
def _login(http: httpx.Client) -> dict:
    # App password in the JSON body, never the URL. One session per run: 24/day vs the 300/day limit.
    r = http.post("com.atproto.server.createSession",
                  json={"identifier": config.BLUESKY_HANDLE, "password": config.BLUESKY_APP_PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['accessJwt']}"}


@retry_http
def _get(s: Session, http: httpx.Client, headers: dict, params: dict) -> dict:
    r = http.get("app.bsky.feed.searchPosts", params=params, headers=headers)
    r.raise_for_status()
    data = r.json()
    s.add(RawResponse(source=SOURCE, endpoint="searchPosts", payload=data))
    return data


def _item_id(uri: str) -> str:
    return uri if len(uri) <= 128 else hashlib.sha1(uri.encode()).hexdigest()  # rare long did:web URIs


def collect(http: httpx.Client | None = None) -> None:
    http = http or client()
    hour = this_hour()
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connector_run(SOURCE, "collect") as (s, run):
        headers = _login(http)
        for query, sort in config.BLUESKY_SEARCHES:
            params = {"q": query, "sort": sort, "since": since, "limit": 100}
            for _ in range(config.BLUESKY_MAX_PAGES):
                page = SearchResponse.model_validate(_get(s, http, headers, params))
                upsert_items(s, [
                    dict(source=SOURCE, item_id=_item_id(p.uri), item_type="post", title=p.record.text,
                         url=f"https://bsky.app/profile/{p.author.handle}/post/{p.uri.rsplit('/', 1)[1]}",
                         channel_id=p.author.did, channel_title=p.author.handle, published_at=p.indexedAt)
                    for p in page.posts
                ])
                upsert_signals(s, [
                    dict(source=SOURCE, item_id=_item_id(p.uri), metric_name=name,
                         metric_value=getattr(p, field), captured_at=hour)
                    for p in page.posts for name, field in METRICS.items()
                ])
                run.items_count += len(page.posts)
                s.commit()
                if not page.posts or not page.cursor:
                    break
                params["cursor"] = page.cursor
