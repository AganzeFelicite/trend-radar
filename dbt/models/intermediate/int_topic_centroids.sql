-- Grain: one centroid (a point in embedding space that stands for a topic).
--   Curated topics: the mean embedding of their alias-matched items (3+ needed).
--   AI registry (ai_topics, written by trend_radar/ai.py): one per registered cluster. kind = topic (active, or merged
--   into another topic: points at the target), noise (no shared subject: attracts generic posts so they stay
--   untopiced) or spam (items nearest to it are flagged in int_item_quality).
select a.topic_slug, 'topic' as kind, avg(e.embedding) as centroid
from {{ ref('int_alias_matches') }} a
join {{ source('warehouse', 'item_embeddings') }} e on e.source = a.source and e.item_id = a.item_id
group by 1
having count(*) >= 3

union all

select
    case when status = 'merged' then merged_into else slug end,
    case when status in ('active', 'merged') then 'topic' else status end,
    centroid
from {{ source('warehouse', 'ai_topics') }}
where status <> 'merged' or merged_into is not null
