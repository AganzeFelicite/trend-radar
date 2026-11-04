-- Grain: one item (channels excluded). Title cleaned for matching:
-- lowercase, no URLs, no possessive 's, punctuation/emoji/# → space, GTA name variants normalised ("gta6",
-- "GTA VI", "Grand Theft Auto 6" → "gta 6"; same for 5), single spaces.
-- is_english: crude (a common English word, no CJK/Cyrillic/Arabic/Thai/Hangul). Used for phrase discovery only.
with cleaned as (
    select
        source, item_id, item_type, channel_id, title,
        coalesce(published_at, first_seen_at) as seen_at,
        btrim(regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(lower(coalesce(title, '')), 'https?://\S+|www\.\S+', ' ', 'g'),
                        '[''’]s\M', '', 'g'),
                    '[^[:alnum:]]+', ' ', 'g'),
                '\m(grand theft auto|gta) ?(vi|6)\M', 'gta 6', 'g'),
            '\m(grand theft auto|gta) ?(v|5)\M', 'gta 5', 'g')) as clean_text
    from {{ ref('stg_items') }}
    where item_type <> 'channel'
)

select
    *,
    clean_text ~ '\m(the|and|is|are|was|to|of|in|for|on|with|this|that|you|your|it|what|how|why|just|will|has|have|about|from|my|we|they|got|before|after|when)\M'
        and coalesce(title, '') !~ '[Ѐ-ӿ؀-ۿ฀-๿぀-ヿ一-鿿가-힯]'
        as is_english
from cleaned
