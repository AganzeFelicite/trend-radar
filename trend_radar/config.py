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

# --- Wikipedia (no key; daily granularity) ---
# `or`, not a get() default: compose passes unset vars through as "".
WIKIMEDIA_USER_AGENT = (
    os.environ.get("WIKIMEDIA_USER_AGENT") or "TrendRadar/0.1 (https://github.com/AganzeFelicite/trend-radar)"
)
WIKIPEDIA_ARTICLES = [
    "Grand_Theft_Auto_VI",
    "Grand_Theft_Auto_V",
    "Grand_Theft_Auto",
    "Rockstar_Games",
    "Take-Two_Interactive",
    "Grand_Theft_Auto:_Vice_City",
]
WIKIPEDIA_BACKFILL_DAYS = 30
