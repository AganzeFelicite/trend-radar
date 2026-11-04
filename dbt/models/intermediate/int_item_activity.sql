-- Grain: one item x hour. activity = attention the item gained in that hour, in its source's own unit: the metrics
-- with activity=true in seeds/metric_catalog.csv (YouTube views; Bluesky likes+reposts+replies+quotes; Twitch
-- concurrent viewers; Wikipedia pageviews). A source with no activity metric (RSS) counts 1 per item: a mention.
--   cumulative: the increase since the previous reading, never negative.
--     First reading of an item under 24h old: its whole count, placed at the hour it was published (event time,
--     not processing time), so a video found 10h after upload doesn't look like a burst now.
--     First reading of an older item: 0 (we can't tell when those views happened); it counts from the next reading.
--   gauge / per_period: the reading itself.
-- Spam-flagged items (int_item_quality) are left out.
-- ponytail: full rebuild; go incremental on (item, hour) when the build passes a minute.
with signal_activity as (
    select
        d.source,
        d.item_id,
        case when d.kind = 'cumulative' and d.prev_value is null
             then date_trunc('hour', t.seen_at) else d.captured_at end as hour,
        sum(case
                when d.kind <> 'cumulative' then d.metric_value
                when d.prev_value is not null then greatest(d.delta, 0)
                when t.seen_at > d.captured_at - interval '24 hours' then d.metric_value
                else 0
            end) as activity
    from {{ ref('int_signal_deltas') }} d
    join {{ ref('metric_catalog') }} c on c.source = d.source and c.metric_name = d.metric_name
    join {{ ref('int_item_text') }} t on t.source = d.source and t.item_id = d.item_id
    where c.activity
    group by 1, 2, 3
),

mentions as (
    select source, item_id, date_trunc('hour', seen_at) as hour, 1::numeric as activity
    from {{ ref('int_item_text') }}
    where source not in (select source from {{ ref('metric_catalog') }} where activity)
)

select a.source, a.item_id, t.channel_id, a.hour, a.activity
from (select * from signal_activity union all select * from mentions) a
join {{ ref('int_item_text') }} t on t.source = a.source and t.item_id = a.item_id
join {{ ref('int_item_quality') }} q on q.source = a.source and q.item_id = a.item_id
where q.spam_reason is null
