-- Grain: one item with activity in the last 24h (spam excluded): the evidence under each topic, and rising videos.
--   per_hour: last-24h activity / hours the item has been live within that window (growth adjusted for age).
--   per_1k_subs (YouTube): last-24h views per 1,000 channel subscribers (adjusted for channel size: 50k views on a
--   2k-subscriber channel is a breakout, on a 5M one it's a normal day). Channels under 1,000 count as 1,000.
-- Topic attention uses raw activity (an audience is an audience); channel size only changes this ranking.
with recent as (
    select source, item_id, sum(activity) as activity_24h
    from {{ ref('int_item_activity') }}
    where hour > now() - interval '24 hours'
    group by 1, 2
),

subscribers as (
    select distinct on (item_id) item_id as channel_id, metric_value as subscribers
    from {{ ref('stg_signals') }}
    where source = 'youtube' and metric_name = 'subscribers'
    order by item_id, captured_at desc
)

select
    t.source, t.item_id, t.title, i.url, t.channel_id, i.channel_title, t.seen_at,
    r.activity_24h,
    r.activity_24h / greatest(least(extract(epoch from now() - t.seen_at) / 3600.0, 24), 1) as per_hour,
    s.subscribers,
    case when t.source = 'youtube' then 1000.0 * r.activity_24h / greatest(s.subscribers, 1000) end as per_1k_subs,
    array(select ti.topic_slug from {{ ref('topic_items') }} ti
          where ti.source = t.source and ti.item_id = t.item_id order by 1) as topics
from recent r
join {{ ref('int_item_text') }} t on t.source = r.source and t.item_id = r.item_id
join {{ ref('stg_items') }} i on i.source = r.source and i.item_id = r.item_id
left join subscribers s on t.source = 'youtube' and s.channel_id = t.channel_id
