-- One row per topic and hour; attention is a share (0..1); growth stays inside its cap; the public top 5 holds only
-- unflagged topics with activity on enough sources, and never more than 5.
select scored_at, topic_slug, 'duplicate' as problem from {{ ref('topic_scores') }} group by 1, 2 having count(*) > 1
union all
select scored_at, topic_slug, 'out of range' from {{ ref('topic_scores') }}
where attention not between 0 and 1.000001 or growth not between 0.25 and 4
union all
select scored_at, topic_slug, 'top 5 rule' from {{ ref('topic_scores') }}
where in_top5 and (is_off_topic or sources < {{ var('top5_min_sources') }} or public_rank > 5)
