import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors import rss
from trend_radar.db import ConnectorRun, Item, RawResponse, engine

DATE = "<pubDate>Tue, 03 Nov 2026 21:22:30 +0000</pubDate>"


def feed(*titles, date=DATE):
    """A minimal RSS 2.0 feed. guids repeat across feeds on purpose (outlets number their own items)."""
    items = "".join(f"<item><title> {t} </title><link>https://news.example/{i}</link><guid>{i}</guid>{date}</item>"
                    for i, t in enumerate(titles))
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{items}</channel></rss>'


def fake_feeds(monkeypatch, bodies):
    """bodies: feed name -> XML served at https://<name>.example/feed."""
    monkeypatch.setattr(config, "RSS_FEEDS", {n: (n.title(), f"https://{n}.example/feed") for n in bodies})
    return httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, text=bodies[req.url.host.split(".")[0]])))


def test_keeps_gta_headlines_only_no_cross_feed_collisions_and_rerun_is_idempotent(monkeypatch):
    http = fake_feeds(monkeypatch, {
        "a": feed("GTA 6 file size revealed", "New Zelda trailer"),
        "b": feed("Grand Theft Auto 6 radio stations teased", "Xbox price rise"),
    })

    rss.collect(http)
    rss.collect(http)

    with Session(engine) as s:
        items = s.scalars(select(Item).order_by(Item.channel_id)).all()
        assert [(i.channel_title, i.title) for i in items] == [
            ("A", "GTA 6 file size revealed"), ("B", "Grand Theft Auto 6 radio stations teased")]  # same guid "0", 2 rows
        assert all(i.item_type == "article" and i.published_at.year == 2026 for i in items)
        raws = s.scalars(select(RawResponse)).all()
        assert len(raws) == 4 and all(len(r.payload["entries"]) == 2 for r in raws)  # bronze keeps non-GTA too
        assert {r.status for r in s.scalars(select(ConnectorRun))} == {"ok"}


def test_broken_feeds_are_isolated_and_mark_the_run_partial(monkeypatch):
    http = fake_feeds(monkeypatch, {
        "good": feed("GTA 6 preload dates confirmed"),
        "html": "<html><body>Service unavailable</body></html>",  # 200 but not RSS: contract drift
        "nodate": feed("GTA 6 map leak", date=""),                 # item without pubDate fails the contract
    })

    rss.collect(http)

    with Session(engine) as s:
        assert s.scalars(select(Item.title)).all() == ["GTA 6 preload dates confirmed"]
        run = s.scalars(select(ConnectorRun)).one()
        assert run.status == "partial" and "html:" in run.error and "nodate:" in run.error


def test_all_feeds_failing_fails_the_run(monkeypatch):
    http = fake_feeds(monkeypatch, {"html": "<html></html>"})

    with pytest.raises(RuntimeError, match="all RSS feeds failed"):
        rss.collect(http)

    with Session(engine) as s:
        assert s.scalars(select(ConnectorRun.status)).one() == "error"
        assert s.scalar(select(func.count()).select_from(Item)) == 0
