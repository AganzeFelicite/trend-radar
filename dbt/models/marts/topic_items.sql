-- Grain: one item in one topic. match_type: alias (keyword, curated) or semantic (embedding nearest to the topic).
-- An item matched by alias is never also matched semantically, so semantic only fills gaps.
select topic_slug, source, item_id, 'alias' as match_type, matched_alias, null::float as similarity, seen_at
from {{ ref('int_alias_matches') }}

union all

select s.topic_slug, s.source, s.item_id, 'semantic', null, s.similarity, t.seen_at
from {{ ref('int_semantic_matches') }} s
join {{ ref('int_item_text') }} t on t.source = s.source and t.item_id = s.item_id
where s.kind = 'topic'
