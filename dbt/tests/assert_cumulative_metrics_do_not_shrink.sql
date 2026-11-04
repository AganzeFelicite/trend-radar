-- Warn when more than 5% of the last 24h of cumulative readings went down. A few are normal (unlikes, deleted
-- comments, YouTube removing spam views: ~1.7% on Nov 4); a lot means bad data (e.g. mixed-up items).
-- Relative and windowed on purpose: a plain count grows with history and would warn on every run.
{{ config(severity='warn') }}
select
    count(*) filter (where delta < 0) as shrinking_readings,
    count(*) as readings
from {{ ref('int_signal_deltas') }}
where kind = 'cumulative' and delta is not null and captured_at > now() - interval '24 hours'
having count(*) filter (where delta < 0) > 0.05 * count(*)
