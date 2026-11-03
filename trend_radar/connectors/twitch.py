"""Twitch Helix: live streams (viewers) and top clips of the last 24h (views) in the GTA 6 category."""

import time
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors.common import retry_http, this_hour, upsert_items, upsert_signals
from trend_radar.db import RawResponse, connector_run

API = "https://api.twitch.tv/helix/"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
SOURCE = "twitch"
_token: dict = {}  # app access token cache: {"value", "expires_at"}. Tokens last ~60 days.


class _Game(BaseModel):
    id: str


class GamesResponse(BaseModel):
    data: list[_Game] = []


class _Pagination(BaseModel):
    cursor: str | None = None


class _Stream(BaseModel):
    id: str
    user_id: str
    user_login: str
    user_name: str
    title: str
    viewer_count: int
    started_at: datetime


class StreamsResponse(BaseModel):
    data: list[_Stream] = []
    pagination: _Pagination = Field(default_factory=_Pagination)


class _Clip(BaseModel):
    id: str
    url: str
    broadcaster_id: str
    broadcaster_name: str
    title: str
    view_count: int
    created_at: datetime


class ClipsResponse(BaseModel):
    data: list[_Clip] = []


def client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=30)


def _headers(http: httpx.Client) -> dict:
    if not _token or _token["expires_at"] < time.time() + 60:
        # Secret goes in the POST body, not the URL, so it can't leak into error messages.
        r = http.post(TOKEN_URL, data={"client_id": config.TWITCH_CLIENT_ID,
                                       "client_secret": config.TWITCH_CLIENT_SECRET,
                                       "grant_type": "client_credentials"})
        r.raise_for_status()
        body = r.json()
        _token.update(value=body["access_token"], expires_at=time.time() + body["expires_in"])
    return {"Client-Id": config.TWITCH_CLIENT_ID, "Authorization": f"Bearer {_token['value']}"}


@retry_http
def _get(s: Session, http: httpx.Client, endpoint: str, params: dict) -> dict:
    r = http.get(endpoint, params=params, headers=_headers(http))
    if r.status_code == 401:  # token revoked or expired early: fetch a new one, try once more
        _token.clear()
        r = http.get(endpoint, params=params, headers=_headers(http))
    r.raise_for_status()
    data = r.json()
    s.add(RawResponse(source=SOURCE, endpoint=endpoint, payload=data))
    return data


def collect(http: httpx.Client | None = None) -> None:
    http = http or client()
    hour = this_hour()
    with connector_run(SOURCE, "collect") as (s, run):
        games = GamesResponse.model_validate(_get(s, http, "games", {"name": config.TWITCH_GAME_NAME}))
        if not games.data:
            raise RuntimeError(f"Twitch category {config.TWITCH_GAME_NAME!r} not found")
        game_id = games.data[0].id

        # Streams come sorted by viewers. ponytail: top TWITCH_MAX_STREAM_PAGES*100 only, raise if release week needs more
        params = {"game_id": game_id, "first": 100}
        for _ in range(config.TWITCH_MAX_STREAM_PAGES):
            page = StreamsResponse.model_validate(_get(s, http, "streams", params))
            upsert_items(s, [
                dict(source=SOURCE, item_id=st.id, item_type="stream", title=st.title,
                     url=f"https://www.twitch.tv/{st.user_login}", channel_id=st.user_id,
                     channel_title=st.user_name, published_at=st.started_at)
                for st in page.data
            ])
            upsert_signals(s, [
                dict(source=SOURCE, item_id=st.id, metric_name="viewers", metric_value=st.viewer_count,
                     captured_at=hour)
                for st in page.data
            ])
            run.items_count += len(page.data)
            s.commit()
            if not page.data or not page.pagination.cursor:
                break
            params["after"] = page.pagination.cursor

        now = datetime.now(timezone.utc)
        clips = ClipsResponse.model_validate(_get(s, http, "clips", {
            "game_id": game_id, "first": 100,
            "started_at": (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }))
        upsert_items(s, [
            dict(source=SOURCE, item_id=c.id, item_type="clip", title=c.title, url=c.url,
                 channel_id=c.broadcaster_id, channel_title=c.broadcaster_name, published_at=c.created_at)
            for c in clips.data
        ])
        upsert_signals(s, [
            dict(source=SOURCE, item_id=c.id, metric_name="views", metric_value=c.view_count, captured_at=hour)
            for c in clips.data
        ])
        run.items_count += len(clips.data)
        s.commit()
