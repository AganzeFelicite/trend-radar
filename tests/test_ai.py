"""AI layer with a fake encoder and a fake namer: no model download, no API calls."""

from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from trend_radar import ai
from trend_radar.connectors.common import upsert_items
from trend_radar.db import AiTopic, ItemEmbedding, engine


def vec(axis, jitter=0.0, seed=0):
    v = np.zeros(384)
    v[axis] = 1
    v[383] = jitter * np.random.default_rng(seed).random()  # small spread inside a cluster
    return (v / np.linalg.norm(v)).tolist()


def add_items(rows, embeddings=None):
    """rows: (item_id, channel, title); embeddings: item_id -> vector, written directly (bypasses the encoder)."""
    with Session(engine) as s:
        upsert_items(s, [dict(source="youtube", item_id=i, item_type="video", title=t, url=f"https://y/{i}",
                              channel_id=c, published_at=datetime.now(timezone.utc)) for i, c, t in rows])
        s.add_all(ItemEmbedding(source="youtube", item_id=i, model=ai.EMBED_VERSION, embedding=v)
                  for i, v in (embeddings or {}).items())
        s.commit()


def test_embed_strips_the_gta_name_writes_once_and_redoes_old_versions():
    add_items([("a", "c1", "GTA 6 map #shorts"), ("b", "c2", "GTA V vs GTA VI")])
    seen = []
    fake = lambda texts: seen.extend(texts) or [vec(1)] * len(texts)  # noqa: E731

    ai.embed(encoder=fake)
    ai.embed(encoder=fake)  # nothing new: no second encode
    with Session(engine) as s:
        s.execute(text("update item_embeddings set model = 'old' where item_id = 'a'"))
        s.commit()
    ai.embed(encoder=fake)  # model/cleaning version changed: re-embed that one

    assert seen == ["map", "GTA5 vs", "map"]
    with Session(engine) as s:
        assert set(s.scalars(select(ItemEmbedding.model))) == {ai.EMBED_VERSION}


def test_discover_registers_named_clusters_keeps_ids_stable_and_rejects_invented_merges():
    rows, emb = [], {}
    for axis, word in ((10, "wanted"), (20, "detox"), (30, "pets")):
        for k in range(6):  # 6 items from 6 channels per cluster
            rows.append((f"{word}{k}", f"{word}-ch{k}", f"{word} story {k}"))
            emb[f"{word}{k}"] = vec(axis, jitter=0.05, seed=k)
    add_items(rows, emb)
    with engine.begin() as c:  # what the dbt build leaves behind
        c.execute(text("create schema analytics"))
        c.execute(text("create table analytics.int_alias_matches (source text, item_id text)"))
        c.execute(text("create table analytics.topics as select 'map'::text as topic_slug, 'Map'::text as topic_name"))

    calls = []

    def namer(clusters, topics):
        calls.append(len(clusters))
        assert topics == {"map": "Map"}
        by_word = {c[0].split()[0]: i for i, c in enumerate(clusters)}
        return [ai.Decision(cluster=by_word["wanted"], kind="topic", name="Wanted System 🚨", merge_into=None),
                ai.Decision(cluster=by_word["detox"], kind="duplicate", name="x", merge_into="map"),
                ai.Decision(cluster=by_word["pets"], kind="duplicate", name="Pets Poll", merge_into="invented")], 123

    ai.discover(namer=namer)
    ai.discover(namer=namer)  # same clusters again: matched to the registry, no LLM call

    with Session(engine) as s:
        reg = {t.slug: (t.name, t.status, t.merged_into) for t in s.scalars(select(AiTopic))}
    assert calls == [3]
    assert reg["wanted-system"] == ("Wanted System", "active", None)  # emoji stripped from the name
    assert ("x", "merged", "map") in reg.values()
    assert reg["pets-poll"] == ("Pets Poll", "active", None)  # merge target doesn't exist: kept as a topic
