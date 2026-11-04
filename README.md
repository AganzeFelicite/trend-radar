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

Day to day, everything goes through one script (run it with no arguments for help):

```sh
scripts/radar.sh up        # build all images from the current code and start: site http://localhost:3100
scripts/radar.sh up --awake  # same, and keep the Mac from sleeping until `down` (on power, lid open)
scripts/radar.sh status    # containers, awake or not, last pipeline runs, current top 5
scripts/radar.sh backup ~/Backups/trend-radar   # pg_dump to a folder outside Docker, keeps the newest 7
scripts/radar.sh restore-test   # restore the newest backup into a throwaway DB (needs RADAR_BACKUP_DIR) or pass a file
scripts/radar.sh offtopic blue-texas on   # keep a meme/non-game topic out of the top 5 (off: undo; no args: list)
scripts/radar.sh refresh   # run the hourly cycle now (embeddings, AI naming, dbt scores)
scripts/radar.sh topics    # review the AI's topic decisions
scripts/radar.sh keys      # which .env keys are set (length only)
scripts/radar.sh test      # all tests + website build
```

Website hot-reload while editing: `cd apps/web && npm install && npm run dev` (needs the API on :8000).

Check what's been collected:

```sh
docker compose exec postgres psql -U trend_radar -c \
  "select job, status, items_count, quota_used, started_at from connector_runs order by id desc limit 10"
```

Until R2 backups exist (P2.4), back up by hand (`backup`) at least daily and check one with `restore-test`.
Deploy instructions will be added once the server exists.
