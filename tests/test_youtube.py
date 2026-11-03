from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors import youtube
from trend_radar.db import ConnectorRun, Item, RawResponse, Signal, engine

RECENT = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_body(ids, channel="UC1"):
    return {"items": [
        {"id": {"kind": "youtube#video", "videoId": i},
         "snippet": {"title": f"GTA 6 Lucia &amp; Jason {i}", "channelId": channel, "channelTitle": "Chan",
                     "publishedAt": RECENT}}
        for i in ids
    ]}


def videos_body(ids):
    return {"items": [{"id": i, "statistics": {"viewCount": "1000", "likeCount": "50"}} for i in ids]}


def fake_api(responses):
    """httpx client that serves `responses` (status, json) in order and records each request path."""
    calls = []

    def handler(request):
        calls.append(request.url.path)
        status, body = responses.pop(0) if len(responses) > 1 else responses[0]
        return httpx.Response(status, json=body)

    return httpx.Client(base_url=youtube.API, transport=httpx.MockTransport(handler)), calls


def count(model):
    with Session(engine) as s:
        return s.scalar(select(func.count()).select_from(model))


def last_run():
    with Session(engine) as s:
        return s.scalars(select(ConnectorRun).order_by(ConnectorRun.id.desc())).first()


def test_discover_inserts_items_and_rerun_creates_no_duplicates(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_SEARCHES", [("GTA 6", "date"), ("GTA 6", "viewCount")])
    http, calls = fake_api([(200, search_body(["a", "b"])), (200, search_body(["b", "c"]))])

    youtube.discover(http)
    youtube.discover(http)

    assert count(Item) == 3
    with Session(engine) as s:
        assert s.get(Item, ("youtube", "a")).title == "GTA 6 Lucia & Jason a"  # HTML unescaped
    assert count(RawResponse) == 4
    run = last_run()
    assert (run.status, run.quota_used) == ("ok", 200)


def test_snapshot_writes_hourly_signals_and_same_hour_rerun_upserts(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_SEARCHES", [("GTA 6", "date")])
    youtube.discover(fake_api([(200, search_body(["a", "b"]))])[0])
    http, calls = fake_api([(200, videos_body(["a", "b"]))])

    youtube.snapshot(http)
    youtube.snapshot(http)

    assert count(Signal) == 4  # 2 videos x (views, likes); commentCount missing -> skipped
    with Session(engine) as s:
        views = s.scalar(select(Signal.metric_value).where(Signal.item_id == "a", Signal.metric_name == "views"))
    assert views == 1000
    assert calls == ["/youtube/v3/videos", "/youtube/v3/videos"]
    assert last_run().quota_used == 1


def test_quota_guard_stops_job_before_exceeding_limit(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_SEARCHES", [("GTA 6", "date"), ("GTA 6", "viewCount")])
    monkeypatch.setattr(config, "YOUTUBE_DAILY_QUOTA_STOP", 150)
    http, calls = fake_api([(200, search_body(["a"]))])

    with pytest.raises(youtube.QuotaExhausted):
        youtube.discover(http)

    assert len(calls) == 1  # second search (another 100 units) never sent
    run = last_run()
    assert (run.status, run.quota_used) == ("error", 100)
    assert "QuotaExhausted" in run.error


def test_429_and_5xx_are_retried_then_succeed(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_SEARCHES", [("GTA 6", "date")])
    http, calls = fake_api([(429, {}), (503, {}), (200, search_body(["a"]))])

    youtube.discover(http)

    assert len(calls) == 3
    assert count(Item) == 1
    assert last_run().quota_used == 300  # every attempt is charged


def test_4xx_is_not_retried(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_SEARCHES", [("GTA 6", "date")])
    http, calls = fake_api([(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})])

    with pytest.raises(httpx.HTTPStatusError):
        youtube.discover(http)

    assert len(calls) == 1
    assert last_run().status == "error"


def test_channels_stores_subscribers_and_skips_hidden_counts(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_SEARCHES", [("GTA 6", "date"), ("GTA 6", "viewCount")])
    youtube.discover(fake_api([(200, search_body(["a"], "UC1")), (200, search_body(["b"], "UC2"))])[0])
    http, calls = fake_api([(200, {"items": [
        {"id": "UC1", "snippet": {"title": "Big Channel"}, "statistics": {"subscriberCount": "5000"}},
        {"id": "UC2", "snippet": {"title": "Shy Channel"}, "statistics": {"hiddenSubscriberCount": True}},
    ]})])

    youtube.channels(http)

    with Session(engine) as s:
        assert s.get(Item, ("youtube", "UC1")).item_type == "channel"
        subs = s.scalars(select(Signal).where(Signal.metric_name == "subscribers")).all()
    assert [(x.item_id, x.metric_value) for x in subs] == [("UC1", 5000)]

    # the hourly video snapshot must not send channel ids to videos.list
    http, calls = fake_api([(200, videos_body([]))])
    requested = []
    http.event_hooks["request"] = [lambda r: requested.append(r.url.params["id"])]
    youtube.snapshot(http)
    assert sorted(requested[0].split(",")) == ["a", "b"]
