-- Grain: one item x topic, for items no alias matched, seen in the last 7 days. An item joins its nearest topic if the
-- cosine similarity is >= semantic_min_similarity (calibrated Nov 4: ~90% agree with alias matches at 0.72), plus any
-- other topic within semantic_tie_margin of it: facets of one story (pre-load, file size, release date) share items,
-- so their centroids nearly coincide, the same way one title matches several aliases. This is what puts
-- "mapa do GTA 6" in Map without a Portuguese alias.
-- Nearest is a noise cluster → no topic; a spam cluster → kind = spam (flagged in int_item_quality).
-- ponytail: items x centroids cross join (~1k x 50 today); add an HNSW index on item_embeddings when it passes ~1M pairs.
with dist as (
    select e.source, e.item_id, c.topic_slug, c.kind, min(e.embedding <=> c.centroid) as d
    from {{ source('warehouse', 'item_embeddings') }} e
    join {{ ref('int_item_text') }} t on t.source = e.source and t.item_id = e.item_id
    cross join {{ ref('int_topic_centroids') }} c
    where t.source <> 'wikipedia'
      and t.seen_at > now() - interval '7 days'
      and not exists (select 1 from {{ ref('int_alias_matches') }} a where a.source = e.source and a.item_id = e.item_id)
    group by 1, 2, 3, 4
),

ranked as (
    select
        *,
        min(d) over w as best_d,
        first_value(kind) over (w order by d, topic_slug) as best_kind
    from dist
    window w as (partition by source, item_id)
)

select source, item_id, topic_slug, kind, 1 - d as similarity
from ranked
where 1 - d >= {{ var('semantic_min_similarity') }}
  and (d = best_d
       or (best_kind = 'topic' and kind = 'topic' and d <= best_d + {{ var('semantic_tie_margin') }}))
