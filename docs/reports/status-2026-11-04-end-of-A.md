# GTA 6 Trend Radar: status report, end of urgent fixes (A)

**As of:** 2026-11-04 08:22 UTC · **Previous report:** `status-2026-11-04.md` (08:00 UTC) · **Launch target:** Nov 15–17
**How this was made:** every number comes from commands run at report time (git, gh, docker compose, SQL on the live database, the API, pytest, dbt result files). Secrets are reported only as set / missing / placeholder.

**Summary.** All four urgent fixes are done, verified and pushed (`009b25d`):

| Fix | Task | Result |
|---|---|---|
| A1 Hourly data on the Mac | P2.10 | A late job now runs instead of being skipped; `radar.sh up --awake` keeps the Mac awake |
| A2 Emergency backup | P2.11 | `radar.sh backup` and `radar.sh restore-test` exist and were tested |
| A3 Stale runs | P2.12 | Row 91 is now `aborted` |
| A4 Top-5 trust rule | P3.4 | Blue Texas moved from #1 to #6; the top 5 are all 3-source topics |

PLAN.md now holds the launch priority order and the new **Phase 9 (AI channel and content engine, P9.1–P9.7)**. B1 (server) waits for the owner's VPS and domain.

---

## 1. Plan progress

**Numbers used for the new tasks**
| Owner's label | PLAN.md task |
|---|---|
| A1 | P2.10 |
| A2 | P2.11 |
| A3 | P2.12 |
| A4 | P3.4 |
| C1–C7 | Phase 9: P9.1–P9.7 |

B is a priority order over existing tasks (P1.1–P1.3, P2.4–P2.6, P4.5–P4.6, P5.x). Two checks were added to P1.2: no dev password defaults, and history moved with row counts matching.

**Bookkeeping fixed:** P2.3 ticked (7 real runs); P3.3 unticked until the owner approves the top-20 review.

### Changed since the 08:00 report
| Task | Status | How verified |
|---|---|---|
| P2.3 YouTube channels | Done | pytest 6 passed; `connector_runs` youtube/channels `ok` (now 8 runs in 24h) |
| P2.10 Late jobs run + `up --awake` | Done | `tests/test_scheduler.py`: a job 21 min late is **skipped** with the old 600 s grace and **runs** with the new defaults (also at 59 min). `pmset -g assertions` shows caffeinate holding system, idle-system and display sleep |
| P2.11 Local backup | Done | 15 MB dump; restored into `restore_check`: items 1,638 / signals 33,120 / runs 175 / topics 33 vs live 1,639 / 33,121 / 176 / 33 (live kept collecting); throwaway DB dropped; rotation keeps the newest 7 |
| P2.12 Stale runs aborted | Done | pytest; real restart 08:17: log "marked 1 run(s) … as aborted", row 91 → `aborted`, finished_at set |
| P3.3 Scoring | Partly done | Open: owner's top-20 approval |
| P3.4 Top-5 trust rule + off-topic | Done | pytest on the real dbt project + API test; a dbt data test fails the build on a violation; real data and screenshots (§5) |
| P9.1–P9.7 | Not started | – |

### Unchanged
| Status | Tasks |
|---|---|
| Done | P0.GH · P1.4 · P2.2 · P2.7 · P3.1 · P3.2 · P4.1–P4.4 |
| Partly done | P0.1 (token permissions, applications) · P0.2 (`ansible-lint`) · P1.5 (uploads-playlist discovery) · P2.1 (no Twitch category) · P2.9 (Reddit, Google Trends, Bluesky query tuning) · P4.6 (SEO, Sentry) |
| Not started | P1.1–P1.3 (blocked: VPS) · P2.4–P2.6 · P2.8 · P4.5 · Phases 5–8 |

---

## 2. Code and repo

| | |
|---|---|
| Repo | `AganzeFelicite/trend-radar` · **PRIVATE** |
| Branch | `main`, pushed |
| Uncommitted | this report only |

**Last commits** (the earlier 18 are listed in the 08:00 report)
```
12b7cca docs: status report Nov 4 (shared with advisor)
009b25d feat(P2.10-P2.12,P3.4): late jobs still run, up --awake, local backup + restore test, stale runs aborted on start, top-5 needs 2+ sources, off-topic buzz
7c3b231 feat(P4.6): UI pass: radar hero, featured #1 with evidence, 6h rank movement, live stats, video thumbnails, labelled chart
```

**New files:**
- `migrations/versions/d9f3a7b1c2e4_off_topic_flags.py`
- `tests/test_scheduler.py`
- `docs/reports/status-2026-11-04.md`

**Changed:**
- `trend_radar/` scheduler, maintenance, db, api
- dbt `topic_scores` plus its test, var and source
- `apps/web` home page, ui, api client
- `scripts/radar.sh`
- README, PLAN, SCORING, CONNECTORS

---

## 3. Infrastructure

Unchanged: **no server, Terraform, Ansible, CI/CD or R2 backups.** Everything runs on the owner's Mac.

| Service | Status | Port |
|---|---|---|
| postgres | Up 20 h (healthy) | 127.0.0.1:5432 |
| worker | Up 4 min (restarted 08:17 for this release) | – |
| api | Up 4 min | 127.0.0.1:8000 |
| web | Up 4 min | 127.0.0.1:3100 |

- **Mac kept awake:** yes (`caffeinate -dimsu`, started by `radar.sh up --awake`, ends with `down`). A closed lid, or battery power, still sleeps a laptop.
- **Backups:** the tool works, but **the only dump so far was a test in a temporary folder.** No backup exists in a folder of the owner's choosing yet.
- **Keys:** unchanged from the 08:00 report.
- **Migrations:** head `d9f3a7b1c2e4`; `alembic check` → no drift.

---

## 4. Data pipeline

### Tables (exact)
| Table | Rows | Table | Rows |
|---|---|---|---|
| raw_responses | 678 | analytics.topics | 33 |
| items | 1,639 | analytics.topic_items | 988 |
| signals | 33,121 | analytics.topic_scores | 518 |
| item_embeddings | 1,304 | analytics.rising_items | 1,226 |
| connector_runs | 179 | analytics.int_signal_deltas | 33,121 |
| ai_topics | 15 | analytics.int_item_activity | 8,824 |
| off_topic_flags (new) | 0 | waitlist | 0 |

### Connectors (last 24 h)
| Connector | Last success (UTC) | Runs 24h | Errors | New items 24h | Quota / cost |
|---|---|---|---|---|---|
| YouTube discover | 08:17 | 21 ok | 0 | 387 videos | 4,200 units |
| YouTube snapshot | 08:05 | 12 ok | 0 | – | 70 units |
| YouTube channels | 08:19 | 8 ok | 0 | 335 channels | 52 units |
| **YouTube total** | | | | | **4,322 / 10,000** |
| Twitch | never | 26 `waiting` | 0 | 0 | 0 |
| Wikipedia | 08:17 | 18 ok | 0 | 6 | free |
| Bluesky | 08:17 | 20 ok | 0 | 885 posts | free |
| News RSS | 08:20 | 23 ok | 0 | 26 | free |
| AI embed | 08:20 | 13 ok | 0 | 1,304 total | free |
| AI discover (Claude Haiku 5.5) | 08:21 | 7 ok, 7 `waiting` | 0 | 15 AI clusters | 29,193 tokens |
| dbt build | 08:21 | 20 ok, 1 partial, 1 aborted (row 91) | 0 | – | – |

- **Snapshots in the last 6 h:** 03:00–06:00, then 08:00. The 07:00 snapshot was lost *before* the fix; from now on a late job runs instead of being skipped.
- **Statuses ever recorded:** ok 144 · waiting 33 · partial 1 · aborted 1 · error 0. Nothing is stuck in `running`.

### Top 10 (public ranking, 08:21 build)
| # | Topic | Score | In top 5 | Origin | Share | Sources | Items 24h | Rank 6h ago | Flags |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Pre-load | 68 | ✓ | curated | 11.7% | 3 | 60 | 1 | – |
| 2 | Xbox | 42 | ✓ | curated | 7.1% | 3 | 47 | 2 | – |
| 3 | File size | 36 | ✓ | curated | 6.0% | 3 | 58 | 3 | – |
| 4 | Map | 28 | ✓ | curated | 4.8% | 3 | 20 | 5 | – |
| 5 | Release date and times | 27 | ✓ | curated | 4.6% | 3 | 25 | 4 | – |
| 6 | Blue Texas | 82 | – (1 source) | AI | 14.0% | 1 | 51 | 22 | – |
| 7 | GTA 5 comparisons | 20 | – | curated | 3.4% | 3 | 44 | 10 | – |
| 8 | Vice City | 17 | – | curated | 2.9% | 3 | 9 | 6 | – |
| 9 | Mark Tilbury Savings | 10 | – | AI | 1.6% | 3 | 4 | 9 | – |
| 10 | Rockstar Games | 9 | – | curated | 1.5% | 2 | 16 | 7 | – |

- **Growth:** still null everywhere (measurable from about Nov 5 16:00 UTC), so scores rank topics by share only.
- **Off-topic flags:** none set; that decision is the owner's.

### dbt
- **Last build** (08:21, 13.4 s): 14 models, 4 seeds, **20/20 tests pass**, including the extended `assert_topic_scores_valid` (top-5 rule).
- **Source freshness:** 4/4 pass.

---

## 5. Product

| Page / endpoint | Status today | Change |
|---|---|---|
| `/` | 200 | Top 5 = topics with 2+ sources; new **"Also moving"** (#6–10); new **"Off-topic buzz"** section (shown only when a topic is flagged); "How the score works" explains the rule |
| `/topics/[slug]` | 200 | Rank = public rank; "1 source" and "Off-topic buzz" chips |
| `/videos` | 200 | – |
| `/about`, `/privacy` | 404 | not built (P4.5) |
| `GET /api/topics/top` | 200 | `rank` = public rank; new `in_top5`, `is_off_topic`, and an `off_topic` list |
| Other endpoints | unchanged (200 / 404 / 422 as before) | – |

- **Off-topic path verified:** Blue Texas was flagged briefly. It left the ranking, appeared under "Off-topic buzz" on home, and its topic page showed no rank. It was then unflagged. Screenshots were taken at 1280 px (light) and 390 px (dark).
- **Alerts / digest / content card:** not built. They are now planned as Phase 9 on top of the Daily Brief.
- **Waitlist:** 0.
- **Quality gates:** pytest **30 passed** (2 new); web `tsc` and `eslint` clean; dbt 20/20.

---

## 6. Deviations and issues

### Built differently from the request, and why
| Request | Built | Why |
|---|---|---|
| "Option that starts the stack wrapped in caffeinate" | `radar.sh up --awake` starts the stack, then runs `caffeinate -dimsu` in the background until `radar.sh down` | `docker compose up -d` returns at once, so wrapping it directly would keep the Mac awake for only a few seconds |
| Top-5 rule as a "config option" | dbt var `top5_min_sources: 2` in `dbt/dbt_project.yml` (1 = off), next to the other scoring settings | The rule lives in the gold mart, so the site, digest, Telegram and Daily Brief all read the same `public_rank` |
| Off-topic "manual flag in admin" | `off_topic_flags` table + `radar.sh offtopic <slug> on\|off`, which re-scores immediately | `/admin` doesn't exist yet (P6.1); it will write to the same table |
| Off-topic topics "excluded from the top 5" | Excluded from the whole public ranking and listed only under "Off-topic buzz" | Avoids showing a topic twice |
| Single-source topics "lower in the full list" | They rank from #6, shown on home as "Also moving" (#6–10) with a "1 source" chip | The site had no full list before. A score-82 topic at #6 needs that chip to explain itself |
| Backup "into a folder I choose" | `backup <folder>` or `RADAR_BACKUP_DIR`; no default folder | The owner chooses |

### Known issues and risks
| # | Issue | State |
|---|---|---|
| 1 | Only copy of the data is on the laptop | **Open until the owner runs `backup` to a folder (ideally on another disk), and P2.4 R2** |
| 2 | Mac sleep skipping jobs | Mitigated: late jobs run; `up --awake`. A closed lid / battery still sleeps |
| 3 | Dev password fallback in compose | Open; now a P1.2 check |
| 4 | Soft 404 on unknown topic pages | Open (P4.6) |
| 5 | Stale `running` rows | **Fixed** (P2.12) |
| 6 | In-memory waitlist rate limit | Open, fine for one process |
| 7 | Breakout videos skip channels with no subscriber count yet | Open |
| 8 | Creators' thumbnails show GTA VI artwork | Owner decision pending. Phase 9 rules forbid them in *videos*; the site question is separate |

**Failing tests:** none.

### Waiting on the owner
- **B1: VPS + domain** (owner buying today). Confirm when ready, with SSH access set up.
- **Run a real backup** to a folder of your choice.
- **Blue Texas / Mark Tilbury Savings:** flag as off-topic or leave ranked.
- **Top-20 approval** (P3.3).
- **Phase 9 decisions:** RADAR name; the 2 extra languages (P9.6); a physical mailing address for the email footer (P9.4, required by email law). Avatar provider comes later: I'll bring a 2–3 option comparison before integrating.
- **Unchanged from before:** R2 keys, Telegram bot token, Sentry DSNs, Healthchecks URL, real Resend key; Reddit / Google Trends application status; brand name; thumbnails on the site.

---

## 7. Next steps (recommended order)

1. **B1 Server live** (P1.1–P1.3), when the owner confirms the VPS and domain:
   - Ansible `site.yml` (base, docker, app), Caddy HTTPS.
   - `.env` from Ansible Vault with no password defaults.
   - History moved with `pg_dump` / restore, row counts compared.
2. **B2 R2 backups** (P2.4): nightly dump, 14-day lifecycle, one real restore. Reuses today's dump and restore-test steps.
3. **B3 CI/CD + monitoring** (P2.5, P2.6): `ci.yml`, `deploy.yml`, Sentry ×3, Healthchecks.
4. **B4 Finish Phase 4** (P4.5, P4.6): About, Privacy, Pro teaser, SEO, real 404.
5. **B5 Daily Brief** (P9.1), then digest (P9.4) and Telegram (P5.2) on top of it.
