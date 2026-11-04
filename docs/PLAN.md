# Plan

Source of truth for progress. Spec: [BRIEF.md](BRIEF.md).

**Definition of Done (every task):** implemented · tested (or manual test documented) · docs updated if behaviour changed · committed (`P1.5: ...`) · deployed if it affects the server · verified.

Each task lists only its specific checks plus `Verified:` (how it was checked).

Status key: `[ ]` todo · `[x]` done and verified · `[~]` blocked (reason given)

## Launch priority order (owner + advisor, Nov 4)
Launch Nov 15–17. Urgent fixes first (P2.10–P2.12, P3.4), then:
1. **Server live with Ansible:** P1.1–P1.3, history moved with `pg_dump`/restore. Terraform stays after launch (P8.1).
2. **Backups to R2:** P2.4.
3. **CI/CD + monitoring:** P2.5, P2.6.
4. **Finish Phase 4:** P4.5, P4.6 (before collecting real emails).
5. **Daily Brief** P9.1 → digest (P9.4 = P5.1) + Telegram alerts (P5.2) built on it.
6. **Content card + AI channel MVP:** P9.2–P9.8. Anything not ready by Nov 15 moves to release week; the site launch does not wait for the channel.

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
  - [ ] `.env` from Ansible Vault; **no dev password defaults** in `docker-compose.yml` (`POSTGRES_PASSWORD` falls back to one in 4 places today)
  - [ ] History moved from the Mac: `pg_dump` → restore on the server, row counts match
  - Verified:
- [~] **P1.3** HTTPS via Caddy. **Blocked: P1.1.**
  - [ ] `https://<domain>` loads
  - [ ] `/api/health` OK
  - [ ] `/admin` and `/api/admin/*` behind Caddy `basic_auth` (the app has no login of its own yet)
  - Verified:
- [x] **P1.4** Alembic: `raw_responses`, `items`, `signals`, `connector_runs`
  - [x] Up and down clean
  - [x] Bronze TTL: `maintenance.purge_raw` deletes `raw_responses` older than 30 days, daily 03:30 UTC (Nov 4; test + real run logged)
  - Verified: local Postgres: `alembic upgrade head` → 4 tables; `alembic downgrade base` → only `alembic_version`; `upgrade head` again OK; `alembic check` → "No new upgrade operations detected."
- [ ] **P1.5** YouTube discovery + hourly snapshots + quota guard + `connector_runs` + pydantic + tenacity
  - [x] New videos in `items`; re-run creates no duplicates (test, mocked API)
  - [x] Hourly rows in `signals`; same-hour re-run upserts (test, mocked API)
  - [x] Simulated quota limit stops jobs (test)
  - [x] Simulated 429/5xx retries; 4xx not retried (test)
  - [x] Worker image builds, runs as non-root, migrates on start, exits if `YOUTUBE_API_KEY` missing
  - [x] Real run against the YouTube API (Nov 3): discover → 97 unique videos for 200 units; snapshot → 97 videos for 2 units
  - [ ] Sub-task: discovery via uploads playlists (1 unit/call): needs the curated GTA channel list
  - Verified: `uv run pytest` → 10 passed; worker with real key: `connector_runs` discover ok (100 results, 200 units), snapshot ok (97, 2 units)

## Phase 2: More sources + safety basics (Nov 5)
Done when: three sources land in `signals`, a backup restores, and a push to `main` deploys.

- [ ] **P2.1** Twitch connector (game ID, streams, clips, token refresh)
  - [x] Streams (paged by cursor) + clips in `signals`; same-hour re-run overwrites (test, mocked API)
  - [x] Token cached and reused; 401 → refreshed once; missing category fails the run (tests)
  - [x] Real run (Nov 3): credentials OK, but Twitch has no "Grand Theft Auto VI" category yet → run records `waiting` (not `error`) and retries hourly
  - [ ] First real streams/clips once Twitch creates the category
  - Verified: `uv run pytest tests/test_twitch.py` → 3 passed
- [x] **P2.2** Wikipedia connector (daily, User-Agent; article→topic mapping moves to P3.2 when topics exist)
  - [x] Daily pageviews in `signals`
  - Verified: live API run Nov 3: 6/6 articles found, 30 days each (GTA VI avg 16,835/day, peak 26,444); worker in Docker ran it on start → `connector_runs` status ok, 6 items
- [x] **P2.3** YouTube `channels.list` daily job
  - [x] Subscriber counts stored as `channel` items + `subscribers` signals; hidden counts skipped; snapshot ignores channels (test)
  - [x] **Real run**: runs daily 06:15 UTC and on worker start; 7 ok runs by Nov 4 08:00 (305 channels, 45 units)
  - Verified: `uv run pytest tests/test_youtube.py` → 6 passed; `connector_runs` youtube/channels status `ok` ×7 (status report Nov 4)
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
- [ ] **P2.9** More sources before Phase 3 (owner decision Nov 4: all sources in first, then dbt). Guide: [adding-sources.html](adding-sources.html)
  - [x] News RSS (Nov 4): 8 feeds, GTA keyword filter, `items` only; broken feeds isolated (`partial`). 3 tests; real run: 8/8 feeds ok, 24 GTA headlines from 7 outlets
  - [ ] Bluesky: needs a free app password (public search returns 403)
    - [x] Connector + 3 tests against a mocked API (Nov 4): one login per run, latest + top over 24h, 4 metrics per post
    - [x] Real run (Nov 4): 624 unique posts / 435 authors over 24h; 'latest' reaches back ~10h at ~50 posts/h
    - [x] Fixes from real data: link-card title joined to post text (GTA words found 513 → 617 of 625); adult-labelled posts kept out of silver; completeness check (`partial` if 'latest' reaches back < 2h)
    - [ ] Tune queries (`GTA 6` vs `GTA6`/`GTA VI`) once the language decision is made
  - [ ] Reddit: when API access is approved (can be built against mocks first)
  - [ ] Google Trends API: when alpha access is granted
  - Verified:
- [x] **P2.10** Stop losing hourly data on the Mac (urgent fix A1, Nov 4)
  - [x] `misfire_grace_time` 3600 + `coalesce` for every job (`scheduler.JOB_DEFAULTS`)
  - [x] `scripts/radar.sh up --awake` keeps the Mac awake (`caffeinate -dimsu`); `down` releases it
  - [x] A job delayed past 10 minutes still runs
  - Verified: `tests/test_scheduler.py`: a job 21 min late is skipped with the old 600 s grace and runs with `JOB_DEFAULTS` (also at 59 min). `up --awake` → `pmset -g assertions` shows caffeinate holding PreventSystemSleep, PreventUserIdleSystemSleep, PreventUserIdleDisplaySleep. A closed lid (or battery) still sleeps a laptop.
- [x] **P2.11** Emergency local backup until R2 exists (urgent fix A2, Nov 4)
  - [x] `scripts/radar.sh backup <folder>` (or `RADAR_BACKUP_DIR`): `pg_dump -Fc -Z 6`, UTC date and time in the name, newest 7 kept, written as `.part` until complete
  - [x] A dump file exists and restores into a throwaway database (`scripts/radar.sh restore-test`)
  - Verified: Nov 4 08:19, 15 MB dump; `restore-test` → `restore_check` items 1,638 · signals 33,120 · runs 175 · topics 33 vs live 1,639 · 33,121 · 176 · 33 (live kept collecting); throwaway database dropped. Rotation: 8 older files + 2 new → 7 kept, oldest removed.
- [x] **P2.12** Close stale runs on worker start (urgent fix A3, Nov 4)
  - [x] `running` rows started before the worker start → `aborted` (`maintenance.abort_stale_runs`)
  - [x] Row id 91 becomes `aborted`
  - Verified: `tests/test_maintenance.py` (only `running`, only before the start). Real restart Nov 4 08:17: log "marked 1 run(s) … as aborted"; row 91 `aborted`, `finished_at` set, error "worker restarted mid-run".

## Phase 3: The brain (Nov 6–8)
Done when: hourly top topics look sensible to a human, with no obvious duplicates or spam.

- [x] **P3.1** dbt Core project (decided Nov 4): sources + freshness, staging models, `int_signal_deltas`; `dbt build` run by the scheduler after each snapshot
  - [x] dbt tests pass: no duplicates, no null timestamps, every metric in `metric_catalog`; shrinking cumulative totals warn above 5% of the last 24h (real rate ~1.7%); `dbt source freshness` passes for YouTube, Bluesky, Wikipedia, RSS
  - [x] `transform.build` hourly at :40, logged in `connector_runs` (ok / partial / error); 2 pytest tests run the real dbt project on the test DB
  - Verified: in the worker container: `dbt build` 15/15 nodes ok, 4,858 delta rows; Safehouse video +10,049 views/h across the 5 h sleep gap
  - Verified:
- [x] **P3.2** Title cleaning + keyword topics (aliases + n-grams) → `topics`, `topic_items`
  - [x] Same topic keeps same ID hour to hour: ID = slug from `seeds/topic_aliases.csv` (by construction; slug format + alias uniqueness tested)
  - [x] Language (owner, Nov 4): phrase discovery English-only (`var topic_discovery_languages`), alias matching on all languages
  - [x] `phrase_candidates` review list (3+ authors, ranked by items in no topic yet); first curation pass added 2 topics + 15 aliases (coverage 38% → 42%)
  - Verified: real data: 27 topics, 671 topic-item links, top topics Pre-load 128 · File size 124 · Xbox 99; dbt 26/26 in the worker; pytest 22 passed
  - Verified:
- [ ] **P3.3** Momentum scoring + flags → `topic_scores`; spam/reupload filters; `docs/SCORING.md` *(unticked Nov 4: built and verified, waiting on the owner's top-20 approval)*
  - [ ] Owner reviews top 20 and approves (or triggers embeddings upgrade)
    - Nov 4: owner triggered the AI upgrade and asked for a defined scale. Built: `ai.embed` (multilingual MiniLM, pgvector), `ai.discover` (HDBSCAN + `ai_topics` registry + Claude Haiku naming), dbt `int_topic_centroids`, `int_semantic_matches`, `topics` = curated ∪ AI, `ai_spam` flag, score 0–100. Waiting on `ANTHROPIC_API_KEY` (8 clusters queued), then the top-20 review again.
  - Verified: dbt models `int_item_quality` (spam), `int_item_activity` (item × hour, event time), `topic_scores` (topic × hour, 7 days), `rising_items`; seed `source_weights`. Real data Nov 4 01:46: 35/35 dbt nodes, 30 items flagged (23 low-engagement videos, 7 reposts), top 5 = preload, xbox, release-date, file-size, map; growth = 1 until 48h after each source started (like-for-like guard). pytest `test_scores_rank_size_times_growth_flag_spikes_and_new_topics_and_drop_spam` (ranking, capped growth, SPIKING, NEW, spam drop, coverage guard); 23 passed.

- [x] **P3.4** Top-5 trust rule + off-topic buzz (urgent fix A4, Nov 4)
  - [x] dbt var `top5_min_sources` (default 2, 1 = off): the public top 5 needs activity on 2+ sources → `topic_scores.in_top5`, `public_rank`; single-source topics rank from #6 ("Also moving")
  - [x] Off-topic flag: `off_topic_flags` (migration d9f3a7b1c2e4), set with `scripts/radar.sh offtopic <slug> on|off` until /admin (P6.1); flagged topics get no public rank and show in a small "Off-topic buzz" section
  - [x] Blue Texas (single source) no longer in the public top 5; still in the full ranking or the off-topic section
  - Verified: pytest scoring test on the real dbt project (a 2-source topic takes public #1 over a higher-momentum 1-source topic; a flagged topic has no public rank) + API test; dbt test `assert_topic_scores_valid` fails the build on any violation. Real data Nov 4 08:18: public top 5 = Pre-load, Xbox, File size, Map, Release date (3 sources each); Blue Texas #6 under "Also moving". Flagged for the check → "Off-topic buzz" only; then unflagged (owner's call). Screenshots 1280 light, 390 dark.

## Phase 4: The product (Nov 9–11)
Done when: a stranger on a phone understands the site, sees today's top topics, and joins the waitlist in under a minute.

- [x] **P4.1** API: `GET /topics/top`, `GET /topics/{slug}`, `GET /videos/rising`, `POST /waitlist` (rate-limited, validated)
  - [x] Endpoint tests pass
  - Verified: Nov 4, `trend_radar/api.py` + `waitlist` table (migration c4d8e1f2a3b5). `tests/test_api.py`: ranking, 7-day series with empty hours = 0, growth null until the previous window is covered, topic page (videos, news, keywords, 404), rising videos (small channel first, unknown subscriber count left out), waitlist (422 invalid, lowercase + dedupe, 429 on the 6th signup/hour); 28 passed. Real data via compose `api` on 127.0.0.1:8000.
- [x] **P4.2** Home: top 5, "updated X minutes ago", waitlist CTA
  - Verified: Nov 4, `apps/web` (Next.js 16, Cache Components). `next build` passes with the API down (data is request-time, 1-min cache). Compose `web` on 127.0.0.1:3100, non-root, 294 MB. Screenshot at 390 px: no horizontal scroll. Waitlist form → API through the `/api` rewrite (422 shown inline). Stranger test still to do (P6.4).
- [x] **P4.3** Topic page: 7-day momentum chart, videos, related keywords
  - Verified: Nov 4, `/topics/[slug]`: score, rank, share, growth ("from Nov 5" until measurable), posts, channels, SVG score chart, keyword chips (alias counts, 7 days), top videos (24h), news headlines. Unknown slug shows the not-found page (soft 404: status 200 because the page streams).
- [x] **P4.4** Rising videos (top 10)
  - Verified: Nov 4, `/videos`: ranked by 24h views per 1,000 subscribers ("N× the channel's subscribers"), 1,000+ views, channels with a known subscriber count only; top 3 also on home.
- [ ] **P4.5** About (unofficial, not affiliated, "Data from YouTube") + Privacy policy + Pro teaser
  - Verified:
- [ ] **P4.6** SEO, original design, mobile-first, Sentry in web
  - [x] Every page checked at phone width (Nov 4, screenshots at 390 px, light + dark)
  - Design pass Nov 4: radar hero (top 5 as blips, CSS sweep, off with reduced motion), featured #1 card with evidence, rank change over 6h (`rank_6h_ago`), live stats strip, YouTube thumbnails (served by YouTube, not proxied or stored), axis-labelled score chart, Bluesky post cards. SEO + Sentry still to do.
  - Verified:

## Phase 5: Delivery (Nov 12)
Done when: a test spike posts to the Telegram channel within minutes, the morning digest arrives, and the daily card is ready.

- [ ] **P5.1** Daily digest to waitlist (Resend, signed unsubscribe) → built as **P9.4** on the Daily Brief (P9.1)
  - [ ] Received; unsubscribe works
  - Verified:
- [ ] **P5.2** Spike alerts → public Telegram channel; dedupe on `(topic_id, date)`; daily post from the approved brief (P9.1–P9.3)
  - [ ] Simulated spike posts exactly once
  - Verified:
- [ ] **P5.3** Admin: 1080×1920 top-5 card (`next/og`) + on-camera script → the data cards and script of the Content Package (**P9.5**)
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
  - [ ] YouTube API policy: confirm how long silver may keep YouTube titles/stats (bronze already purged at 30 days)
  - [ ] Bluesky: honour post deletions (posts are public, but deleted ones should not stay in silver indefinitely)
- [ ] **P7.2** Go live; monitor errors/uptime/quota every few hours for 48h
- [ ] **P7.3** Tune scoring weights on release-week data

## Phase 8: After launch (Nov 20+)

- [ ] **P8.1** Terraform (VPS, firewall, DNS, R2; remote state) + `terraform.yml`
- [ ] **P8.2** Rebuild drill on staging, timed and documented
- [ ] **P8.3** Auth.js + Stripe + Pro + per-user alerts
- [ ] **P8.4** New sources behind flags: Bluesky, RSS, Threads, X, Reddit; YouTube comment text; Twitch chat (Nov 3: owner chose YouTube + Twitch only for launch)
- [ ] **P8.5** "Make this now" list
- [ ] **P8.6** Upgrade triggers documented (Redis, partitioning, Dagster, bigger VPS)

## Phase 9: AI channel and content engine (owner + advisor, Nov 4; revised same day)
Goal: one verified data run per day powers everything: the subscriber email, Telegram, the website "Today" page, and
**Content Packages** for short videos hosted by an obviously-AI character, **RADAR** (working name, owner to confirm).
**Trend Radar does not make videos.** The owner's separate "Video Studio" makes them from our packages. The channel grows
an audience sponsors pay to reach; viewers discover the site and subscribe. Priority: P9.1 + P9.4 before launch
(priority 5); P9.2–P9.8 by Nov 15 or release week (priority 6).

Done when: an approved Daily Brief produces, the same morning, a test digest email, a Telegram post, the website "Today"
text, and at least one English Content Package (JSON + Markdown + data cards + Video Studio prompts) ready to hand to the
Video Studio. Everything is approved by the owner, and every fact traces to the brief.

**Non-negotiable rules**
- **Facts only from data.** The writer gets the Daily Brief and may not add facts, numbers, topics or claims not in it. Every number is inserted from the brief by code, never generated by the model.
- **Human approval.** Nothing is sent, published or exported without the owner's explicit approval in /admin.
- **Clearly AI.** RADAR is a stylised, obviously-AI host, never a realistic fake human. Bios say "AI anchor powered by real-time GTA 6 trend data." The owner switches on platform AI labels when posting (YouTube altered/synthetic disclosure; TikTok AI-generated label).
- **Originality (YouTube "inauthentic content" policy).** Every package has our own data (rankings, scores, charts, a "make this now" pick) and one line of human commentary the owner writes or edits. Rotate formats; never reuse identical titles or thumbnails.
- **No third-party media.** No creator clips or thumbnails, no Rockstar/GTA logos, artwork, characters or music. Visuals are our own data graphics (later the owner's own gameplay, if Rockstar's policy allows).
- **Email law and consent.** Double opt-in, unsubscribe link in every email, physical mailing address in the footer, clear sender identity.
- **Costs capped.** AI writing has a monthly cap in config; jobs stop and alert the owner when it is reached. Video rendering costs live in the Video Studio, not here.

- [ ] **P9.1** Daily Brief builder (no AI): daily job after the morning dbt build → one JSON per day in `daily_briefs` (date, version, json, status draft/approved/published). Contents: top 5 (name, score, rank change, sources, item counts), biggest riser, "make this now" pick (high talk/watch momentum, few videos; empty until growth data exists), 3 breakout videos (title, channel, link: email/site only, never in packages), off-topic buzz (optional), data window and freshness notes
  - [x] JSON schema defined and validated with pydantic (`trend_radar/brief.py`; stored JSON round-trips through it)
  - [x] Brief for today generated from real data (Nov 4 v2, 08:40 UTC)
  - [ ] Reviewed by the owner (at `/admin`)
  - Built Nov 4 (ahead of priority order while B1 waits for the VPS): `daily_briefs` (migration e1a4c6d8f0b2), job at 06:50 UTC, `scripts/radar.sh brief`, `GET /api/admin/brief`, read-only `/admin` preview. Riser and "make this now" follow the 2-source trust rule; "make this now" is empty until growth is measurable.
  - Verified: `tests/test_brief.py` (top 5 = in_top5 only, off-topic apart, one-source riser excluded, versions per day, API returns the latest); real data v2: top 5 Pre-load 68 · Xbox 42 · File size 36 · Map 28 · Release date 27, riser Jason #20 → #17 (2 sources), notes for Twitch and growth; screenshots 1280 light, 390 dark.
- [ ] **P9.2** Writer (Claude API) with grounding guard: from the brief, (a) email copy, (b) 2–3 video scripts in different formats, (c) Telegram post, (d) website "Today" text. Every number is a placeholder (`{{topic1.score}}`) filled by code; a validator rejects any output naming a topic, number or name not in the brief, then retries or flags it
  - [x] Validator test: an output with an invented number is rejected
  - [x] Monthly cost cap enforced ($4.00, owner Nov 4; `config.AI_WRITING_MONTHLY_CAP_USD`)
  - [ ] Myth or Real? format: needs viral claims in the brief (not collected yet); Make This Now starts when the brief has a pick; Weekly Recap on Sundays
  - Built Nov 4: `trend_radar/writer.py` (Claude Haiku 5.5, structured output), `drafts` table (migration f2b5d7e9a1c3; template with placeholders + filled text), runs right after the brief at 06:50 UTC, `scripts/radar.sh drafts`, drafts and month spend on `/admin`. Grounding: placeholders only (no typed digits except "GTA 6", "top 5/3", "24 hours", "out of 100"), unknown placeholders, our topics not in the brief, and video placeholders in scripts are rejected; one retry with the reasons, then `flagged`. Cap: checked before every call with a worst-case estimate; at the cap the run is `capped` and shown on /admin (Telegram alert when the bot token exists, P6.2). Cost = tokens × list price ($0.10 / $0.50 per MTok), stored in `connector_runs.quota_used` as micro-dollars.
  - Verified: `tests/test_writer.py` (fake Claude): typed "92" rejected and retried; video in a script flagged after the retry; cap reached → no call, status `capped`; filled text and cost. Real run Nov 4: 4 drafts (email, Telegram, Today, Daily Radar script), all passed the check, $0.0036 then $0.0019 after a wording fix; numbers match the brief.
- [ ] **P9.3** Admin approval page: today's brief and all drafts side by side; edit text, add the one-line human commentary per video, approve or reject each item *(Nov 4: read-only `/admin` shows the brief and empty draft slots; no actions yet)*
  - [ ] Nothing can be sent or exported unless status = approved (enforced server-side)
  - Verified:
- [ ] **P9.4** Subscriber email (Resend): double opt-in for waitlist/subscribers, signed unsubscribe links, physical address in the footer (config); daily digest rendered with React Email from the approved brief; opens/clicks tracked (= P5.1)
  - [ ] Opt-in confirmation email works end to end
  - [ ] Unsubscribe works and is respected immediately
  - [ ] Test send to the owner only before any real send
  - Verified:
- [ ] **P9.5** Content Package export (handoff to the owner's Video Studio). One package per video, only from an **approved** brief. Formats rotate: Daily Radar (60 s, top 3) · Make This Now (one opportunity) · Myth or Real? (a viral claim vs our data) · Weekly Recap (longer, Sundays). Each package holds:
  1. `package_id`, date, format, language, target length, status (approved)
  2. **Verified facts:** every number, topic and claim used, each with its source (topic id, metric, value, timestamp), `verified: true`
  3. **Script** with a narrative arc (hook → what the data shows → why it matters → what to watch / make next), split into timed scenes
  4. The owner's **human commentary line** (from P9.3)
  5. **Visual cues per scene:** which of our data cards to show; cards rendered as PNG/SVG in our own design (1080×1920 topic cards, rank-movement chart, momentum chart) and attached
  6. **3 title options**, caption, hashtags, all different from the last 7 packages
  7. **Rules for the Video Studio**, copied verbatim into every package: no third-party clips or thumbnails; no Rockstar/GTA logos, art or music; RADAR is a stylised, clearly-AI host; platform AI label on; no sensational claims; no finance/health/legal topics; any extra research cited and marked `unverified-context`
  8. **Ready-made prompts** for the Video Studio (research + production), filled with this package's content

  Export: `package.json` + `package.md` + data-card images, zipped. Delivery: download from /admin, plus `GET /api/content-packages/{date}` behind an admin-only token, so the Video Studio can fetch packages later.
  - Nov 4 (owner asked for it early): item 8 built as the **Video Studio brief** (`trend_radar/studio.py`, template, no AI): verified facts with sources (F1…), research per topic (the trending videos under it to read with their comments, Bluesky posts, headlines, what people call it, questions to answer), breakout videos to study, the day's script, scene plan, rules verbatim. On `/admin` (Copy, Download .md), `GET /api/admin/studio-prompt`, `scripts/radar.sh studio [file]`. Daily Brief now carries research leads per topic (`evidence`). Sensitive-topic blocklist (`config.PACKAGE_BLOCKED_TOPICS`/`_WORDS`) applied: part of P9.8. Verified: `tests/test_studio.py`; real brief v3 printed and read.
  - [ ] One package exported end to end from an approved brief
  - [ ] Every number in the script traces to a `verified` fact (automated check)
  - [ ] Data-card images rendered with our own design only (checked)
  - [ ] Titles differ from the previous 7 packages
  - [ ] Content-package endpoint refuses requests without the admin token
  - Verified:
- [ ] **P9.6** Multi-language packages (after English works): each approved English package → translated packages in 2 languages the owner chooses (e.g. Spanish, Portuguese). Facts and numbers stay identical; only the text is translated. The owner spot-checks before export
  - [ ] One approved brief produces packages in 3 languages with identical facts
  - Verified:
- [ ] **P9.7** Channel kit + tracking: channel name options, bio with AI disclosure, profile/banner in our own design, pinned "What is RADAR?" script, public media-kit page (audience numbers later). Tracking table per published video (platform, format, topic, publish time, views at 24h/7d; manual first, YouTube Analytics API later) + weekly summary of best formats/topics
  - [ ] Channel kit delivered for the owner's review
  - [ ] Tracking table + weekly summary working with sample data
  - Verified:
- [ ] **P9.8** YouTube-policy safeguards (YouTube's July 2026 clarification), enforced on every package (P9.2, P9.5, P9.6):
  - **Narrative arc:** the validator flags a script that is only a list (needs hook → data → why it matters → what next)
  - **No generic tutorials:** no how-to packages that repeat common content (e.g. "how to preload"); every video is built around our own data
  - **No sensational or misleading claims:** no "cancelled / leaked / confirmed" framing unless the brief holds a verified source for it; no fake urgency
  - **Sensitive-topic filter:** finance, investing, money-making, health, medical and legal topics never reach a package (configurable blocklist + AI classifier tag); e.g. "Mark Tilbury Savings". They may still rank on the website if the owner chooses
  - **Weekly channel audit:** every Sunday, the last 10 packages side by side (titles, formats, first script lines), with anything too similar flagged
  - [ ] Validator test: a list-only script is flagged
  - [ ] Validator test: "leaked" / "confirmed" framing without a verified source is rejected
  - [ ] A blocklisted or classifier-tagged topic (e.g. `mark-tilbury-savings`) never appears in a package (test)
  - [ ] Weekly audit view flags two near-identical packages (sample data)
  - Verified:
