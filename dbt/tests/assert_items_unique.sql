select source, item_id, count(*) as n
from {{ ref('stg_items') }}
group by 1, 2
having count(*) > 1
