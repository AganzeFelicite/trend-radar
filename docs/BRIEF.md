# Build Prompt: GTA 6 Trend Radar

You are my coding agent. We are building **GTA 6 Trend Radar**: a website that shows creators, every day, which GTA 6 topics are exploding right now, so they know what videos to make next.

I am a software engineer (Python, React/Next.js, PostgreSQL, Docker on a VPS). I will review your work. Explain decisions briefly as you go, and ask me before anything that costs money, deletes data, or touches production.

---

## 0. How you work: checklists for every task

Before writing any code, create `docs/PLAN.md` in the repo containing every phase and task below, each as a checkbox. Keep it updated as the single source of truth for progress.

**Every task gets its own checklist** using this Definition of Done. Copy it under each task in `docs/PLAN.md`:

```
- [ ] Implemented
- [ ] Tests written and passing (or a manual test documented if tests don't apply)
- [ ] README / docs updated
- [ ] Committed and pushed (commit message references the task, e.g. "P2.3: YouTube snapshot job")
- [ ] Deployed (if the task affects the server)
- [ ] Verified working — write HOW it was verified (command, URL, query, screenshot)
```

Rules:
- Work on one task at a time, in order. Do not start the next phase until the current phase's "Phase done when" criterion is met.
- Never tick "Verified working" without actually checking it. If something can't be verified yet, leave it unchecked and say why.
- At the end of each phase, post a short summary to me: what was done, what was verified, anything blocked, and what's next.
- If a task turns out bigger than expected, split it into sub-tasks in `docs/PLAN.md`, each with its own checklist.

---

## 1. GitHub repository setup (do this first, using my GitHub CLI)

Use the GitHub CLI (`gh`) that is installed and logged in on my machine.

1. Run `gh auth status`. If I'm not logged in, stop and ask me to run `gh auth login`. Never ask for or print my token.
2. Ask me to confirm the repository name (default suggestion: `trend-radar`).
3. Initialise the project locally: `git init`, default branch `main`.
4. Add a `.gitignore` covering Python, Node/Next.js, `.env` files, virtual environments, build output, and OS files. **`.env` must never be committed.**
5. Add a minimal `README.md` and `docs/PLAN.md` (with all checklists from section 0).
6. Make the first commit.
7. Create the repository as **private** on my account and push:
   `gh repo create <name> --private --source=. --remote=origin --push`
8. Verify with `gh repo view --json name,visibility,url` that visibility is `PRIVATE`, and show me the result.
9. Later, when deployment is ready (Phase 1), set deploy secrets with `gh secret set` (e.g. `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`). Ask me to provide the values interactively; never echo them or write them into files.

### Checklist — Task P0.GH: GitHub repository
- [ ] `gh auth status` confirmed logged in
- [ ] Repo name confirmed with me
- [ ] `.gitignore` excludes `.env` and secrets
- [ ] `README.md` and `docs/PLAN.md` committed
- [ ] Private repo created and pushed with `gh repo create --private`
- [ ] Visibility verified as `PRIVATE` with `gh repo view`

---

## 2. Context and deadline

- GTA 6 releases **November 19, 2026** (PS5/Xbox, single-player only at launch).
- Target: a working public version by **November 15–17, 2026**.
- Scope tightly. Ship the core first, polish later. If time runs short, cut scope inside a phase rather than moving launch. The data pipeline (Phases 1–2) must not be late, because momentum needs history.

## 3. Product in one sentence

Every hour we collect new GTA 6 videos, clips, streams and pageviews from official APIs, measure how fast they are growing, group them into topics, and rank topics by momentum. Free users see today's top 5 rising topics; Pro users (later) get everything plus alerts.

---

## 4. Tech stack (my familiar stack — use exactly this)

- **Hosting:** one VPS running **Docker Compose**. Services: `caddy`, `web` (Next.js + TypeScript + Tailwind), `api` (FastAPI, Python 3.12), `worker` (Python 3.12), `postgres` (`pgvector/pgvector` image), `redis`, `uptime-kuma`.
- **Reverse proxy:** Caddy with automatic HTTPS; routes `/` to `web` and `/api` to `api`.
- **Backend API:** FastAPI; SQLAlchemy 2 + Alembic for models and migrations.
- **Workers:** one Python service with APScheduler for all scheduled jobs; `httpx` (async) + `tenacity` (retries/backoff) + `pydantic` (response validation) for connectors.
- **Database:** PostgreSQL with pgvector; partition the signals/snapshots tables by day.
- **Transforms:** dbt Core (`dbt-postgres`), run by the worker after each ingestion cycle.
- **Topics:** `sentence-transformers` (`all-MiniLM-L6-v2`) embeddings stored in pgvector, clustered with HDBSCAN. Cluster names from top keywords first; optional Claude API naming behind a feature flag with a hard monthly cost cap.
- **Coordination:** Redis for quota counters, job locks and alert deduplication.
- **Auth:** Auth.js in Next.js (email magic links via Resend); users stored in Postgres.
- **Email:** Resend + React Email. **Instant alerts:** Telegram bot.
- **Raw data + backups:** Cloudflare R2 (S3-compatible, use `boto3`). Nightly `pg_dump` to R2, keep 14 days. Lifecycle rules for raw-data retention per platform terms.
- **Monitoring:** Sentry (web, api, worker) + Uptime Kuma.
- **CI/CD:** GitHub Actions builds images, pushes to GitHub Container Registry, deploys to the VPS over SSH with `docker compose pull && docker compose up -d`.
- **Security:** non-root containers; secrets only in a `.env` file on the server (never committed); firewall allows only 22/80/443; Postgres and Redis never exposed publicly.

Provide `docker-compose.yml`, a `Caddyfile`, `.env.example`, and a README covering local dev, deploy, and restore-from-backup.

### Infrastructure as Code (automation)

**Rule: no manual server or cloud changes.** Everything that creates or configures infrastructure lives in the repo and can rebuild the whole system from scratch.

- **Provisioning — Terraform** (HashiCorp). Creates the cloud resources:
  - VPS server, SSH key and cloud firewall (provider: ask me to confirm Hetzner or DigitalOcean; use its official Terraform provider)
  - Cloudflare DNS records for the domain
  - Cloudflare R2 buckets (raw data, backups) with lifecycle rules
  - Outputs: server IP, bucket names
  - Note: if I prefer a fully open-source licence, OpenTofu is a drop-in replacement; ask me once.
- **Terraform state:** stored remotely, never in git. Use the R2 bucket as an S3-compatible backend (with the settings Cloudflare documents for S3 compatibility), or HCP Terraform's free tier — ask me which. Enable state locking where supported.
- **Configuration — Ansible.** Configures the server and deploys the app, using roles:
  - `common`: packages, timezone, automatic security updates, fail2ban
  - `security`: non-root deploy user, SSH keys only, password login off, root login off, UFW firewall (22/80/443)
  - `docker`: Docker Engine + Compose plugin from the official repository
  - `app`: directories, `docker-compose.yml`, `Caddyfile`, templated `.env`, `docker compose pull && up -d`
  - `backups`: nightly `pg_dump` to R2 via a systemd timer or cron, 14-day retention
  - `monitoring`: Uptime Kuma container, log rotation
  - Inventory generated from Terraform outputs (no hand-typed IPs).
  - Playbooks must be **idempotent**: running twice changes nothing the second time.
- **Secrets:** Ansible Vault for server secrets (the `.env` values), with the vault password stored only as a GitHub secret and on my machine. Terraform provider tokens only as environment variables / GitHub secrets. Never commit plain-text secrets. (HashiCorp Vault is overkill at this size; revisit later.)
- **Pipelines (GitHub Actions):**
  - `terraform.yml`: `fmt` + `validate` + `plan` on pull requests; `apply` only manually (workflow_dispatch) after I approve the plan.
  - `deploy.yml`: build images → push to GHCR → run the Ansible `deploy` playbook against the server.
  - `lint.yml`: `ansible-lint`, `terraform validate`, Python/TypeScript linters.
- **Rebuild test:** the README must document how to destroy and recreate a staging server from zero using only Terraform + Ansible + a backup restore.

### Repository layout
```
trend-radar/
├── apps/web/            Next.js site, auth, admin UI
├── services/api/        FastAPI app
├── services/worker/
│   ├── connectors/      youtube.py, twitch.py, wikipedia.py (later: bluesky, rss, threads, x, reddit)
│   ├── scoring/         embeddings, clustering, momentum, naming
│   ├── alerts/          spike detection, email + Telegram
│   └── scheduler.py     APScheduler jobs
├── dbt/                 dbt models and tests
├── db/migrations/       Alembic
├── deploy/              docker-compose.yml, Caddyfile, backup scripts
├── infra/
│   ├── terraform/       VPS, firewall, DNS, R2 buckets, remote state config
│   └── ansible/
│       ├── inventory/   generated from Terraform outputs
│       ├── roles/       common, security, docker, app, backups, monitoring
│       ├── site.yml     full server setup
│       └── deploy.yml   app deploy only
├── docs/PLAN.md         phases, tasks, checklists
└── .github/workflows/   CI and deploy
```

---

## 5. Data sources

Official APIs only. Never scrape any site, and never use third-party scraping services.

**Launch (build now):**
1. **YouTube Data API v3** — signal type MAKE. Default quota 10,000 units/day: `search.list` ≈ 100 units, `videos.list` ≈ 1 unit per 50 IDs. Use search sparingly for discovery; use `videos.list` for hourly snapshots. Follow the YouTube API Services Terms (attribution, linking back, data storage/refresh rules).
2. **Twitch API (Helix)** — signal type WATCH. Streams (title, viewer count) and top clips (title, clip views) for the GTA 6 game category. Handle app-token refresh automatically.
3. **Wikimedia Pageviews API** — signal type WATCH. Daily pageviews for a configurable list of GTA-related articles.

**After launch (build connectors behind feature flags, default OFF):**
4. Bluesky (Jetstream, always-on listener) — TALK
5. Gaming news RSS (headline, link, timestamp only) — TALK
6. Threads API keyword search (requires `threads_keyword_search` permission; check current rate limit in Meta docs) — TALK
7. X API pay-per-use (hard monthly spend cap in config) — TALK
8. Reddit Data API (commercial use requires Reddit's approval) — TALK
9. Google Trends API alpha (only if access is granted) — WATCH

Do **not** add TikTok, Facebook or Instagram sources.

---

## 6. Architecture

- **Connectors:** one module per source; each with its own schedule, rate-limit/quota budget, retries with exponential backoff, and idempotent upserts.
- **Raw layer:** save every raw API response to R2 as gzip JSON, partitioned `source/date/hour`, plus an index row in Postgres. Data can be re-processed without re-fetching.
- **Signals layer:** normalize every source into one table: `source, item_id, item_type, title/text, url, author/channel, published_at, metric_name, metric_value, captured_at`.
- **Topics layer:** cluster items from all sources into shared topics (`topics`, `topic_items`).
- **Scoring:** per item, growth rate adjusted for age and channel size; per source, compare against that source's own baseline; per topic, weighted sum across sources (weights in config) vs the previous 24h. Flags: `NEW`, `SPIKING`, `CONFIRMED` (rising on 2+ sources at launch; raise to 3+ when more sources are on). Later: "Make this now" = high TALK/WATCH momentum with low MAKE coverage.
- **Serving:** FastAPI reads scores; Next.js renders pages; alert jobs and the content card read from Postgres.

---

## 7. Phases and tasks

Put all of these in `docs/PLAN.md`. **Each task below gets the full Definition of Done checklist from section 0**, plus its task-specific checks.

### Phase 0 — Accounts and access (Nov 3)
Phase done when: every launch-day key is in hand and slow applications are submitted. (I do most of these; you give me a list and verify what you can.)
- **P0.GH** GitHub repository (section 1)
- **P0.1** Give me a checklist of accounts/keys to create: VPS provider account + API token (for Terraform), domain on Cloudflare + Cloudflare API token (DNS + R2 permissions only), R2 access keys, YouTube API key, Twitch app, Resend, Telegram bot, Sentry; applications for Reddit, Threads, Google Trends
  - [ ] List delivered  - [ ] `.env.example` lists every variable needed  - [ ] Each token uses the minimum permissions required
- **P0.2** Local tooling check: `terraform` (or `tofu`), `ansible`, `ansible-lint`, `docker`, `gh` installed on my machine
  - [ ] Versions printed and confirmed

### Phase 1 — Server foundation, fully automated (Nov 3–4)
Phase done when: Terraform + Ansible can build the server from zero, a push to `main` deploys automatically, the domain loads over HTTPS, and a backup has been restored successfully. No manual server changes.
- **P1.1** Terraform remote state backend (R2 or HCP Terraform, as I choose)
  - [ ] `terraform init` uses the remote backend  - [ ] No state file in git  - [ ] Locking works (or limitation documented)
- **P1.2** Terraform: VPS, SSH key, cloud firewall (22/80/443), Cloudflare DNS, R2 buckets with lifecycle rules
  - [ ] `terraform plan` reviewed and approved by me before `apply`  - [ ] Outputs show server IP and bucket names  - [ ] Second `plan` shows no changes
- **P1.3** Ansible inventory generated from Terraform outputs
  - [ ] `ansible all -m ping` succeeds without hand-typed IPs
- **P1.4** Ansible roles `common` + `security`: updates, fail2ban, deploy user, SSH keys only, root and password login off, UFW 22/80/443
  - [ ] Password SSH login refused  - [ ] Root login refused  - [ ] `ansible-lint` passes  - [ ] Second run reports 0 changes (idempotent)
- **P1.5** Ansible role `docker` + `app`: Docker Engine, Compose, all services; placeholder `web`, `api`, `worker` that start and respond; `.env` from Ansible Vault
  - [ ] `docker compose ps` shows all healthy  - [ ] Postgres and Redis not reachable from outside  - [ ] No plain-text secrets in the repo
- **P1.6** Caddy + domain + automatic HTTPS
  - [ ] `https://<domain>` loads  - [ ] `/api/health` returns OK
- **P1.7** GitHub Actions: `lint.yml`, `terraform.yml` (plan on PR, manual apply), `deploy.yml` (build → GHCR → Ansible deploy); secrets set with `gh secret set`
  - [ ] A test commit deploys automatically  - [ ] A PR shows a Terraform plan
- **P1.8** Ansible role `backups`: nightly `pg_dump` to R2, 14-day retention
  - [ ] A backup file appears in R2  - [ ] Restored into a test database successfully
- **P1.9** Ansible role `monitoring` + Sentry in web, api, worker
  - [ ] A test error appears in Sentry  - [ ] Uptime Kuma shows all checks green
- **P1.10** Rebuild drill: destroy a staging server and rebuild it from scratch with Terraform + Ansible + backup restore, timing each step
  - [ ] Rebuild completed  - [ ] Steps and time documented in the README

### Phase 2 — First data flowing (Nov 5–6)
Phase done when: new GTA 6 videos are discovered automatically, views are snapshotted hourly, and daily quota stays well under the limit.
- **P2.1** Alembic migrations: `raw_responses`, `items`, `signals` (partitioned by day), `connector_runs`
  - [ ] Migrations run up and down cleanly
- **P2.2** R2 raw-storage helper (gzip JSON, `source/date/hour` paths)
  - [ ] Test file written and read back
- **P2.3** YouTube discovery job (configurable queries, ordered by date)
  - [ ] New videos appear in `items`  - [ ] Re-run creates no duplicates
- **P2.4** YouTube hourly snapshot job (videos < 7 days old, batches of 50)
  - [ ] Hourly rows in `signals` for the same videos
- **P2.5** Redis quota guard + tenacity retries + pydantic validation
  - [ ] Simulated quota limit stops jobs  - [ ] Simulated 429/5xx retries correctly
- **P2.6** `connector_runs` logging (items, errors, quota used)
  - [ ] Overnight run reviewed: snapshots every hour, quota under limit

### Phase 3 — More sources (Nov 7)
Phase done when: Twitch and Wikipedia data land in `signals` with no downstream changes.
- **P3.1** Twitch connector (streams + clips, token refresh)
  - [ ] GTA 6 game ID resolved  - [ ] Streams and clips in `signals`
- **P3.2** Wikipedia pageviews connector
  - [ ] Daily pageviews in `signals`
- **P3.3** Connector template documented for future sources
  - [ ] `docs/CONNECTORS.md` explains how to add a source

### Phase 4 — The brain (Nov 8–9)
Phase done when: hourly top topics look sensible to a human, with no obvious duplicates or spam.
- **P4.1** dbt models: raw → clean signals → hourly aggregates; dbt tests (no duplicates, no negative growth, no missing timestamps)
  - [ ] `dbt build` passes  - [ ] Runs automatically after ingestion
- **P4.2** Title cleaning + MiniLM embeddings stored in pgvector
  - [ ] Embeddings stored for all recent items
- **P4.3** HDBSCAN clustering into `topics` / `topic_items`, stable across hours
  - [ ] Same topic keeps the same ID hour to hour
- **P4.4** Topic naming from top keywords (Claude naming behind a flag, cost-capped)
  - [ ] Names readable for top 20 topics
- **P4.5** Momentum scoring + flags → `topic_scores` hourly; spam/reupload filters; formula documented
  - [ ] I review the top 20 topics and approve

### Phase 5 — The product (Nov 10–11)
Phase done when: a stranger on a phone understands the site, sees today's top topics, and joins the waitlist in under a minute.
- **P5.1** API: `GET /topics/top`, `GET /topics/{slug}`, `GET /videos/rising`, `POST /waitlist`; free vs Pro limits enforced server-side; Redis response caching
  - [ ] Endpoint tests pass  - [ ] Cached responses verified
- **P5.2** Home page: top 5, "updated X minutes ago", waitlist CTA
- **P5.3** Topic page: 7-day momentum chart, videos, related keywords
- **P5.4** Rising videos page (free: top 10)
- **P5.5** Pro page + About page (unofficial fan-made tool, not affiliated with Rockstar Games or Take-Two; "Data from YouTube" attribution)
- **P5.6** Auth.js magic-link login via Resend
- **P5.7** SEO titles/descriptions; original design (no GTA logos or artwork); mobile-first
  - [ ] Each page checked on a phone-size screen

### Phase 6 — Delivery (Nov 12)
Phase done when: a test spike triggers a Telegram alert within minutes, the morning digest arrives, and the daily card is ready to post.
- **P6.1** Daily digest email (Resend + React Email), with unsubscribe
- **P6.2** Spike alerts by email + Telegram; Redis dedupe (one alert per topic per user, daily cap)
  - [ ] Simulated spike delivers exactly one alert
- **P6.3** Admin button: 1080×1920 content card of the top 5 + short on-camera script
  - [ ] Card generated and downloaded

### Phase 7 — Safety net and testing (Nov 13–14)
Phase done when: five outside people used the site without help, all sources show healthy, and a deliberately broken job raises an alert.
- **P7.1** Admin page: source health, quota/budget, merge/rename/hide topics, edit queries and weights, export waitlist CSV
- **P7.2** Alerts to me: Telegram message when a connector fails twice in a row
  - [ ] Broken job triggers the alert
- **P7.3** Load test home page and API
  - [ ] Results documented; cached responses hold
- **P7.4** Fix list from my review and user testing; then feature freeze

### Phase 8 — Launch (Nov 15–19)
Phase done when: the site is public and stable through GTA 6 release day.
- **P8.1** Pre-launch check of every source, alert, digest and backup
- **P8.2** Go live; monitor errors, uptime and quota every few hours for the first 48h
- **P8.3** Tune scoring weights on real release-week data

### Phase 9 — After launch (Nov 20 onward; each behind a feature flag)
- **P9.1** Bluesky Jetstream listener  - **P9.2** RSS  - **P9.3** Threads  - **P9.4** X (spend cap)  - **P9.5** Reddit (after approval)
- **P9.6** "Make this now" list
- **P9.7** Stripe subscriptions + Pro features
- **P9.8** Upgrade triggers documented: Dagster when jobs multiply; bigger VPS when resources stay high; BigQuery/Snowflake only with many games or years of data

---

## 8. Rules (apply to every task)

- Official APIs only; follow each platform's terms; stay within rate limits.
- Never use Rockstar/GTA logos, artwork, characters or music in our design. Label the product as an unofficial, fan-made tool.
- We sell analysis, rankings and alerts — never raw platform data.
- Store minimal user data (email, alert settings); easy unsubscribe.
- Secrets only in environment variables, GitHub secrets or Ansible Vault. Never commit, print or log them.
- Infrastructure only through Terraform and Ansible — no manual changes on the server or in cloud dashboards. If something must be done by hand once, document it and automate it next.
- Ask me before: spending money, any `terraform apply` or `destroy`, deleting data, changing production data, or force-pushing.

**Start now with section 1 (GitHub repository), then create `docs/PLAN.md` with every task and its checklist, and show me the plan before starting Phase 1.**
