select topic_slug, source, item_id, count(*) from {{ ref('topic_items') }} group by 1, 2, 3 having count(*) > 1
