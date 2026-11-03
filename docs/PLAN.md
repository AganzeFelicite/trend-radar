# Plan

Source of truth for progress. Spec: [BRIEF.md](BRIEF.md).

**Definition of Done (every task):** implemented · tested (or manual test documented) · docs updated if behaviour changed · committed (`P1.5: ...`) · deployed if it affects the server · verified.

Each task lists only its specific checks plus `Verified:` (how it was checked).

Status key: `[ ]` todo · `[x]` done and verified · `[~]` blocked (reason given)

---

## Phase 0: Accounts and access (Nov 3)
Done when: launch keys are in hand and slow applications are submitted.

- [x] **P0.GH** GitHub repository
  - [x] `gh auth status` logged in (AganzeFelicite)
  - [x] Repo name confirmed: `trend-radar`
  - [x] `.gitignore` excludes `.env`
  - [x] Private repo pushed
  - [x] Visibility verified `PRIVATE`
  - Verified: `gh repo view --json name,visibility,url` → `{"name":"trend-radar","url":"https://github.com/AganzeFelicite/trend-radar","visibility":"PRIVATE"}`
- [ ] **P0.1** Accounts/keys checklist for owner; applications submitted (Reddit, Threads, Google Trends)
  - [x] List delivered (in chat, Nov 3)
  - [x] `.env.example` lists every variable
  - [ ] Each token minimum-permission
  - Verified:
- [ ] **P0.2** Local tooling: ansible, ansible-lint, docker, gh
  - [~] Versions printed: ansible core 2.20.5, docker 28.5.1, compose v2.40.3, gh 2.96.0. **ansible-lint not installed.**
  - Verified:

## Phase 1: Server up, YouTube collecting (Nov 3–4) ⚠ critical path
Done when: YouTube snapshots land hourly in Postgres on the server.

> Nov 3: no server yet → P1.4 and P1.5 built and running locally first. Local collection can start as soon as the YouTube key exists; history moves to the server later via `pg_dump`.

- [~] **P1.1** Manual one-time setup (VPS, DNS, R2 bucket + 14-day lifecycle) → `docs/MANUAL_SETUP.md`. **Blocked: no server yet.**
  - [ ] Server reachable by SSH key
  - [ ] DNS resolves
  - Verified:
- [~] **P1.2** Ansible `site.yml` (`base`, `docker`, `app`); compose: caddy, postgres, worker, placeholder api/web; `.env` from Vault. **Blocked: P1.1.**
  - [ ] Password + root SSH refused
  - [ ] `docker compose ps` healthy
  - [ ] Postgres not reachable from outside
  - [ ] Second run reports 0 changes
  - [ ] `ansible-lint` passes
  - Verified:
- [~] **P1.3** HTTPS via Caddy. **Blocked: P1.1.**
  - [ ] `https://<domain>` loads
  - [ ] `/api/health` OK
  - Verified:
- [x] **P1.4** Alembic: `raw_responses`, `items`, `signals`, `connector_runs`
  - [x] Up and down clean
  - Verified: local Postgres: `alembic upgrade head` → 4 tables; `alembic downgrade base` → only `alembic_version`; `upgrade head` again OK; `alembic check` → "No new upgrade operations detected."
- [ ] **P1.5** YouTube discovery + hourly snapshots + quota guard + `connector_runs` + pydantic + tenacity
  - [x] New videos in `items`; re-run creates no duplicates (test, mocked API)
  - [x] Hourly rows in `signals`; same-hour re-run upserts (test, mocked API)
  - [x] Simulated quota limit stops jobs (test)
  - [x] Simulated 429/5xx retries; 4xx not retried (test)
  - [x] Worker image builds, runs as non-root, migrates on start, exits if `YOUTUBE_API_KEY` missing
  - [ ] **Real run against the YouTube API**: waiting on the key
  - [ ] Sub-task: discovery via uploads playlists (1 unit/call): needs the curated GTA channel list
  - Verified: `uv run pytest` → 5 passed; `docker compose --profile worker run --rm worker` → "YOUTUBE_API_KEY is not set"

## Phase 2: More sources + safety basics (Nov 5)
Done when: three sources land in `signals`, a backup restores, and a push to `main` deploys.

- [ ] **P2.1** Twitch connector (game ID, streams, clips, token refresh)
  - [x] Streams (paged by cursor) + clips in `signals`; same-hour re-run overwrites (test, mocked API)
  - [x] Token cached and reused; 401 → refreshed once; missing category fails the run (tests)
  - [ ] **Real run**: waiting on the Twitch app (client ID + secret); confirms the category name "Grand Theft Auto VI"
  - Verified: `uv run pytest tests/test_twitch.py` → 3 passed
- [x] **P2.2** Wikipedia connector (daily, User-Agent; article→topic mapping moves to P3.2 when topics exist)
  - [x] Daily pageviews in `signals`
  - Verified: live API run Nov 3: 6/6 articles found, 30 days each (GTA VI avg 16,835/day, peak 26,444); worker in Docker ran it on start → `connector_runs` status ok, 6 items
- [ ] **P2.3** YouTube `channels.list` daily job
  - [x] Subscriber counts stored as `channel` items + `subscribers` signals; hidden counts skipped; snapshot ignores channels (test)
  - [ ] **Real run**: waiting on the YouTube key
  - Verified: `uv run pytest tests/test_youtube.py` → 6 passed
- [ ] **P2.4** Backups: nightly `pg_dump` → R2
  - [ ] File in R2
  - [ ] Restored into a test DB
  - Verified:
- [ ] **P2.5** GitHub Actions `ci.yml` + `deploy.yml`; secrets via `gh secret set`
  - [ ] Test commit deploys automatically
  - Verified:
- [ ] **P2.6** Sentry (worker, api) + Healthchecks.io heartbeat + external uptime check
  - [ ] Test error in Sentry
  - [ ] Stopping worker triggers Healthchecks alert
  - Verified:
- [x] **P2.7** `docs/CONNECTORS.md`: how to add a source
  - Verified: doc lists all 5 jobs (schedule, metrics, cost, keys) and the 10-step recipe the 3 connectors follow
- [ ] **P2.8** Overnight review
  - [ ] Snapshots every hour, quota under budget
  - Verified:

## Phase 3: The brain (Nov 6–8)
Done when: hourly top topics look sensible to a human, with no obvious duplicates or spam.

- [ ] **P3.1** SQL views: clean signals → hourly aggregates, refreshed after each cycle
  - [ ] Checks pass: no duplicates, no negative growth, no null timestamps
  - Verified:
- [ ] **P3.2** Title cleaning + keyword topics (aliases + n-grams) → `topics`, `topic_items`
  - [ ] Same topic keeps same ID hour to hour
  - Verified:
- [ ] **P3.3** Momentum scoring + flags → `topic_scores`; spam/reupload filters; `docs/SCORING.md`
  - [ ] Owner reviews top 20 and approves (or triggers embeddings upgrade)
  - Verified:

## Phase 4: The product (Nov 9–11)
Done when: a stranger on a phone understands the site, sees today's top topics, and joins the waitlist in under a minute.

- [ ] **P4.1** API: `GET /topics/top`, `GET /topics/{slug}`, `GET /videos/rising`, `POST /waitlist` (rate-limited, validated)
  - [ ] Endpoint tests pass
  - Verified:
- [ ] **P4.2** Home: top 5, "updated X minutes ago", waitlist CTA
  - Verified:
- [ ] **P4.3** Topic page: 7-day momentum chart, videos, related keywords
  - Verified:
- [ ] **P4.4** Rising videos (top 10)
  - Verified:
- [ ] **P4.5** About (unofficial, not affiliated, "Data from YouTube") + Privacy policy + Pro teaser
  - Verified:
- [ ] **P4.6** SEO, original design, mobile-first, Sentry in web
  - [ ] Every page checked at phone width
  - Verified:

## Phase 5: Delivery (Nov 12)
Done when: a test spike posts to the Telegram channel within minutes, the morning digest arrives, and the daily card is ready.

- [ ] **P5.1** Daily digest to waitlist (Resend, signed unsubscribe)
  - [ ] Received; unsubscribe works
  - Verified:
- [ ] **P5.2** Spike alerts → public Telegram channel; dedupe on `(topic_id, date)`
  - [ ] Simulated spike posts exactly once
  - Verified:
- [ ] **P5.3** Admin: 1080×1920 top-5 card (`next/og`) + on-camera script
  - [ ] Card downloaded
  - Verified:

## Phase 6: Safety net and testing (Nov 13–14)
Done when: five outside people used the site without help, all sources are healthy, and a deliberately broken job raises an alert.

- [ ] **P6.1** `/admin` (basic_auth): source health, quota, rename/merge/hide topics, waitlist CSV
  - Verified:
- [ ] **P6.2** Ops Telegram alert when a connector fails twice in a row
  - [ ] Broken job triggers it
  - Verified:
- [ ] **P6.3** Load test (`oha`/`hey`) home + API
  - [ ] Results documented
  - Verified:
- [ ] **P6.4** Fix list from review + user testing → feature freeze
  - Verified:

## Phase 7: Launch (Nov 15–19)
Done when: the site is public and stable through release day.

- [ ] **P7.1** Pre-launch check: every source, alert, digest, backup
- [ ] **P7.2** Go live; monitor errors/uptime/quota every few hours for 48h
- [ ] **P7.3** Tune scoring weights on release-week data

## Phase 8: After launch (Nov 20+)

- [ ] **P8.1** Terraform (VPS, firewall, DNS, R2; remote state) + `terraform.yml`
- [ ] **P8.2** Rebuild drill on staging, timed and documented
- [ ] **P8.3** Auth.js + Stripe + Pro + per-user alerts
- [ ] **P8.4** New sources behind flags: Bluesky, RSS, Threads, X, Reddit
- [ ] **P8.5** "Make this now" list
- [ ] **P8.6** Upgrade triggers documented (Redis, dbt, partitioning, Dagster, bigger VPS)
