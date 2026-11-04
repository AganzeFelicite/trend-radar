-- Aliases are plain lowercase words (they go straight into a regex), slugs are url-safe,
-- and one alias can't point at two topics.
select alias, 'bad format' as problem from {{ ref('topic_aliases') }}
where alias !~ '^[a-z0-9]+( [a-z0-9]+)*$' or topic_slug !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
union all
select alias, 'duplicate alias' from {{ ref('topic_aliases') }} group by alias having count(*) > 1
