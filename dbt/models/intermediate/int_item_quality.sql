-- Grain: one item (channels excluded). spam_reason is null for clean items; flagged items are left out of scoring.
--   low_engagement: YouTube video with 50k+ views but under 1 comment per 20k views (bought views, clip farms;
--     e.g. 2.6M views and 18 comments). Hidden comments (no count) are not flagged.
--   repost: the same cleaned text (20+ chars) again from the same channel or author; the earliest copy counts.
--   reupload: a YouTube title an earlier video from another channel already used; the earliest counts.
--     Not applied to Bluesky: different people posting the same link card is genuine sharing.
--   ai_spam: nearest to a cluster Claude marked as spam (int_semantic_matches, kind = spam).
-- ponytail: thresholds read off Nov 4 data (23 of 91 videos over 50k flagged); retune on release week (P7.3).
with latest as (
    select distinct on (item_id, metric_name) item_id, metric_name, metric_value
    from {{ ref('stg_signals') }}
    where source = 'youtube'
    order by item_id, metric_name, captured_at desc
),

engagement as (
    select
        item_id,
        max(metric_value) filter (where metric_name = 'views') as views,
        max(metric_value) filter (where metric_name = 'comments') as comments
    from latest
    group by item_id
),

copies as (
    select
        t.source, t.item_id, t.channel_id, t.clean_text, e.views, e.comments,
        row_number() over (partition by t.source, t.channel_id, t.clean_text order by t.seen_at, t.item_id) as copy_in_channel,
        first_value(t.channel_id) over (partition by t.source, t.clean_text order by t.seen_at, t.item_id) as first_channel
    from {{ ref('int_item_text') }} t
    left join engagement e on t.source = 'youtube' and e.item_id = t.item_id
)

select
    source,
    item_id,
    case
        when views >= 50000 and comments < views / 20000.0 then 'low_engagement'
        when length(clean_text) >= 20 and copy_in_channel > 1 then 'repost'
        when length(clean_text) >= 20 and source = 'youtube' and first_channel is distinct from channel_id then 'reupload'
        when exists (select 1 from {{ ref('int_semantic_matches') }} m
                     where m.source = copies.source and m.item_id = copies.item_id and m.kind = 'spam') then 'ai_spam'
    end as spam_reason
from copies
