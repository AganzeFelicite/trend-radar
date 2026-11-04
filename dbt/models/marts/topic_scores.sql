-- Grain: one topic x hour, last 7 days (the topic-page chart and alert history). Full rebuild, so late data restates
-- recent hours. Formula, flags and worked example: docs/SCORING.md.
--   Per source, the topic's share of that source's GTA activity (each source against its own baseline, so views,
--   likes and headlines become comparable) in three windows ending at scored_at:
--   now = last 24h, prev = the 24h before, burst = last 3h.
--   attention = weighted average of the "now" shares (seeds/source_weights.csv) over sources live in the window.
--   growth = like-for-like now vs prev, over sources we were already collecting when the prev window opened
--   (first ok run in connector_runs); 1 until such a source exists, so day one isn't all "4x growth".
--   momentum = attention x growth (growth capped to 0.25..4): size x speed.
--   score = momentum on a 0-100 scale, Google-Trends style: 100 = the strongest topic-hour of the last 7 days that
--   had 5+ items (one lone old article = 100% share of an empty hour must not set the scale); capped at 100.
--   rank = momentum rank over every topic. public_rank = what the site shows: the top 5 are the 5 best topics with
--   activity on var('top5_min_sources')+ sources (in_top5); everything else follows by momentum. Topics the owner
--   flagged off-topic (off_topic_flags) get no public_rank; the site lists them apart as "Off-topic buzz".
{% set w = var('momentum_window_hours') %}
{% set b = var('burst_window_hours') %}
with collecting as (  -- when each source started: windows before this hold only back-dated first readings
    select source, min(started_at) as since
    from {{ source('warehouse', 'connector_runs') }}
    where status in ('ok', 'partial')
    group by 1
),

spine as (  -- hours since collection started, at most 7 days
    select generate_series(
        greatest(date_trunc('hour', now()) - interval '7 days',
                 (select date_trunc('hour', min(since)) from collecting
                  where source in (select source from {{ ref('source_weights') }} where weight > 0))),
        date_trunc('hour', now()), interval '1 hour') as scored_at
),

-- ponytail: range join (each activity row x every hour whose windows contain it); fine to a few million rows.
win as (
    select
        s.scored_at, a.source, a.item_id, a.channel_id, a.activity,
        a.hour > s.scored_at - interval '{{ w }} hours' as in_now,
        a.hour > s.scored_at - interval '{{ b }} hours' as in_burst
    from spine s
    join {{ ref('int_item_activity') }} a
      on a.hour > s.scored_at - interval '{{ 2 * w }} hours' and a.hour <= s.scored_at
    where a.activity > 0  -- items = items that gained attention in the window
),

totals as (  -- per source and hour: all GTA activity (topic or not) = the source's baseline
    select
        w.scored_at, w.source, sw.weight,
        sum(activity) filter (where in_now) as total_now,
        case when max(c.since) <= w.scored_at - interval '{{ 2 * w }} hours'
             then sum(activity) filter (where not in_now) end as total_prev,
        sum(activity) filter (where in_burst) as total_burst
    from win w
    join {{ ref('source_weights') }} sw on sw.source = w.source
    left join collecting c on c.source = w.source
    where sw.weight > 0
    group by 1, 2, 3
),

live_weight as (  -- denominators: weights of the sources that have data in each window
    select
        scored_at,
        nullif(sum(weight) filter (where total_now > 0), 0) as now_w,
        nullif(sum(weight) filter (where total_now > 0 and total_prev > 0), 0) as lfl_w,
        nullif(sum(weight) filter (where total_burst > 0), 0) as burst_w
    from totals
    group by 1
),

per_source as (
    select
        w.scored_at, ti.topic_slug, w.source, t.weight,
        coalesce(sum(activity) filter (where in_now) / nullif(t.total_now, 0), 0) as share_now,
        coalesce(sum(activity) filter (where not in_now) / nullif(t.total_prev, 0), 0) as share_prev,
        coalesce(sum(activity) filter (where in_burst) / nullif(t.total_burst, 0), 0) as share_burst,
        t.total_now > 0 as live_now,
        t.total_now > 0 and t.total_prev > 0 as live_both,
        t.total_burst > 0 as live_burst,
        count(distinct w.item_id) filter (where in_now) as items_now,
        count(distinct w.item_id) filter (where not in_now) as items_prev,
        count(distinct w.item_id) filter (where in_burst) as items_burst,
        count(distinct w.channel_id) filter (where in_now) as channels_now,
        count(distinct w.channel_id) filter (where in_burst) as channels_burst
    from win w
    join {{ ref('topic_items') }} ti on ti.source = w.source and ti.item_id = w.item_id
    join totals t on t.scored_at = w.scored_at and t.source = w.source
    group by 1, 2, 3, 4, t.total_now, t.total_prev, t.total_burst
),

topic as (
    select
        p.scored_at, p.topic_slug,
        sum(weight * share_now) filter (where live_now) / max(lw.now_w) as attention,
        sum(weight * share_now) filter (where live_both) / max(lw.lfl_w) as attention_lfl,
        sum(weight * share_prev) filter (where live_both) / max(lw.lfl_w) as prev_attention,
        sum(weight * share_burst) filter (where live_burst) / max(lw.burst_w) as burst_attention,
        sum(items_now) as items,
        sum(items_prev) as items_prev,
        sum(items_burst) as items_burst,
        sum(channels_now) as channels,
        sum(channels_burst) as channels_burst,
        count(*) filter (where items_now > 0) as sources,
        -- rising on a source: share up 20%+ vs the previous window, with 2+ items there now
        count(*) filter (where live_both and items_now >= 2 and share_now > 1.2 * share_prev) as rising_sources,
        max(lw.lfl_w) is not null as has_prev
    from per_source p
    join live_weight lw on lw.scored_at = p.scored_at
    group by 1, 2
),

scored as (
    select
        *,
        case when prev_attention is null then 1.0
             else least(greatest((attention_lfl + 0.005) / (prev_attention + 0.005), 0.25), 4.0) end as growth
    from topic
),

final as (
select
    scored_at,
    topic_slug,
    round(least(100, 100 * coalesce(attention, 0) * growth
                / nullif(max(coalesce(attention, 0) * growth) filter (where items >= 5) over (), 0))::numeric, 1) as score,
    rank() over (partition by scored_at order by coalesce(attention, 0) * growth desc) as rank,
    coalesce(attention, 0) * growth as momentum,
    coalesce(attention, 0) as attention,
    prev_attention,
    growth,
    burst_attention,
    items, items_prev, items_burst, channels, sources, rising_sources,
    has_prev and items_prev = 0 and items >= 3 as is_new,
    burst_attention >= 0.01 and burst_attention >= 2 * attention and items_burst >= 3 and channels_burst >= 2 as is_spiking,
    rising_sources >= 2 as is_confirmed,
    topic_slug in (select topic_slug from {{ source('warehouse', 'off_topic_flags') }}) as is_off_topic
from scored
),

top5 as (
    select
        *,
        not is_off_topic and sources >= {{ var('top5_min_sources') }}
          and row_number() over (partition by scored_at, not is_off_topic and sources >= {{ var('top5_min_sources') }}
                                 order by momentum desc, topic_slug) <= 5 as in_top5
    from final
)

select
    *,
    case when not is_off_topic then
        row_number() over (partition by scored_at, is_off_topic order by in_top5 desc, momentum desc, topic_slug)
    end as public_rank
from top5
