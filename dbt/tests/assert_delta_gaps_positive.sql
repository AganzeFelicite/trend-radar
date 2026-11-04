select *
from {{ ref('int_signal_deltas') }}
where hours_since_prev <= 0
