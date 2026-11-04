-- Grain: one item (video, stream, clip, article, post, channel) per source. Light cleaning only.
select
    source,
    item_id,
    item_type,
    nullif(btrim(title), '') as title,
    url,
    channel_id,
    channel_title,
    published_at,
    first_seen_at
from {{ source('warehouse', 'items') }}
