#!/usr/bin/env bash
# Run Trend Radar locally. Usage: scripts/radar.sh <command>
#
#   up [--awake]        build every image from the current code and (re)start everything;
#                       --awake also keeps the Mac from sleeping (caffeinate) until `down`
#   status              containers, awake or not, last pipeline runs, current top 5
#   backup <folder>     pg_dump (compressed) into <folder> (or $RADAR_BACKUP_DIR); keeps the newest 7
#   restore-test [file] restore a dump (default: newest backup) into a throwaway database, compare row counts
#   offtopic [slug on|off]  flag a meme/non-game topic out of the top 5 (no args: list flags)
#   cycle               collect from every source now, then score; prints each step, then status
#   refresh             run the hourly cycle now: embed titles, AI topic naming (Claude, ~1-2 cents if new clusters), dbt scores
#   brief               build today's Daily Brief now (verified data, no AI) and open it at /admin
#   drafts              AI-write today's drafts from the latest brief now (Claude, a few cents; $4/month cap)
#   studio [file]       the Video Studio brief (facts, what to research, scenes, rules) for your video AI
#   published ["title" [platform] [url]]  log a video you posted (packages avoid the last 7 titles); no args: list
#   video [file]        make a video in your Video Studio from today's package (or a pasted package/topic in file)
#   video-ui            the same as a page: paste or load the package, click Make video, watch, play (Ctrl+C stops)
#   topics              what the AI decided for each cluster (review names, merges, noise, spam)
#   keys                which .env keys are set (shows length only, never the value)
#   test                Python tests + website typecheck, lint and build
#   logs [s]            follow logs (default: worker; or api, web, postgres)
#   open                open the site in Arc
#   down                stop everything (collected data is kept) and let the Mac sleep again
set -euo pipefail
cd "$(dirname "$0")/.."

SITE=http://localhost:3100
AWAKE="caffeinate -dimsu"  # no display, idle, disk or system sleep (system: on power only); a closed lid still sleeps
psql() { docker compose exec -T postgres psql -U trend_radar -d trend_radar "$@"; }
newest_backup() { ls -1t "${RADAR_BACKUP_DIR:?pass a dump file or set RADAR_BACKUP_DIR}"/trend_radar_*.dump | head -1; }

case "${1:-help}" in
  up)
    # Always all services: a worker image older than the database's migrations crash-loops on start.
    docker compose up -d --build
    docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    if [ "${2:-}" = "--awake" ]; then
      pkill -f "$AWAKE" || true
      nohup $AWAKE >/dev/null 2>&1 &
      echo "Mac kept awake until scripts/radar.sh down (keep it on power, lid open)"
    fi
    echo "Site: $SITE   API docs: http://localhost:8000/api/docs"
    ;;
  status)
    docker compose ps --format 'table {{.Service}}\t{{.Status}}'
    pgrep -f "$AWAKE" >/dev/null && echo "Mac: kept awake" || echo "Mac: may sleep (start with: scripts/radar.sh up --awake)"
    psql -c "select source, job, status, started_at::timestamp(0) as started_utc, items_count,
                    left(coalesce(error, ''), 70) as error
             from connector_runs order by id desc limit 12"
    curl -sf localhost:8000/api/topics/top | python3 -c '
import json, sys
for t in json.load(sys.stdin)["topics"]:
    print("{:>2}  {:5.1f}  {}{}".format(t["rank"], t["score"], t["name"], "  (AI)" if t["origin"] == "ai" else ""))' \
      || echo "API not reachable: run scripts/radar.sh up"
    ;;
  cycle)
    # One full hour now, step by step: collect from every source, then embed/AI/dbt. Same jobs the scheduler runs.
    docker compose exec -T worker python -c '
import time
from trend_radar.connectors import bluesky, rss, twitch, youtube
from trend_radar.scheduler import transform_cycle
for job in (youtube.snapshot, twitch.collect, rss.collect, bluesky.collect, transform_cycle):
    name, t = job.__module__.rsplit(".", 1)[-1] + "." + job.__name__, time.monotonic()
    print("->", name, "...", flush=True)
    try:
        job()
        print("   done in {:.0f}s".format(time.monotonic() - t), flush=True)
    except Exception as e:  # recorded in connector_runs too; keep going so one source cannot block the rest
        print("   FAILED:", type(e).__name__, str(e)[:120], flush=True)
'
    "$0" status
    ;;
  refresh)
    docker compose exec -T worker python -c "from trend_radar.scheduler import transform_cycle; transform_cycle()"
    psql -c "select source, job, status, items_count, quota_used as tokens, left(coalesce(error, ''), 80) as error
             from connector_runs where source in ('ai', 'dbt') order by id desc limit 3"
    ;;
  brief)
    docker compose exec -T worker python -c "from trend_radar import brief; brief.build()"
    curl -sf localhost:8000/api/admin/brief | python3 -c '
import json, sys
r = json.load(sys.stdin); b = r["json"]
print("Daily Brief {} v{} ({})".format(r["brief_date"], r["version"], r["status"]))
for t in b["top5"]: print("  {:>2}  {:>3.0f}  {}".format(t["rank"], t["score"], t["name"]))
for n in b["notes"]: print("  ! " + n)'
    open -a Arc "$SITE/admin"
    ;;
  drafts)
    docker compose exec -T worker python -c "from trend_radar import writer; writer.write()"
    psql -c "select status, items_count as drafts, round(quota_used / 1e6, 4) as cost_usd, left(coalesce(error, ''), 80) as error
             from connector_runs where source = 'writer' order by id desc limit 1"
    open -a Arc "$SITE/admin"
    ;;
  studio)
    if [ -n "${2:-}" ]; then
      curl -sf localhost:8000/api/admin/studio-prompt -o "$2" && echo "Saved to $2"
    else
      curl -sf localhost:8000/api/admin/studio-prompt
    fi
    ;;
  published)
    if [ -z "${2:-}" ]; then
      psql -c "select published_at::timestamp(0), platform, title, url from published_videos order by published_at desc limit 10"
    else
      printf '%s\n' "insert into published_videos (title, platform, url) values (:'t', :'p', nullif(:'u', ''))" |
        psql -v t="$2" -v p="${3:-youtube}" -v u="${4:-}"
    fi
    ;;
  video)
    # Trend Radar doesn't make videos: this hands the package to your Video Studio ($STUDIO_DIR) and runs its steps.
    # $0: research and script use your Claude Code login; voice, animation and the FilmCraft edit run on this Mac.
    # Nothing is published.
    studio=${STUDIO_DIR:-$HOME/Desktop/thevault/dog-video-generate}
    if [ -n "${2:-}" ]; then body=$(jq -n --rawfile s "$2" '{input: $s}')
    else body=$(curl -sf localhost:8000/api/admin/content-package | jq '{input: tojson}'); fi
    r=$(curl -s -X POST 127.0.0.1:8400/jobs -H 'content-type: application/json' -d "$body")
    id=$(jq -r '.id // empty' <<<"$r" 2>/dev/null || true)
    [ -n "$id" ] || { echo "Studio refused the input: $r"; exit 1; }
    echo "Studio job $id ($(jq -r '"\(.input_kind), \(.target_seconds) s, \(.facts) facts"' <<<"$r"))"
    cd "$studio/api"
    export PYTHONUNBUFFERED=1
    for step in research script safety voice clip broll edit; do
      echo "== $step ($(date +%H:%M))"
      if [ "$step" = safety ]; then
        out=$(uv run python -m studio.safety "$id"); echo "$out"; [ "$out" = passed ] || exit 1
      else
        uv run python -m "studio.$step" "$id"
      fi
    done
    echo "DONE $studio/storage/jobs/$id/final.mp4"
    if [ -t 1 ]; then open "$studio/storage/jobs/$id/final.mp4"; fi
    ;;
  video-ui)
    (sleep 1; open -a Arc http://127.0.0.1:3600) &
    exec python3 scripts/video_ui.py
    ;;
  topics)
    psql -c "select slug, name, status, merged_into, items_count as items, left(examples->>0, 60) as example
             from ai_topics order by status, items_count desc"
    ;;
  keys)
    for k in $(grep -oE '^[A-Z0-9_]+=' .env.example | tr -d =); do
      v=$(grep -E "^$k=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d "\"'" || true)
      if [ -n "$v" ]; then printf '%-24s set (%d chars)\n' "$k" "${#v}"; else printf '%-24s missing\n' "$k"; fi
    done
    ;;
  test)
    uv run pytest -q
    (cd apps/web && npx tsc --noEmit && npm run lint && npm run build)
    ;;
  backup)
    dir=${2:-${RADAR_BACKUP_DIR:-}}
    [ -n "$dir" ] || { echo "usage: scripts/radar.sh backup <folder>   (or set RADAR_BACKUP_DIR)"; exit 1; }
    mkdir -p "$dir"
    f="$dir/trend_radar_$(date -u +%Y-%m-%d_%H%MZ).dump"
    # Custom format (-Fc) is compressed and restores table by table. Written to .part first: a failed dump never
    # looks like a good backup, and never pushes a good one out of the newest 7.
    docker compose exec -T postgres pg_dump -U trend_radar -d trend_radar -Fc -Z 6 > "$f.part" || { rm -f "$f.part"; exit 1; }
    mv "$f.part" "$f"
    ls -1t "$dir"/trend_radar_*.dump | tail -n +8 | while read -r old; do rm -f "$old"; done
    ls -lh "$dir"/trend_radar_*.dump
    ;;
  restore-test)
    f=${2:-$(newest_backup)}
    echo "Restoring $f into a throwaway database (restore_check)"
    psql -q -c "drop database if exists restore_check" -c "create database restore_check"
    docker compose exec -T postgres pg_restore -U trend_radar -d restore_check --no-owner --exit-on-error < "$f"
    for db in trend_radar restore_check; do  # live keeps collecting, so it may be slightly ahead of the dump
      docker compose exec -T postgres psql -U trend_radar -d "$db" -At -F ' | ' -c "select '$db', 'items ' || count(*),
        'signals ' || (select count(*) from signals), 'runs ' || (select count(*) from connector_runs),
        'topics ' || (select count(*) from analytics.topics) from items"
    done
    psql -q -c "drop database restore_check"
    echo "Restore OK"
    ;;
  offtopic)
    if [ -z "${2:-}" ]; then psql -c "select * from off_topic_flags order by flagged_at"; exit; fi
    [[ "$2" =~ ^[a-z0-9-]+$ ]] || { echo "not a topic slug: $2"; exit 1; }
    case "${3:-}" in
      on)  psql -c "insert into off_topic_flags (topic_slug) select topic_slug from analytics.topics
                    where topic_slug = '$2' on conflict do nothing" ;;
      off) psql -c "delete from off_topic_flags where topic_slug = '$2'" ;;
      *) echo "usage: scripts/radar.sh offtopic <slug> on|off"; exit 1 ;;
    esac
    echo "Re-scoring so the site shows it (about 30 s)…"
    docker compose exec -T worker python -c "from trend_radar import transform; transform.build()"
    ;;
  logs) docker compose logs -f --tail 50 "${2:-worker}" ;;
  open) open -a Arc "$SITE" ;;
  down) docker compose down; pkill -f "$AWAKE" || true ;;
  *) sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
