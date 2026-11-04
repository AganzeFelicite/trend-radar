-- The idempotency guarantee: one reading per item, metric and bucket.
select source, item_id, metric_name, captured_at, count(*) as n
from {{ ref('stg_signals') }}
group by 1, 2, 3, 4
having count(*) > 1
