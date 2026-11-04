-- Grain: one topic. ID = slug from seeds/topic_aliases.csv, so it is stable hour to hour by construction.
select topic_slug, min(topic_name) as topic_name, count(*) as aliases
from {{ ref('topic_aliases') }}
group by topic_slug
