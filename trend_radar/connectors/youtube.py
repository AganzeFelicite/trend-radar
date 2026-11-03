"""YouTube Data API v3: discovery (search.list), hourly video snapshots (videos.list), daily channel sizes (channels.list)."""

import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors.common import retry_http, this_hour, upsert_items, upsert_signals
from trend_radar.db import ConnectorRun, Item, RawResponse, connector_run

API = "https://www.googleapis.com/youtube/v3/"
SOURCE = "youtube"
COST = {"search": 100, "videos": 1, "channels": 1}


class QuotaExhausted(Exception):
    pass


# Only the fields we use; anything else in the response is ignored.
class _SearchId(BaseModel):
    videoId: str


class _Snippet(BaseModel):
    title: str
    channelId: str
    channelTitle: str
    publishedAt: datetime


class _SearchItem(BaseModel):
    id: _SearchId
    snippet: _Snippet


class SearchResponse(BaseModel):
    items: list[_SearchItem] = []


class _Statistics(BaseModel):
    viewCount: int | None = None
    likeCount: int | None = None  # missing when the creator hides likes
    commentCount: int | None = None  # missing when comments are off


class _Video(BaseModel):
    id: str
    statistics: _Statistics


class VideosResponse(BaseModel):
    items: list[_Video] = []


class _ChannelSnippet(BaseModel):
    title: str


class _ChannelStatistics(BaseModel):
    subscriberCount: int | None = None  # missing when the channel hides it


class _Channel(BaseModel):
    id: str
    snippet: _ChannelSnippet
    statistics: _ChannelStatistics


class ChannelsResponse(BaseModel):
    items: list[_Channel] = []


def client() -> httpx.Client:
    # Key goes in a header, not the URL, so it never ends up in error messages or logs.
    return httpx.Client(base_url=API, headers={"X-Goog-Api-Key": config.YOUTUBE_API_KEY}, timeout=30)


def quota_used_today(s: Session) -> int:
    midnight = datetime.now(ZoneInfo("America/Los_Angeles")).replace(hour=0, minute=0, second=0, microsecond=0)
    return s.scalar(
        select(func.coalesce(func.sum(ConnectorRun.quota_used), 0)).where(
            ConnectorRun.source == SOURCE, ConnectorRun.started_at >= midnight
        )
    )


@retry_http
def _call(s: Session, run: ConnectorRun, http: httpx.Client, endpoint: str, params: dict) -> dict:
    """One API request. Charged before sending (failed requests cost quota too), so retries are counted."""
    cost = COST[endpoint]
    if quota_used_today(s) + cost > config.YOUTUBE_DAILY_QUOTA_STOP:
        raise QuotaExhausted(f"{quota_used_today(s)} units used today, stop at {config.YOUTUBE_DAILY_QUOTA_STOP}")
    run.quota_used += cost
    s.commit()
    r = http.get(endpoint, params=params)
    r.raise_for_status()
    data = r.json()
    s.add(RawResponse(source=SOURCE, endpoint=endpoint, payload=data))
    return data


def _recent_videos(s: Session, column):
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.YOUTUBE_SNAPSHOT_MAX_AGE_DAYS)
    return s.scalars(select(column).distinct().where(
        Item.source == SOURCE, Item.item_type == "video", Item.published_at >= cutoff
    )).all()


def discover(http: httpx.Client | None = None) -> None:
    http = http or client()
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connector_run(SOURCE, "discover") as (s, run):
        for query, order in config.YOUTUBE_SEARCHES:
            # ponytail: one page (50) per search; add pageToken paging if release-week volume needs it
            params = {"part": "snippet", "type": "video", "q": query, "order": order,
                      "publishedAfter": since, "maxResults": 50}
            data = SearchResponse.model_validate(_call(s, run, http, "search", params))
            run.items_count += upsert_items(s, [
                dict(
                    source=SOURCE,
                    item_id=v.id.videoId,
                    item_type="video",
                    title=html.unescape(v.snippet.title),  # search snippets come HTML-escaped
                    url=f"https://www.youtube.com/watch?v={v.id.videoId}",
                    channel_id=v.snippet.channelId,
                    channel_title=html.unescape(v.snippet.channelTitle),
                    published_at=v.snippet.publishedAt,
                )
                for v in data.items
            ])
            s.commit()


def snapshot(http: httpx.Client | None = None) -> None:
    http = http or client()
    hour = this_hour()
    with connector_run(SOURCE, "snapshot") as (s, run):
        ids = _recent_videos(s, Item.item_id)
        for i in range(0, len(ids), 50):
            params = {"part": "statistics", "id": ",".join(ids[i:i + 50]), "maxResults": 50}
            data = VideosResponse.model_validate(_call(s, run, http, "videos", params))
            upsert_signals(s, [
                dict(source=SOURCE, item_id=v.id, metric_name=name, metric_value=value, captured_at=hour)
                for v in data.items
                for name, value in (("views", v.statistics.viewCount), ("likes", v.statistics.likeCount),
                                    ("comments", v.statistics.commentCount))
                if value is not None
            ])
            run.items_count += len(data.items)
            s.commit()


def channels(http: httpx.Client | None = None) -> None:
    """Daily subscriber counts for channels with recent videos (scoring adjusts growth for channel size).
    Channels are stored as items (item_type='channel') so they reuse the signals table."""
    http = http or client()
    today = this_hour().replace(hour=0)
    with connector_run(SOURCE, "channels") as (s, run):
        ids = [c for c in _recent_videos(s, Item.channel_id) if c]
        for i in range(0, len(ids), 50):
            params = {"part": "snippet,statistics", "id": ",".join(ids[i:i + 50]), "maxResults": 50}
            data = ChannelsResponse.model_validate(_call(s, run, http, "channels", params))
            upsert_items(s, [
                dict(source=SOURCE, item_id=c.id, item_type="channel", title=c.snippet.title,
                     url=f"https://www.youtube.com/channel/{c.id}")
                for c in data.items
            ])
            upsert_signals(s, [
                dict(source=SOURCE, item_id=c.id, metric_name="subscribers",
                     metric_value=c.statistics.subscriberCount, captured_at=today)
                for c in data.items if c.statistics.subscriberCount is not None
            ])
            run.items_count += len(data.items)
            s.commit()
