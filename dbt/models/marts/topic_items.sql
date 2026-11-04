-- Grain: one item in one topic (an item can belong to several). matched_alias = the longest alias that hit.
-- ponytail: regex match of every item x every alias, full rebuild; restrict to recent items when it gets slow.
select distinct on (a.topic_slug, t.source, t.item_id)
    a.topic_slug,
    t.source,
    t.item_id,
    a.alias as matched_alias,
    t.seen_at
from {{ ref('int_item_text') }} t
join {{ ref('topic_aliases') }} a on t.clean_text ~ ('\m' || a.alias || '\M')
order by a.topic_slug, t.source, t.item_id, length(a.alias) desc
