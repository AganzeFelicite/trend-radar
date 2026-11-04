import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://trend_radar:trend_radar@localhost:5432/trend_radar"
)

# --- YouTube (quota: 10,000 units/day, resets at midnight Pacific) ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
# (query, order). "date" = newest uploads, "viewCount" = what's already taking off.
# Each search.list costs 100 units; each runs once per YOUTUBE_SEARCH_EVERY_HOURS over the last 24h.
YOUTUBE_SEARCHES = [("GTA 6", "date"), ("GTA 6", "viewCount")]
YOUTUBE_SEARCH_EVERY_HOURS = 1
YOUTUBE_SNAPSHOT_MAX_AGE_DAYS = 7
YOUTUBE_DAILY_QUOTA_STOP = 9_000  # leave 1,000 units headroom

SEARCHES_PER_DAY = len(YOUTUBE_SEARCHES) * 24 / YOUTUBE_SEARCH_EVERY_HOURS
assert SEARCHES_PER_DAY <= 60, f"{SEARCHES_PER_DAY} searches/day blows the 6,000-unit search budget"

# --- Twitch (app access token; rate limit 800 points/min, we use ~15/hour) ---
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")
TWITCH_GAME_NAME = "Grand Theft Auto VI"
TWITCH_MAX_STREAM_PAGES = 10  # x100 streams, sorted by viewers

# Identifies us to APIs and feeds that ask for a descriptive client name.
USER_AGENT = "TrendRadar/0.1 (https://github.com/AganzeFelicite/trend-radar)"

# --- Bronze retention (YouTube allows stored API data for 30 days) ---
RAW_RETENTION_DAYS = 30

# --- Wikipedia (no key; daily granularity) ---
# `or`, not a get() default: compose passes unset vars through as "".
WIKIMEDIA_USER_AGENT = os.environ.get("WIKIMEDIA_USER_AGENT") or USER_AGENT
WIKIPEDIA_ARTICLES = [
    "Grand_Theft_Auto_VI",
    "Grand_Theft_Auto_V",
    "Grand_Theft_Auto",
    "Rockstar_Games",
    "Take-Two_Interactive",
    "Grand_Theft_Auto:_Vice_City",
]
WIKIPEDIA_BACKFILL_DAYS = 30

# --- News RSS (no key; headlines + links only, never article text) ---
# name -> (outlet, feed URL). All RSS 2.0, verified Nov 4, 2026.
RSS_FEEDS = {
    "gamespot": ("GameSpot", "https://www.gamespot.com/feeds/news/"),
    "eurogamer": ("Eurogamer", "https://www.eurogamer.net/feed"),
    "ign": ("IGN", "https://feeds.feedburner.com/ign/all"),
    "kotaku": ("Kotaku", "https://kotaku.com/rss"),
    "gamesradar": ("GamesRadar+", "https://www.gamesradar.com/feeds/all/"),
    "pcgamer": ("PC Gamer", "https://www.pcgamer.com/rss/"),
    "polygon": ("Polygon", "https://www.polygon.com/rss/index.xml"),
    "vgc": ("VGC", "https://www.videogameschronicle.com/feed/"),
}
# A headline is kept if its title contains one of these (whole word, any case).
RSS_KEYWORDS = ["GTA", "Grand Theft Auto", "Rockstar", "Vice City", "Leonida", "Take-Two"]

# --- Bluesky (free account + app password; public search needs a login since 2025) ---
BLUESKY_HANDLE = os.environ.get("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")
BLUESKY_API = "https://bsky.social/xrpc/"  # entryway for accounts hosted on bsky.social
# (query, sort): "latest" = volume, "top" = what's taking off. Each runs over the last 24h.
BLUESKY_SEARCHES = [("GTA 6", "latest"), ("GTA 6", "top")]
BLUESKY_MAX_PAGES = 5  # x100 posts per search

# --- AI layer (docs/SCORING.md § AI topics) ---
# Embeddings run locally on CPU (free). The model is baked into the Docker image at MODEL_CACHE_DIR.
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # 50+ languages, 384 dims
MODEL_CACHE_DIR = os.environ.get("MODEL_CACHE_DIR") or None  # None = fastembed's default cache
# Claude names new clusters, merges duplicates, flags spam. Owner chose Haiku 5.5 (Nov 4): ~$2-6/month.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL = "claude-haiku-5-5"
AI_MAX_CLUSTERS_PER_RUN = 25  # cost cap: one LLM call per hour with at most this many clusters


# --- AI writing (P9.2): daily drafts from the Daily Brief ---
AI_WRITING_MONTHLY_CAP_USD = 4.00  # owner, Nov 4. Checked before every call; writing stops (status 'capped') at the cap
# Claude Haiku 5.5 list price per million tokens, prompts up to 100K tokens (claude-api skill, models.md). Thinking
# tokens are billed as output. Update both if AI_MODEL changes.
AI_PRICE_PER_MTOK_IN = 0.10
AI_PRICE_PER_MTOK_OUT = 0.50

# --- Content packages (P9.5, P9.8): topics that must never reach a video package. They may still rank on the site.
PACKAGE_BLOCKED_TOPICS = {"mark-tilbury-savings"}  # owner + advisor, Nov 4
PACKAGE_BLOCKED_WORDS = r"saving|invest|money|crypto|stock|financ|loan|health|medic|doctor|diet|legal|lawyer|lawsuit"
