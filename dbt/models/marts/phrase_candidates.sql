-- Grain: one 2–3 word phrase seen in the last 24h that no topic alias covers yet.
-- The review list for new aliases (topic IDs stay curated, so they stay stable). 3+ different channels/authors
-- required, so one spammer can't create a phrase. Wikipedia is excluded (fixed article titles).
-- uncovered_items = items with this phrase that are in no topic yet: high = a genuinely new subject,
-- low = a fragment of a story a topic already covers. Review by uncovered_items desc.
with words as (
    select source, item_id, channel_id, u.w, u.ord
    from {{ ref('int_item_text') }},
         unnest(string_to_array(clean_text, ' ')) with ordinality as u(w, ord)
    where seen_at > now() - interval '24 hours'
      and source <> 'wikipedia'
      {% if var('topic_discovery_languages') == 'en' %}and is_english{% endif %}
),

grams as (
    select source, item_id, channel_id, w,
           lead(w, 1) over x as w2,
           lead(w, 2) over x as w3
    from words
    window x as (partition by source, item_id order by ord)
),

phrases as (
    select source, item_id, channel_id, w || ' ' || w2 as phrase, w as first_word, w2 as last_word
    from grams where w2 is not null
    union all
    select source, item_id, channel_id, w || ' ' || w2 || ' ' || w3, w, w3
    from grams where w3 is not null
)

select
    phrase,
    count(distinct (source, item_id)) as items,
    count(distinct (source, item_id)) filter (
        where not exists (select 1 from {{ ref('topic_items') }} ti where ti.source = p.source and ti.item_id = p.item_id)
    ) as uncovered_items,
    count(distinct channel_id) as channels,
    count(distinct source) as sources
from phrases p
where first_word not in (select word from {{ ref('stopwords') }})
  and last_word not in (select word from {{ ref('stopwords') }})
  and phrase !~ '^[0-9 ]+$'
  and not exists (select 1 from {{ ref('topic_aliases') }} a where p.phrase ~ ('\m' || a.alias || '\M'))
group by phrase
having count(distinct channel_id) >= 3
