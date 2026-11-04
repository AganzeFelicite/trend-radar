# Connectors

Each connector lives in `trend_radar/connectors/<source>.py`, fetches from **one official API**, and writes to the same tables:
`items` (one row per video / stream / clip / article / channel) and `signals` (one metric reading per item per time bucket).

## Current connectors

| Source | Job | Schedule (UTC) | Metrics | Cost / limits | Needs |
|---|---|---|---|---|---|
| YouTube | `youtube.discover` | every hour | new `video` items | 2 × 100 units/hour = 4,800/day | `YOUTUBE_API_KEY` |
| YouTube | `youtube.snapshot` | hourly at :05 | `views`, `likes`, `comments` for videos < 7 days old | 1 unit / 50 videos | `YOUTUBE_API_KEY` |
| YouTube | `youtube.channels` | daily 06:15 | `subscribers` (channels stored as `channel` items) | 1 unit / 50 channels | `YOUTUBE_API_KEY` |
| Twitch | `twitch.collect` | hourly at :10 (+ on start) | `viewers` per `stream`, `views` per `clip` (top 100 clips of last 24h) | ~13 points of 800/min | `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` |

Twitch had no "Grand Theft Auto VI" category on Nov 3, 2026. Until it exists, `twitch.collect` records status `waiting` (not `error`) and checks again every hour.
| Bluesky | `bluesky.collect` | hourly at :25 (+ on start) | `likes`, `reposts`, `replies`, `quotes` per `post` (last 24h, "latest" + "top"); link-card title joined to the text; adult-labelled posts skipped; `partial` if "latest" reaches back < 2h | 1 login + ≤10 searches; login limit 300/day | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` |
| News RSS | `rss.collect` | hourly at :20 (+ on start) | `article` items only (no metrics): GTA headlines from 8 outlets; mentions/hour derived in dbt | 8 requests | nothing |
| Wikipedia | `wikipedia.collect` | every 6h (+ on start) | daily `pageviews` per `article`, re-fetches last 30 days | 1 call per article | nothing (descriptive User-Agent) |

Housekeeping: `maintenance.purge_raw` deletes `raw_responses` older than 30 days, daily at 03:30 UTC.

The YouTube quota guard stops all YouTube jobs at 9,000 units/day (summed from `connector_runs`, reset at midnight Pacific).
A connector whose keys are missing is skipped at startup with a warning. The worker still runs the others.

## Adding a source

Step-by-step guide with copy-paste templates and the source catalog: [adding-sources.html](adding-sources.html).

1. **Module** `trend_radar/connectors/<source>.py` with `SOURCE = "<source>"`.
2. **Response models:** pydantic classes with only the fields you use. Validation fails loudly if the API changes shape.
3. **One `_get()` per connector**, decorated with `@retry_http` (from `common.py`: retries 429/5xx/network errors with backoff, never other 4xx). It must save the body: `s.add(RawResponse(source=SOURCE, endpoint=..., payload=data))`.
4. **Secrets never in URLs.** Put them in headers or POST bodies. URLs end up in logs and error messages (httpx logs every request URL).
5. **A job function** (`collect()` or similar) that takes an optional `httpx.Client` (tests inject a fake) and wraps its work in `with connector_run(SOURCE, "<job>") as (s, run):`, which records status, errors and counts. Statuses: `running` → `ok` / `partial` / `error` / `waiting` (nothing to fetch yet); `aborted` = the worker restarted mid-run (set on the next worker start).
6. **Write with `upsert_items()` / `upsert_signals()`** from `common.py`. Use a **bucketed** `captured_at` (`this_hour()` or a date) so re-runs overwrite instead of duplicating. `s.commit()` after each page.
7. **Config:** keys from env in `config.py`; add them to `.env.example` and the `worker` environment in `docker-compose.yml`.
8. **Schedule** in `scheduler.py`, gated on its keys being present.
9. **Test** in `tests/test_<source>.py` with `httpx.MockTransport`: data lands, a re-run doesn't duplicate, and the source's failure mode is handled (bad token, missing data, quota).
10. **Terms:** official API only, respect its rate limits and storage rules, never resell raw data.
11. **dbt:** add every new metric to `dbt/seeds/metric_catalog.csv` (the build fails otherwise, on purpose; `activity=true` for the metric that measures attention), a row in `dbt/seeds/source_weights.csv` (tested too), and a freshness entry in `dbt/models/staging/_sources.yml`. Scoring: `docs/SCORING.md`. Transform runs hourly at :40 (`transform.build`).
