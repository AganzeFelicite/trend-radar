-- Grain: one row per item x metric x time bucket, with the change since the previous reading.
-- delta_per_hour divides by the real gap between buckets, so a 5-hour gap (worker asleep) averages correctly.
-- Meaning depends on kind: cumulative → activity per hour; gauge → change in level; per_period → change vs previous day.
-- ponytail: full rebuild every run (also picks up Wikipedia's late revisions); go incremental when it takes > 1 min.
with readings as (
    select
        *,
        lag(metric_value) over w as prev_value,
        lag(captured_at) over w as prev_captured_at
    from {{ ref('stg_signals') }}
    window w as (partition by source, item_id, metric_name order by captured_at)
)

select
    source,
    item_id,
    metric_name,
    kind,
    bucket,
    captured_at,
    metric_value,
    prev_value,
    metric_value - prev_value as delta,
    extract(epoch from captured_at - prev_captured_at) / 3600.0 as hours_since_prev,
    (metric_value - prev_value) / nullif(extract(epoch from captured_at - prev_captured_at) / 3600.0, 0) as delta_per_hour
from readings
