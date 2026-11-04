# Scoring

How a topic gets its momentum score. All of it is SQL in dbt (`dbt/models/`), rebuilt every hour at :40.

```
signals ─► int_signal_deltas ─► int_item_activity ─┬─► topic_scores   (gold, topic × hour, last 7 days)
items ───► int_item_text ─────► int_item_quality ──┘    rising_items   (gold, item, last 24h)
                                topic_items ────────┘
```

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

## 5. Score and rank

```
score = attention × growth          (momentum = size × speed)
```

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

## Worked example (the `test_scores_…` test)

YouTube only. Prev 24h: preload 10k views, map 1k, other 9k → shares 50%, 5%, 45%.
Now: preload 10k, map 9k (all in the last 3h, 3 channels), other 1k → 50%, 45%, 5%.

- map: attention 0.45, growth (0.455 / 0.055 = 8.3) → capped 4, **score 1.8**, `SPIKING` (100% of the last 3h).
- preload: attention 0.50, growth 1, **score 0.5**.
- A 100k-view video with 1 comment in the map topic is dropped as `low_engagement`.

## Tuning (P7.3)

Thresholds were read off Nov 3–4 data and are guesses until release week: the spam ratio, the growth cap
and prior, the spike ratio and floor, the source weights. Change them in the seed / SQL; the next hourly
build applies them and restates the last 7 days.
