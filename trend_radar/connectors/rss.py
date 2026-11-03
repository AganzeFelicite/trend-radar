"""News RSS: GTA headlines from gaming news sites. Hourly, no key. Headlines + links only, never article text.

No engagement numbers exist here, so this writes `items` only. Mentions per topic per hour are derived in dbt.
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from trend_radar import config
from trend_radar.connectors.common import retry_http, upsert_items
from trend_radar.db import RawResponse, connector_run

SOURCE = "rss"
GTA = re.compile(r"\b(" + "|".join(map(re.escape, config.RSS_KEYWORDS)) + r")\b", re.IGNORECASE)
log = logging.getLogger(__name__)


class Entry(BaseModel):
    """Contract for one RSS 2.0 <item>: a missing title, link or date fails validation."""

    id: str
    title: str
    link: str
    published: datetime


def client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": config.USER_AGENT}, timeout=30, follow_redirects=True)


def _date(rfc822: str | None) -> str | None:
    try:
        return parsedate_to_datetime(rfc822).isoformat()
    except (TypeError, ValueError):
        return None  # Entry validation then fails the feed


def parse(xml: str) -> list[dict]:
    # ponytail: stdlib parser (expat guards against entity bombs); feeds are from known publishers.
    root = ET.fromstring(xml)
    if root.tag != "rss":  # all feeds are RSS 2.0 today; anything else (Atom, an HTML error page) is drift
        raise ValueError(f"expected an RSS 2.0 feed, got <{root.tag}>")
    return [{"id": it.findtext("guid") or it.findtext("link"),
             "title": (it.findtext("title") or "").strip(),
             "link": (it.findtext("link") or "").strip(),
             "published": _date(it.findtext("pubDate"))}
            for it in root.iter("item")]


@retry_http
def _get(s: Session, http: httpx.Client, name: str, url: str) -> list[Entry]:
    r = http.get(url)
    r.raise_for_status()
    entries = parse(r.text)
    # Bronze keeps every parsed entry (GTA or not), so a changed keyword list can be replayed.
    s.add(RawResponse(source=SOURCE, endpoint=name, payload={"url": url, "entries": entries}))
    return [Entry.model_validate(e) for e in entries]


def collect(http: httpx.Client | None = None) -> None:
    http = http or client()
    with connector_run(SOURCE, "collect") as (s, run):
        failed = []
        for name, (outlet, url) in config.RSS_FEEDS.items():
            try:
                entries = _get(s, http, name, url)
            except (httpx.HTTPError, ET.ParseError, ValueError) as e:  # one broken feed must not stop the rest
                log.warning("rss: feed %s failed: %r", name, e)
                failed.append(f"{name}: {e!r}"[:300])
                continue
            hits = [e for e in entries if GTA.search(e.title)]
            upsert_items(s, [
                # guid is only unique within one outlet (GameSpot uses plain numbers), so hash it with the feed name.
                dict(source=SOURCE, item_id=hashlib.sha1(f"{name}:{e.id}".encode()).hexdigest(),
                     item_type="article", title=e.title, url=e.link,
                     channel_id=name, channel_title=outlet, published_at=e.published)
                for e in hits
            ])
            run.items_count += len(hits)
            s.commit()
        if len(failed) == len(config.RSS_FEEDS):
            raise RuntimeError("all RSS feeds failed: " + "; ".join(failed))
        if failed:
            run.status, run.error = "partial", "; ".join(failed)[:2000]
