import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors import wikipedia
from trend_radar.db import ConnectorRun, Item, Signal, engine


def fake_wikimedia():
    """Has data for Grand_Theft_Auto_VI only; any other article 404s like the real API."""
    seen = []

    def handler(req):
        seen.append(req)
        if "Grand_Theft_Auto_VI" not in req.url.path:
            return httpx.Response(404, json={"title": "Not found."})
        days = [{"timestamp": f"202611{d:02d}00", "views": 1000 * d} for d in (1, 2, 3)]
        return httpx.Response(200, json={"items": days})

    return httpx.Client(base_url=wikipedia.API, transport=httpx.MockTransport(handler),
                        headers={"User-Agent": config.WIKIMEDIA_USER_AGENT}), seen


def test_collect_stores_daily_pageviews_skips_missing_and_rerun_is_idempotent(monkeypatch):
    monkeypatch.setattr(config, "WIKIPEDIA_ARTICLES", ["Grand_Theft_Auto_VI", "Misspelled_Article"])
    http, seen = fake_wikimedia()

    wikipedia.collect(http)
    wikipedia.collect(http)

    with Session(engine) as s:
        assert s.scalars(select(Item.item_id)).all() == ["Grand_Theft_Auto_VI"]
        assert s.scalar(select(func.count()).select_from(Signal)) == 3
        assert s.scalar(select(func.max(Signal.metric_value))) == 3000
        assert {r.status for r in s.scalars(select(ConnectorRun))} == {"ok"}  # a 404 is not a failure
    assert all(r.headers["User-Agent"].startswith("TrendRadar/") for r in seen)
