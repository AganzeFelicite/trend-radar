-- Grain: one topic. ID = slug, stable hour to hour by construction.
--   curated: seeds/topic_aliases.csv (edit to add, rename or extend).
--   ai: clusters found by trend_radar/ai.py and named by Claude (ai_topics, status active).
select topic_slug, min(topic_name) as topic_name, 'curated' as origin, count(*) as aliases
from {{ ref('topic_aliases') }}
group by topic_slug

union all

select slug, name, 'ai', 0
from {{ source('warehouse', 'ai_topics') }}
where status = 'active'
