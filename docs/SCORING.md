# Scoring

How a topic gets its momentum score. All of it is SQL in dbt (`dbt/models/`), rebuilt every hour at :40.

```
items ──► ai.embed ─► item_embeddings ─┐            ai.discover ─► ai_topics (registry, Claude names)
items ──► int_item_text ─► int_alias_matches ─┬─► int_topic_centroids ─► int_semantic_matches
                                              └──────────────┬────────────────────┘
signals ─► int_signal_deltas ─► int_item_activity ─┐     topic_items (alias ∪ semantic)
                  int_item_quality (spam) ─────────┴─► topic_scores (topic × hour, 7 days) · rising_items
```

Every hour at :40: `ai.embed` → `ai.discover` → `dbt build`. An AI failure is logged and never blocks the build.

## 1. Item activity (`int_item_activity`, grain: item × hour)

How much attention one item gained in one hour, in its source's own unit. Which metrics count is declared
in `seeds/metric_catalog.csv` (`activity = true`):

| Source | Activity | Kind |
|---|---|---|
| YouTube | views | cumulative → increase since previous reading |
| Bluesky | likes + reposts + replies + quotes | cumulative |
| Twitch | concurrent viewers | gauge → the reading itself |
| Wikipedia | pageviews | per day → the reading itself |
| News RSS | 1 per headline (no activity metric = mention count) | — |

- **Event time, not processing time.** An item's first reading (all views since upload) is placed at the hour
  it was published, if it is under 24h old. A video found 10 hours after upload doesn't look like a burst now.
- First reading of an item older than 24h counts 0: we can't tell when those views happened.
- Negative increases (YouTube recounts) count 0.
- **Spam filter** (`int_item_quality`), flagged items are left out entirely:
  - `low_engagement`: YouTube, 50k+ views and under 1 comment per 20k views (bought views, clip farms).
  - `repost`: the same text again from the same channel/author; the first copy counts.
  - `reupload`: a YouTube title another channel already used; the first counts. Not applied to Bluesky,
    where different people posting the same article is genuine sharing.

## 2. Per source: share of that source's GTA activity

For each topic, source and hour, three windows ending at that hour:
**now** = last 24h, **prev** = the 24h before, **burst** = last 3h (`vars` in `dbt_project.yml`).

```
share(topic, source, window) = topic activity / all GTA activity of that source in the window
```

This is "each source against its own baseline": YouTube views, Bluesky likes and headline counts become
comparable (all 0–1), overall GTA hype growing doesn't lift every topic, and collection gaps (the worker
asleep) shrink numerator and denominator together.

## 3. Per topic: weighted sum across sources

```
attention = Σ weight(s) · share_now(s)  /  Σ weight(s)        over sources with data in the window
```

Weights live in `seeds/source_weights.csv`: YouTube 0.40, Bluesky 0.20, RSS 0.15, Twitch 0.15,
Wikipedia 0 (daily and 1–2 days late, so it can't say what's rising this hour; it still feeds topic pages).
Dividing by the weights actually present means a source that's down doesn't drag every topic down.

`attention` reads as "share of the GTA conversation": 0.12 = 12%.

## 4. Growth vs the previous 24h, like-for-like

```
growth = (attention_now + 0.005) / (attention_prev + 0.005), capped to 0.25 … 4
```

- Only over sources that were **already collecting when the prev window opened** (first ok run in
  `connector_runs`), like same-store sales. Until then growth = 1, so day one isn't "everything grew 4×".
- `+ 0.005` (half a share point) stops a topic going from 0.01% to 0.1% from reading as 10× growth.

## 5. Momentum, score (0–100) and rank

```
momentum = attention × growth                        (size × speed; max 4 = 100% share × 4× growth)
score    = 100 × momentum / highest momentum of any topic in any hour of the last 7 days
```

**Score is out of 100**, Google-Trends style: 100 = the strongest topic-hour of the past week (among topic-hours
with 5+ items, so one lone article in an empty hour can't set the scale; capped at 100), 50 = half that momentum.
Scored hours start when collection started. It's relative, so it compares topics and hours with each other; the raw `momentum`, `attention`
(share of the conversation) and `growth` (× vs yesterday) stay in the table for thresholds and the topic page.
The site can show "Pre-load · 100 · 13.6% of the conversation · ×1.8 vs yesterday".

A big topic that's growing wins; a big steady topic still ranks; a small topic needs real growth to climb.
`rank` = position within that hour. The latest ranking is `where scored_at = max(scored_at)`.

## 6. Flags

| Flag | Rule | Meaning |
|---|---|---|
| `NEW` | prev window covered, no active items in it, 3+ now | a topic that wasn't there yesterday |
| `SPIKING` | burst share ≥ 2 × 24h share, burst share ≥ 1%, 3+ items from 2+ channels gained attention in the last 3h | accelerating right now (alert candidate, P5.2) |
| `CONFIRMED` | share up 20%+ vs prev on 2+ sources, with 2+ items on each | not one platform's quirk |

`CONFIRMED` and `NEW` need a covered prev window, so they appear from 48h after a source starts.
`CONFIRMED` will be rare at launch; nothing depends on it.

## 7. Items (`rising_items`, grain: item active in the last 24h)

- `per_hour` = last-24h activity / hours live in that window (growth adjusted for age).
- `per_1k_subs` (YouTube) = last-24h views per 1,000 subscribers (adjusted for channel size; channels under
  1,000 count as 1,000). 50k views on a 2k channel is a breakout; on a 5M channel it's a normal day.
- Topic attention uses raw activity (an audience is an audience). Channel size only changes this ranking.

## 8. AI topics (embeddings + Claude)

Owner's call at the first top-20 review (Nov 4): keywords alone miss too much (21% of YouTube views were in a
topic) and don't cross languages. Hybrid, so the curated topics stay exactly as they are:

1. **Embed** (`ai.embed`, local, free): one 384-dim vector per title with `paraphrase-multilingual-MiniLM-L12-v2`
   (50+ languages, ONNX via fastembed, baked into the image). "GTA 6" and filler hashtags are stripped first:
   every item says GTA 6, so it dominated the vectors. `model` holds model + cleaning version; changing either
   re-embeds everything.
2. **Match** (dbt, `int_semantic_matches`): an item no alias matched joins its nearest topic centroid if cosine
   ≥ 0.72, plus other topics within 0.03 of it (facets of one story). Curated centroids = mean of their
   alias-matched items. Calibrated Nov 4: at 0.72, ~90% agree with alias matches. `topic_items.match_type`
   says which way an item got in.
3. **Discover** (`ai.discover`): HDBSCAN over the last 48h of items no alias covers; a cluster needs 5+ items
   from 3+ channels. Each cluster is compared with the `ai_topics` registry: cosine ≥ 0.8 to a known centroid →
   same topic, same slug, **no LLM call** (stable IDs). Only unseen clusters go to Claude.
4. **Name** (Claude Haiku 5.5, one call per hour, ≤ 25 clusters, structured JSON): each cluster becomes
   `topic` (new AI topic), `duplicate` (merged into an existing slug; its centroid then pulls similar items into
   that topic), `noise` (generic chatter; attracts generic posts so they stay untopiced) or `spam` (items nearest
   to it get `ai_spam` in `int_item_quality` and leave the scores). Titles are sent as untrusted data;
   names are sanitised (letters, digits, basic punctuation, 40 chars). Tokens used → `connector_runs.quota_used`.

Owner's calls at the first AI review (Nov 4):
- Effort `medium`, and spam only when nearly every title is an ad or scam: at `low`, Haiku called a cluster of
  multilingual hype clips and the PS5 firmware story "spam", which would have removed real activity from scoring.
- A cluster named like an existing topic, or like another cluster in the same call, is merged into it (Blexas → Blue
  Texas, Chinese Jason shorts → Jason).
- **Memes that mention GTA 6 but are about something else (e.g. "Blue Texas before GTA 6") stay ranked**: they are what
  the GTA 6 conversation is about. Hide one by setting its `ai_topics.status` to `noise`.

`topics` = curated (seed) ∪ AI (`ai_topics`, status `active`). Rename, merge or hide AI topics: update the row
(P6.1 admin page later).

## Worked example (the `test_scores_…` test)

YouTube only. Prev 24h: preload 10k views, map 1k, other 9k → shares 50%, 5%, 45%.
Now: preload 10k, map 9k (all in the last 3h, 3 channels), other 1k → 50%, 45%, 5%.

- map: attention 0.45, growth (0.455 / 0.055 = 8.3) → capped 4, **momentum 1.8**, `SPIKING` (100% of the last 3h).
- preload: attention 0.50, growth 1, **momentum 0.5**. If map's 1.8 is the week's peak: map scores 100, preload 28.
- A 100k-view video with 1 comment in the map topic is dropped as `low_engagement`.

## Tuning (P7.3)

Thresholds were read off Nov 3–4 data and are guesses until release week: the spam ratio, the growth cap
and prior, the spike ratio and floor, the source weights, the semantic threshold (0.72) and tie margin (0.03). Change them in the seed / SQL; the next hourly
build applies them and restates the last 7 days.
