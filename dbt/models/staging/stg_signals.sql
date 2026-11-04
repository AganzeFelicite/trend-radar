-- Grain: one reading per item x metric x time bucket. Labelled with the metric catalog (kind, bucket).
-- Left join on purpose: a metric missing from the catalog gets kind = null and fails the not_null test.
select
    s.source,
    s.item_id,
    s.metric_name,
    c.kind,
    c.bucket,
    s.metric_value,
    s.captured_at
from {{ source('warehouse', 'signals') }} s
left join {{ ref('metric_catalog') }} c using (source, metric_name)
