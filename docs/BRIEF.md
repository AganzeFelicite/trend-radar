# Build Prompt: GTA 6 Trend Radar (v2, scoped for launch)

You are my coding agent. We are building **GTA 6 Trend Radar**: a website that shows creators, every day, which GTA 6 topics are exploding right now, so they know what videos to make next.

I am a software engineer (Python, React/Next.js, PostgreSQL, Docker on a VPS). I will review your work. Explain decisions briefly as you go, and ask me before anything that costs money, deletes data, or touches production.

---

## 0. How you work

Before writing any code, create `docs/PLAN.md` with every phase and task below as checkboxes. It is the single source of truth for progress.

**Definition of Done (applies to every task; written once at the top of `docs/PLAN.md`, not copied per task):**
implemented · tested (or manual test documented) · docs updated if behaviour changed · committed (message references the task, e.g. `P1.5: YouTube snapshot job`) · deployed if it affects the server · verified.

Each task in `docs/PLAN.md` keeps only its **task-specific checks** plus one line: `Verified: <command / URL / query / screenshot>`.

Rules:
- One task at a time, in order. Don't start the next phase until the current phase's "Phase done when" is met. **Exception:** once data collection is running (P1.5), it never waits on anything else.
- Never tick a check without actually checking it. If it can't be verified yet, leave it unchecked and say why.
- End of each phase: short summary to me (done, verified, blocked, next), **and a report at `docs/reports/phase-N.html`**: what we did, how far we are (tasks done vs total, days left), **why** each notable decision was made, how things were verified, what's blocked, and what's next. Self-contained HTML (no external assets), readable on a phone, light + dark mode. Open it in the browser when done.
- A task bigger than expected gets split into sub-tasks in `docs/PLAN.md`.

---

## 1. GitHub repository setup (do this first, using my GitHub CLI)

1. Run `gh auth status`. If not logged in, stop and ask me to run `gh auth login`. Never ask for or print my token.
2. Ask me to confirm the repository name (default: `trend-radar`).
3. `git init`, default branch `main`.
4. `.gitignore` covering Python, Node/Next.js, `.env*` (except `.env.example`), virtualenvs, build output, OS files. **`.env` must never be committed.**
5. Minimal `README.md`, `docs/PLAN.md`, and this brief as `docs/BRIEF.md`.
6. First commit.
7. `gh repo create <name> --private --source=. --remote=origin --push`
8. Verify with `gh repo view --json name,visibility,url` that visibility is `PRIVATE`; show me the result.

### P0.GH checks
- [ ] `gh auth status` logged in  - [ ] Repo name confirmed  - [ ] `.gitignore` excludes `.env`  - [ ] Private repo pushed  - [ ] Visibility verified `PRIVATE`

---

## 2. Context and deadline

- GTA 6 releases **November 19, 2026**. Target: public version by **November 15–17, 2026**.
- **Data history is the one thing we can't recreate later.** YouTube collection must be running on the server by end of Nov 4. Everything else can slip; collection can't.
- If time runs short, cut scope inside a phase rather than moving launch.

## 3. Product in one sentence

Every hour we collect new GTA 6 videos, clips and streams (plus daily Wikipedia pageviews) from official APIs, measure how fast they grow, group them into topics, and rank topics by momentum. Free users see today's top 5 rising topics; Pro (after launch) gets everything plus alerts.

---

## 4. Tech stack (launch)

- **Hosting:** one VPS running **Docker Compose**. Services: `caddy`, `web` (Next.js + TypeScript + Tailwind), `api` (FastAPI, Python 3.12), `worker` (Python 3.12), `postgres` (`pgvector/pgvector` image).
- **Reverse proxy:** Caddy, automatic HTTPS; `/` → `web`, `/api` → `api`, `/admin` protected with Caddy `basic_auth`.
- **Backend:** FastAPI; SQLAlchemy 2 + Alembic.
- **Worker:** one Python process, APScheduler (`max_instances=1` per job = job lock). `httpx` + `tenacity` + `pydantic` for connectors.
- **Database:** PostgreSQL. No partitioning at launch; index `signals(item_id, captured_at)`. Raw API responses stored as `jsonb` in `raw_responses`, deleted after 30 days.
- **Transformations:** dbt Core (dbt-postgres) for silver → gold: sources with freshness checks, staging / intermediate / mart models, dbt tests; `dbt build` run by the worker after each ingestion cycle. Keyword topics are plain SQL in dbt too (aliases + stopwords as seeds). *(Changed Nov 4: owner chose dbt over plain SQL views; topics English-only for phrase discovery, all languages for alias matching.)*
- **Caching:** Next.js `revalidate` (data changes hourly). No Redis.
- **Quota counting / alert dedupe:** Postgres (`connector_runs` sums; unique constraints).
- **Email:** Resend HTTP API, sent from the worker, HTML via stdlib `string.Template`; HMAC-signed unsubscribe links.
- **Alerts:** one public Telegram channel (broadcast), plus a private chat for ops alerts to me.
- **Backups:** nightly `pg_dump` → Cloudflare R2 (`boto3`), 14-day retention via R2 lifecycle rule.
- **Monitoring:** Sentry (web, api, worker). External uptime check on `/api/health` (UptimeRobot or Better Stack free tier). Healthchecks.io heartbeat pinged by the worker every cycle (catches a dead worker).
- **CI/CD:** GitHub Actions: lint → build images → push to GHCR → `ansible-playbook site.yml --tags app` against the server. **This is the only deploy path.**
- **Security:** non-root containers; secrets only in Ansible Vault / GitHub secrets; UFW allows only 22/80/443; Postgres never exposed publicly.

### Infrastructure (launch version)

- **One-time manual setup, documented:** VPS, Cloudflare DNS records, R2 bucket + lifecycle rule are created by hand once (I do it, you give me exact steps). Every step goes in `docs/MANUAL_SETUP.md`. Terraform replaces this after launch (P8.1).
- **Ansible — one playbook, `infra/ansible/site.yml`**, tagged sections:
  - `base`: packages, timezone, unattended security upgrades, fail2ban, deploy user, SSH keys only, root + password login off, UFW 22/80/443
  - `docker`: Docker Engine + Compose plugin from the official repo
  - `app`: directories, `docker-compose.yml`, `Caddyfile`, `.env` templated from Vault, GHCR login, `docker compose pull && up -d`
  - `backups`: nightly `pg_dump` → R2 cron
  - Inventory: `infra/ansible/inventory.ini` with the server IP (an IP is not a secret).
  - Idempotent: second run reports 0 changes.
- **Source of truth:** `docker-compose.yml` lives only at the repo root (Ansible copies it); `Caddyfile` only in `infra/ansible/templates/`. No copies elsewhere.
- **Secrets:** Ansible Vault for all `.env` values (including a GHCR `read:packages` token so the server can pull private images). GitHub secrets, set with `gh secret set`, values entered by me interactively, never echoed: `ANSIBLE_VAULT_PASSWORD`, `DEPLOY_SSH_KEY`, `DEPLOY_HOST`.

### Repository layout
```
trend-radar/
├── trend_radar/         one Python package + one image; worker and api share the models
│   ├── db.py            models + connector_run logging
│   ├── connectors/      youtube.py, twitch.py, wikipedia.py
│   ├── scoring/         topics, momentum
│   ├── alerts/          spike detection, email, Telegram
│   ├── api.py           FastAPI app (same image, different command)
│   └── scheduler.py     APScheduler jobs
├── migrations/          Alembic
├── tests/
├── docker-compose.yml   the only compose file; Ansible copies it to the server
├── Dockerfile           Python image (worker + api)
├── apps/web/            Next.js site + admin UI
├── infra/ansible/       site.yml, inventory.ini, templates/ (Caddyfile, .env), group_vars/ (vault)
├── docs/                PLAN.md, BRIEF.md, MANUAL_SETUP.md, CONNECTORS.md, SCORING.md
└── .github/workflows/   ci.yml (lint + test), deploy.yml
```

---

## 5. Data sources

Official APIs only. Never scrape, never use third-party scraping services.

**Launch:**
1. **YouTube Data API v3** — MAKE.
   - **Quota budget (10,000 units/day; no increase possible before launch, since it needs a weeks-long audit):**
     - Discovery: `search.list` (100 units) **≤ 60 calls/day** = 6,000. Plus `playlistItems.list` (1 unit) on the uploads playlists of a curated list of GTA channels in config, which is cheap discovery.
     - Snapshots: `videos.list` (1 unit / 50 IDs), videos < 7 days old, hourly. ~2,000 videos ≈ 960 units/day.
     - Channel sizes: `channels.list` (1 unit / 50 IDs), daily, ≈ 50 units/day.
     - Guard: worker stops YouTube jobs at **9,000 units** used (counted from `connector_runs`, reset at midnight Pacific).
   - Terms: "Data from YouTube" attribution + link back; refresh or delete stored YouTube API data within 30 days; check the Developer Policies on labelling derived metrics (our momentum score) before launch.
2. **Twitch Helix** — WATCH. Streams (title, viewers) and top clips for the GTA 6 category; automatic app-token refresh.
3. **Wikimedia Pageviews API** — WATCH. **Daily** granularity only, lags ~1 day, so it is a slow signal. Send a descriptive `User-Agent` per Wikimedia policy. Articles are mapped to topics **by hand in config**, not clustered.

**After launch (feature flags, default OFF):** Bluesky Jetstream, gaming news RSS (headline/link/time only), Threads keyword search, X pay-per-use (hard monthly cap), Reddit (after approval), Google Trends alpha (if granted). No TikTok, Facebook or Instagram.

---

## 6. Architecture

- **Connectors:** one module per source; own schedule, quota budget, tenacity backoff, idempotent upserts.
- **Raw layer:** every API response → `raw_responses` (`source, fetched_at, payload jsonb`). Re-processable without re-fetching. 30-day cleanup job.
- **Signals:** one table: `source, item_id, item_type, title, url, channel, published_at, metric_name, metric_value, captured_at`.
- **Topics (v1, keyword-based):** curated alias list in config (e.g. `lucia`, `jason`, `vice city`, `trailer 3`, `price`, `pc release`, `leak`) + n-gram counting over cleaned titles to surface new phrases. Topic ID = slug, so IDs are stable by construction.
  - **Upgrade path (only if my top-20 review shows keyword topics miss or duplicate too much):** MiniLM embeddings (CPU-only torch wheel) in pgvector, HDBSCAN, and stable IDs by matching each new cluster centroid to existing topics (cosine ≥ 0.8 → reuse ID, else new topic).
  - *(Triggered Nov 4 by owner at the top-20 review: "we need some sort of AI". Built hybrid: curated aliases stay; multilingual MiniLM embeddings via fastembed/ONNX (no torch) in pgvector; items with no alias join the nearest topic centroid in dbt; HDBSCAN finds new clusters; Claude Haiku 5.5 names them, merges duplicates, flags spam (~$2–6/month, owner approved). Score shown 0–100, 100 = strongest topic-hour of the last 7 days.)*
- **Scoring:** per item, growth rate adjusted for age and channel size; per source, vs that source's own baseline; per topic, weighted sum across sources (weights in config) vs previous 24h. Flags: `NEW`, `SPIKING`, `CONFIRMED` (rising on 2+ sources; expect this to be rare at launch since Twitch titles are noisy, so it must not block anything). Formula in `docs/SCORING.md`.
- **Serving:** FastAPI reads scores; Next.js renders with `revalidate`; worker sends alerts and digest.

---

## 7. Phases and tasks

### Phase 0 — Accounts and access (Nov 3)
Phase done when: launch keys are in hand and slow applications are submitted.
- **P0.GH** GitHub repository (section 1)
- **P0.1** Checklist of accounts/keys for me: VPS provider, domain on Cloudflare (**note: avoid "GTA" in the domain because of trademark risk**), R2 access keys (bucket-scoped), YouTube API key, Twitch app, Resend, Telegram bot, Sentry, Healthchecks.io, uptime monitor. Submit applications today: Reddit, Threads, Google Trends.
  - [ ] List delivered  - [ ] `.env.example` lists every variable  - [ ] Each token minimum-permission
- **P0.2** Local tooling: `ansible`, `ansible-lint`, `docker`, `gh`
  - [ ] Versions printed

### Phase 1 — Server up, YouTube collecting (Nov 3–4) ⚠ critical path
Phase done when: YouTube snapshots land hourly in Postgres on the server.
- **P1.1** Manual one-time setup (VPS, DNS, R2 bucket + 14-day lifecycle), steps in `docs/MANUAL_SETUP.md`
  - [ ] Server reachable by SSH key  - [ ] DNS resolves
- **P1.2** Ansible `site.yml` tags `base` + `docker` + `app`; compose with caddy, postgres, worker, placeholder api/web; `.env` from Vault
  - [ ] Password + root SSH refused  - [ ] `docker compose ps` healthy  - [ ] Postgres not reachable from outside  - [ ] Second run 0 changes  - [ ] `ansible-lint` passes
- **P1.3** HTTPS via Caddy
  - [ ] `https://<domain>` loads  - [ ] `/api/health` OK
- **P1.4** Alembic: `raw_responses`, `items`, `signals`, `connector_runs`
  - [ ] Up and down clean
- **P1.5** YouTube discovery (search + uploads playlists) + hourly snapshots + quota guard + `connector_runs` logging + pydantic validation + tenacity retries
  - [ ] New videos in `items`, re-run creates no duplicates  - [ ] Hourly rows in `signals`  - [ ] Simulated quota limit stops jobs  - [ ] Simulated 429/5xx retries

### Phase 2 — More sources + safety basics (Nov 5)
Phase done when: three sources land in `signals`, a backup restores, and a push to `main` deploys.
- **P2.1** Twitch connector (game ID, streams, clips, token refresh)  - [ ] Streams + clips in `signals`
- **P2.2** Wikipedia connector (daily, User-Agent, article→topic map)  - [ ] Daily pageviews in `signals`
- **P2.3** YouTube `channels.list` daily job  - [ ] Subscriber counts stored
- **P2.4** Backups tag: nightly `pg_dump` → R2  - [ ] File in R2  - [ ] Restored into a test DB
- **P2.5** GitHub Actions `ci.yml` + `deploy.yml`; secrets via `gh secret set`  - [ ] Test commit deploys automatically
- **P2.6** Sentry (worker, api) + Healthchecks.io heartbeat + external uptime check  - [ ] Test error in Sentry  - [ ] Stopping worker triggers Healthchecks alert
- **P2.7** `docs/CONNECTORS.md`: how to add a source
- **P2.8** Overnight review  - [ ] Snapshots every hour, quota under budget

### Phase 3 — The brain (Nov 6–8)
Phase done when: hourly top topics look sensible to a human, with no obvious duplicates or spam.
- **P3.1** dbt project: sources + freshness, staging models, `int_signal_deltas` (hourly growth); `dbt build` after each cycle  - [ ] Data checks pass: no duplicates, no negative growth, no null timestamps
- **P3.2** Title cleaning + keyword topics (aliases + n-grams) → `topics`, `topic_items`  - [ ] Same topic keeps same ID hour to hour
- **P3.3** Momentum scoring + flags → `topic_scores` hourly; spam/reupload filters; `docs/SCORING.md`
  - [ ] I review the top 20 and approve (or we trigger the embeddings upgrade path)

### Phase 4 — The product (Nov 9–11)
Phase done when: a stranger on a phone understands the site, sees today's top topics, and joins the waitlist in under a minute.
- **P4.1** API: `GET /topics/top`, `GET /topics/{slug}`, `GET /videos/rising`, `POST /waitlist` (rate-limited, email validated)  - [ ] Endpoint tests pass
- **P4.2** Home: top 5, "updated X minutes ago", waitlist CTA
- **P4.3** Topic page: 7-day momentum chart, videos, related keywords
- **P4.4** Rising videos (top 10)
- **P4.5** About (unofficial fan-made tool, not affiliated with Rockstar Games or Take-Two; "Data from YouTube" attribution) + **Privacy policy** + Pro teaser
- **P4.6** SEO titles/descriptions; original design (no GTA logos/artwork); mobile-first; Sentry in web  - [ ] Every page checked at phone width

### Phase 5 — Delivery (Nov 12)
Phase done when: a test spike posts to the Telegram channel within minutes, the morning digest arrives, and the daily card is ready.
- **P5.1** Daily digest to waitlist (Resend, signed unsubscribe link)  - [ ] Received; unsubscribe works
- **P5.2** Spike alerts → public Telegram channel; dedupe via unique `(topic_id, date)`  - [ ] Simulated spike posts exactly once
- **P5.3** Admin button: 1080×1920 card of top 5 via Next.js `ImageResponse` (`next/og`) + short on-camera script  - [ ] Card downloaded

### Phase 6 — Safety net and testing (Nov 13–14)
Phase done when: five outside people used the site without help, all sources are healthy, and a deliberately broken job raises an alert.
- **P6.1** Admin page (`/admin`, basic_auth): source health, quota used, rename/merge/hide topics, waitlist CSV export. (Queries and weights stay in config and change via deploy.)
- **P6.2** Ops alert to my Telegram when a connector fails twice in a row  - [ ] Broken job triggers it
- **P6.3** Quick load test (`oha` or `hey`) on home + API  - [ ] Results documented
- **P6.4** Fix list from review + user testing → feature freeze

### Phase 7 — Launch (Nov 15–19)
Phase done when: the site is public and stable through release day.
- **P7.1** Pre-launch check: every source, alert, digest, backup
- **P7.2** Go live; check errors, uptime, quota every few hours for the first 48h
- **P7.3** Tune scoring weights on release-week data

### Phase 8 — After launch (Nov 20 onward)
- **P8.1** Terraform for VPS, firewall, DNS, R2 (remote state on R2, locking documented); `terraform.yml` plan-on-PR, manual apply
- **P8.2** Rebuild drill: staging server from zero with Terraform + Ansible + backup restore, timed, documented (ask before creating the paid staging server)
- **P8.3** Auth.js magic links + Stripe + Pro features + per-user email/Telegram alerts
- **P8.4** New sources behind flags: Bluesky, RSS, Threads, X (spend cap), Reddit (after approval)
- **P8.5** "Make this now" list (high TALK/WATCH momentum, low MAKE coverage)
- **P8.6** Upgrade triggers, documented: Redis when >1 worker or response caching isn't enough · partition `signals` near 100M rows · Dagster when jobs multiply · bigger VPS when resources stay high

---

## 8. Rules (every task)

- Official APIs only; follow each platform's terms; stay within rate limits.
- No Rockstar/GTA logos, artwork, characters or music. Label the product as an unofficial, fan-made tool.
- We sell analysis, rankings and alerts, never raw platform data.
- Minimal user data (email); one-click unsubscribe.
- Secrets only in Ansible Vault, GitHub secrets or env vars. Never commit, print or log them.
- Server changes only through Ansible. Anything done by hand once goes in `docs/MANUAL_SETUP.md` and gets automated after launch.
- Ask me before: spending money, deleting data, changing production data, force-pushing, or creating/destroying servers.

**Start now with section 1 (GitHub repository), then create `docs/PLAN.md`, and show me the plan before starting Phase 1.**
