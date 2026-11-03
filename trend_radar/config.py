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
