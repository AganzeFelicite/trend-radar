# Trend Radar

Shows creators which GTA 6 topics are rising right now, ranked by momentum across YouTube, Twitch and Wikipedia.

Unofficial, fan-made tool, not affiliated with Rockstar Games or Take-Two Interactive.

- Brief: [docs/BRIEF.md](docs/BRIEF.md)
- Plan and progress: [docs/PLAN.md](docs/PLAN.md)
- Data architecture and status: [docs/architecture.html](docs/architecture.html)

## Local dev

Needs Docker and [uv](https://docs.astral.sh/uv/).

```sh
docker compose up -d postgres     # Postgres on 127.0.0.1:5432
uv sync                           # Python 3.12 venv in .venv
uv run alembic upgrade head       # create tables
uv run pytest                     # tests use a separate trend_radar_test database
```

Collect real data locally (keys go in `.env`, which is gitignored; see `.env.example`):

```sh
docker compose up -d --build       # runs every connector that has its keys; Wikipedia needs none
docker compose logs -f worker
```

Transform layer (dbt; also runs hourly in the worker):

```sh
cd dbt && uv run dbt build --profiles-dir . && uv run dbt source freshness --profiles-dir .
```

Website + API (Phase 4):

```sh
docker compose up -d --build api web   # site on http://localhost:3100, API on http://localhost:8000/api/docs
cd apps/web && npm install && npm run dev   # or: hot-reload dev server (needs the API on :8000)
```

Check what's been collected:

```sh
docker compose exec postgres psql -U trend_radar -c \
  "select job, status, items_count, quota_used, started_at from connector_runs order by id desc limit 10"
```

Deploy and restore instructions will be added once the server exists.
