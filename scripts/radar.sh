#!/usr/bin/env bash
# Run Trend Radar locally. Usage: scripts/radar.sh <command>
#
#   up        build every image from the current code and (re)start everything
#   status    containers, last pipeline runs, current top 5
#   refresh   run the hourly cycle now: embed titles, AI topic naming (Claude, ~1-2 cents if new clusters), dbt scores
#   topics    what the AI decided for each cluster (review names, merges, noise, spam)
#   keys      which .env keys are set (shows length only, never the value)
#   test      Python tests + website typecheck, lint and build
#   logs [s]  follow logs (default: worker; or api, web, postgres)
#   open      open the site in Arc
#   down      stop everything (collected data is kept)
set -euo pipefail
cd "$(dirname "$0")/.."

SITE=http://localhost:3100
psql() { docker compose exec -T postgres psql -U trend_radar -d trend_radar "$@"; }

case "${1:-help}" in
  up)
    # Always all services: a worker image older than the database's migrations crash-loops on start.
    docker compose up -d --build
    docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    echo "Site: $SITE   API docs: http://localhost:8000/api/docs"
    ;;
  status)
    docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    psql -c "select source, job, status, started_at::timestamp(0) as started_utc, items_count,
                    left(coalesce(error, ''), 70) as error
             from connector_runs order by id desc limit 12"
    curl -sf localhost:8000/api/topics/top | python3 -c '
import json, sys
for t in json.load(sys.stdin)["topics"]:
    print("{:>2}  {:5.1f}  {}{}".format(t["rank"], t["score"], t["name"], "  (AI)" if t["origin"] == "ai" else ""))' \
      || echo "API not reachable: run scripts/radar.sh up"
    ;;
  refresh)
    docker compose exec -T worker python -c "from trend_radar.scheduler import transform_cycle; transform_cycle()"
    psql -c "select source, job, status, items_count, quota_used as tokens, left(coalesce(error, ''), 80) as error
             from connector_runs where source in ('ai', 'dbt') order by id desc limit 3"
    ;;
  topics)
    psql -c "select slug, name, status, merged_into, items_count as items, left(examples->>0, 60) as example
             from ai_topics order by status, items_count desc"
    ;;
  keys)
    for k in $(grep -oE '^[A-Z_]+=' .env.example | tr -d =); do
      v=$(grep -E "^$k=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'" || true)
      if [ -n "$v" ]; then printf '%-24s set (%d chars)\n' "$k" "${#v}"; else printf '%-24s missing\n' "$k"; fi
    done
    ;;
  test)
    uv run pytest -q
    (cd apps/web && npx tsc --noEmit && npm run lint && npm run build)
    ;;
  logs) docker compose logs -f --tail 50 "${2:-worker}" ;;
  open) open -a Arc "$SITE" ;;
  down) docker compose down ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
