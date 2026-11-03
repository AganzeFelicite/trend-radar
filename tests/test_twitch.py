from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar.connectors import twitch
from trend_radar.db import ConnectorRun, Item, Signal, engine

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stream(i, viewers):
    return {"id": i, "user_id": f"u{i}", "user_login": f"user{i}", "user_name": f"User{i}",
            "title": f"GTA 6 stream {i}", "viewer_count": viewers, "started_at": NOW}


def clip(i, views):
    return {"id": i, "url": f"https://clips.twitch.tv/{i}", "broadcaster_id": "b1", "broadcaster_name": "B",
            "title": f"clip {i}", "view_count": views, "created_at": NOW}


def fake_twitch(games=({"id": "493057"},), stream_pages=None, clips=(), unauthorized_once=False):
    """Serves token, games, streams (paged), clips. Records (host, path, params) of each request."""
    calls, pages = [], list(stream_pages or [{"data": [], "pagination": {}}])
    state = {"tokens": 0, "unauthorized": unauthorized_once}

    def handler(req):
        calls.append((req.url.host, req.url.path, dict(req.url.params)))
        if req.url.host == "id.twitch.tv":
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"t{state['tokens']}", "expires_in": 5_000_000})
        if state["unauthorized"]:
            state["unauthorized"] = False
            return httpx.Response(401, json={"message": "Invalid OAuth token"})
        endpoint = req.url.path.removeprefix("/helix/")
        if endpoint == "games":
            return httpx.Response(200, json={"data": list(games)})
        if endpoint == "streams":
            return httpx.Response(200, json=pages.pop(0))
        return httpx.Response(200, json={"data": list(clips), "pagination": {}})

    return httpx.Client(base_url=twitch.API, transport=httpx.MockTransport(handler)), calls, state


def count(model):
    with Session(engine) as s:
        return s.scalar(select(func.count()).select_from(model))


def test_collect_pages_streams_stores_clips_and_reuses_token():
    http, calls, state = fake_twitch(
        stream_pages=[{"data": [stream("s1", 900), stream("s2", 40)], "pagination": {"cursor": "c1"}},
                      {"data": [stream("s3", 5)], "pagination": {}}],
        clips=[clip("k1", 1200)],
    )

    twitch.collect(http)

    with Session(engine) as s:
        kinds = dict(s.execute(select(Item.item_type, func.count()).group_by(Item.item_type)).all())
        viewers = s.scalar(select(Signal.metric_value).where(Signal.item_id == "s1"))
        clip_views = s.scalar(select(Signal.metric_value).where(Signal.item_id == "k1"))
    assert kinds == {"stream": 3, "clip": 1}
    assert (viewers, clip_views) == (900, 1200)
    stream_calls = [p for host, path, p in calls if path.endswith("/streams")]
    assert stream_calls[1]["after"] == "c1"  # second page requested with the cursor
    assert stream_calls[0]["game_id"] == "493057"

    # second run: same token reused, same-hour signals overwritten not duplicated
    http2, _, state2 = fake_twitch(stream_pages=[{"data": [stream("s1", 950)], "pagination": {}}])
    twitch.collect(http2)
    assert state2["tokens"] == 0
    with Session(engine) as s:
        assert s.scalar(select(Signal.metric_value).where(Signal.item_id == "s1")) == 950
    assert count(Signal) == 4


def test_expired_token_is_refreshed_once():
    http, calls, state = fake_twitch(unauthorized_once=True)

    twitch.collect(http)

    assert state["tokens"] == 2
    assert twitch._token["value"] == "t2"


def test_missing_category_waits_instead_of_failing():
    http, _, _ = fake_twitch(games=())

    twitch.collect(http)

    with Session(engine) as s:
        run = s.scalars(select(ConnectorRun)).one()
        assert run.status == "waiting" and "does not exist yet" in run.error
