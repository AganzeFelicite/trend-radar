import json

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors import bluesky
from trend_radar.db import ConnectorRun, Item, Signal, engine


def post(i, likes=5):
    return {"uri": f"at://did:plc:abc{i}/app.bsky.feed.post/3k{i}", "cid": "bafy",
            "author": {"did": f"did:plc:abc{i}", "handle": f"user{i}.bsky.social"},
            "record": {"text": f"GTA 6 map looks huge #{i}", "createdAt": "2026-11-04T10:00:00Z"},
            "indexedAt": "2026-11-04T10:00:01Z", "likeCount": likes, "repostCount": 1, "replyCount": 2}


def fake_bluesky(monkeypatch, pages, login_status=200):
    """pages: served in order per search via the cursor. Records every request."""
    monkeypatch.setattr(config, "BLUESKY_HANDLE", "me.bsky.social")
    monkeypatch.setattr(config, "BLUESKY_APP_PASSWORD", "app-pass-1234")
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.path.endswith("createSession"):
            if login_status != 200:
                return httpx.Response(login_status, json={"error": "AuthenticationRequired"})
            return httpx.Response(200, json={"accessJwt": "jwt-1", "refreshJwt": "r", "did": "did:plc:me"})
        assert req.headers["Authorization"] == "Bearer jwt-1"
        i = int(req.url.params.get("cursor", 0))
        return httpx.Response(200, json={"posts": pages[i], "cursor": str(i + 1) if i + 1 < len(pages) else None})

    return httpx.Client(base_url=config.BLUESKY_API, transport=httpx.MockTransport(handler)), seen


def test_logs_in_once_per_run_pages_both_searches_and_rerun_is_idempotent(monkeypatch):
    http, seen = fake_bluesky(monkeypatch, [[post(1), post(2)], [post(3)]])

    bluesky.collect(http)
    bluesky.collect(http)

    logins = [r for r in seen if r.url.path.endswith("createSession")]
    assert len(logins) == 2  # one per run
    assert json.loads(logins[0].content)["password"] == "app-pass-1234"
    assert all("app-pass" not in str(r.url) for r in seen)  # secret never in a URL
    searches = [r for r in seen if "searchPosts" in r.url.path]
    assert {r.url.params["sort"] for r in searches} == {"latest", "top"} and len(searches) == 8  # 2 sorts x 2 pages x 2 runs
    with Session(engine) as s:
        items = s.scalars(select(Item)).all()
        assert len(items) == 3  # same posts from "latest" and "top" upsert into one row each
        assert items[0].url == "https://bsky.app/profile/user1.bsky.social/post/3k1"
        assert s.scalar(select(func.count()).select_from(Signal)) == 12  # 3 posts x 4 metrics, same hour
        assert {r.status for r in s.scalars(select(ConnectorRun))} == {"ok"}


def test_wrong_app_password_fails_fast_without_searching(monkeypatch):
    http, seen = fake_bluesky(monkeypatch, [[post(1)]], login_status=401)

    with pytest.raises(httpx.HTTPStatusError):
        bluesky.collect(http)

    assert len(seen) == 1  # no retries on 401, no searches
    with Session(engine) as s:
        assert s.scalars(select(ConnectorRun.status)).one() == "error"


def test_schema_change_fails_the_run(monkeypatch):
    broken = post(1)
    del broken["author"]
    http, _ = fake_bluesky(monkeypatch, [[broken]])

    with pytest.raises(ValidationError):
        bluesky.collect(http)

    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Item)) == 0
