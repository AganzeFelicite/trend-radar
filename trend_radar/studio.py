"""Content Package (P9.5) for the owner's Video Studio: package() = the machine-readable package, markdown() = the
text the owner pastes into their video AI. Template only, no AI: every number comes from the Daily Brief.

Rules from the review of the first sample (Nov 4):
- facts are `verified` (our data, listed here) or `official` (added during research, primary-source URL only);
- topics sharing more than half their trending items become one segment;
- a "riser" segment only for real movement (config RISER_*; the brief applies it);
- each topic's rank change is stated; `movement: none` when no top topic moved ("still leading");
- 40 s by default, at most 3 segments plus hook and close;
- the host is the Video Studio's character (config HOST_NAME); Trend Radar is the data brand;
- comments are read through official APIs only; piracy/jailbreak/leak/cheat items never reach the research list.
"""

import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from trend_radar import config
from trend_radar.brief import Brief, Lead, TopicFact, VideoFact

FORMAT = "daily_radar"
BLOCKED = re.compile(config.PACKAGE_BLOCKED_WORDS, re.I)
EXCLUDED = re.compile(config.RESEARCH_EXCLUDE_WORDS, re.I)
TITLE_BANNED = '"confirmed", "leaked", "insane"'

RULES = [
    "No third-party clips or thumbnails in the video. The videos, posts and headlines in the research list are for "
    "reading and citing only.",
    "No Rockstar/GTA logos, art, screenshots, characters or music.",
    "The host is a stylised, clearly-AI character, never a realistic human. Trend Radar is the data source, not the host.",
    "The platform AI label must be switched on when posting (YouTube altered/synthetic content; TikTok AI-generated).",
    "Only `verified` facts (listed in this package) and `official` facts (from Rockstar Newswire, PlayStation, Xbox or "
    "a store page, with the primary-source URL; short links resolved; never a news site as the source) may be said or "
    "shown as numbers or dates.",
    "Anything else from research is cited and marked `unverified-context`, and is never shown as a number.",
    "No sensational claims: no \"leaked\", \"confirmed\", \"cancelled\" or \"delayed\" framing unless an official "
    "source says so; no fake urgency.",
    f"Titles never use {TITLE_BANNED} or all-caps words, and differ from the previous titles listed in this package.",
    "No finance, money-making, health or legal topics. Nothing about piracy, jailbreaks, leaks or cheats.",
    "Read comments and replies only through official APIs: YouTube Data API (commentThreads.list) and the Bluesky API "
    "(app.bsky.feed.getPostThread). No scraping.",
    "Never show or say commenters' names or handles; paraphrase what they say.",
]


class Fact(BaseModel):
    id: str
    type: Literal["verified", "official"]
    label: str
    value: str
    source: str  # verified: our table · topic · metric · hour. official: the primary-source URL


class SegmentTopic(BaseModel):
    key: str  # placeholder prefix in the writer's facts (t1..t5, riser)
    topic: TopicFact
    movement: str  # 6h rank change, in words
    fact_ids: list[str]


class Segment(BaseModel):
    label: str
    kind: Literal["top", "riser"]
    topics: list[SegmentTopic]
    keywords: list[str]
    leads: list[Lead]
    questions: list[str]


class Scene(BaseModel):
    start: int
    end: int
    voice: str
    screen: str


class Card(BaseModel):
    file: str
    shows: str
    rendered: bool = False  # data-card rendering isn't built yet: the Video Studio draws it from the facts


class OfficialSource(BaseModel):
    url: str
    found_in: str
    truncated: bool


class ContentPackage(BaseModel):
    package_id: str
    format: str
    language: str
    host: str
    data_brand: str
    target_length_seconds: int
    status: str
    brief_date: str
    brief_version: int
    scores_at: str
    movement: Literal["none", "some"]
    facts: list[Fact]
    segments: list[Segment]
    breakout_videos: list[VideoFact]
    official_sources_in_our_data: list[OfficialSource]
    script: str | None
    scenes: list[Scene]
    cards: list[Card]
    previous_titles: list[str]
    rules: list[str]


def allowed(t: TopicFact) -> bool:
    """P9.8 sensitive-topic filter (blocklist; the AI classifier tag comes later)."""
    return t.slug not in config.PACKAGE_BLOCKED_TOPICS and not BLOCKED.search(t.name)


def rank_change(t: TopicFact) -> int | None:
    return t.rank_6h_ago - t.rank if t.rank and t.rank_6h_ago else None


def movement_text(t: TopicFact) -> str:
    d = rank_change(t)
    if d is None:
        return "not in the ranking 6 hours ago"
    if d == 0:
        return f"unchanged in 6 hours (still #{t.rank})"
    places = f"{abs(d)} place{'s' if abs(d) != 1 else ''}"
    return f"{'up' if d > 0 else 'down'} {places} in 6 hours (#{t.rank_6h_ago} → #{t.rank})"


def overlap(a: set[str], b: set[str]) -> float:
    """Share of the smaller topic's trending items that the other topic also has."""
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def segment_plan(b: Brief) -> list[tuple[str, list[tuple[str, TopicFact]]]]:
    """[(kind, [(key, topic), ...])]: top topics in rank order, overlapping ones merged (2 per segment at most, a
    third overlapping one is dropped for the next distinct topic), the riser (if any) in the last slot."""
    items = {slug: set(e.items) for slug, e in b.evidence.items()}
    r = b.biggest_riser
    riser = r if r and allowed(r) and r.slug not in {t.slug for t in b.top5} else None
    room = config.PACKAGE_MAX_SEGMENTS - (1 if riser else 0)
    plan: list[list[tuple[str, TopicFact]]] = []
    for i, t in enumerate(b.top5, 1):
        if not allowed(t):
            continue
        twin = next((seg for seg in plan if any(overlap(items.get(t.slug, set()), items.get(x.slug, set()))
                                                > config.TOPIC_OVERLAP_MERGE for _, x in seg)), None)
        if twin is not None:
            if len(twin) < 2:
                twin.append((f"t{i}", t))
        elif len(plan) < room:
            plan.append([(f"t{i}", t)])
    return [("top", seg) for seg in plan] + ([("riser", [("riser", riser)])] if riser else [])


def _questions(label: str, kind: str, topics: list[TopicFact]) -> list[str]:
    q = [f"What is actually happening with {label}? For every official statement give the primary-source URL "
         "(Rockstar Newswire, PlayStation, Xbox or the store page; resolve short links; a news article is never the "
         "source of an official fact) and tag it `official`. Everything else is `unverified-context`.",
         "The 3 questions, complaints or claims that come up most in the comments and replies of the items below "
         "(read through the YouTube Data API and the Bluesky API only; paraphrase; no usernames; rough share).",
         "What do the top videos have in common (angle, title, hook in the first 5 seconds), and what do viewers say "
         "is missing? That gap is our angle."]
    if kind == "riser":
        q.append(f"It climbed {movement_text(topics[0])}: which video, post or headline started it?")
    return q


def package(b: Brief, script: str | None, brief_version: int, brief_status: str,
            previous_titles: list[str] | None = None) -> ContentPackage:
    at = f"{b.scores_at:%Y-%m-%d %H:%M} UTC"
    facts: list[Fact] = []
    segments: list[Segment] = []
    for kind, members in segment_plan(b):
        seg_topics, keywords, leads, seen = [], [], [], set()
        for key, t in members:
            ids = []
            for metric, label, value in (
                    ("public_rank", "rank", f"#{t.rank}"),
                    ("public_rank_6h_ago", "rank 6 hours ago", f"#{t.rank_6h_ago}" if t.rank_6h_ago else None),
                    ("score", "score (0-100)", f"{round(t.score)}"),
                    ("attention", "share of the GTA 6 conversation, 24h", f"{t.share * 100:.1f}%"),
                    ("sources", "sources it's active on", str(t.sources)),
                    ("items", "posts and videos, 24h", str(t.items)),
                    ("growth", "vs the previous 24h", f"{t.growth:.1f}x" if t.growth is not None else None)):
                if value is not None:
                    facts.append(Fact(id=f"F{len(facts) + 1}", type="verified", label=f"{t.name}: {label}", value=value,
                                      source=f"Trend Radar topic_scores · {t.slug} · {metric} · {at}"))
                    ids.append(facts[-1].id)
            seg_topics.append(SegmentTopic(key=key, topic=t, movement=movement_text(t), fact_ids=ids))
            e = b.evidence.get(t.slug)
            if e:
                keywords += [k for k in e.keywords if k not in keywords]
                for lead in e.videos + e.posts + e.news:
                    if lead.url not in seen and not EXCLUDED.search(lead.title):
                        seen.add(lead.url)
                        leads.append(lead)
        label = " & ".join(x.topic.name for x in seg_topics)
        segments.append(Segment(label=label, kind=kind, topics=seg_topics, keywords=keywords, leads=leads,
                                questions=_questions(label, kind, [x.topic for x in seg_topics])))

    top_moves = [rank_change(x.topic) for s in segments if s.kind == "top" for x in s.topics]
    movement = "none" if top_moves and all(d == 0 for d in top_moves) else "some"

    official = [OfficialSource(url=link.rstrip("…"), found_in=lead.url, truncated=link.endswith("…"))
                for s in segments for lead in s.leads for link in lead.links
                if any((urlparse(link).hostname or "").endswith(d) for d in config.OFFICIAL_DOMAINS)]

    total = config.PACKAGE_TARGET_SECONDS
    hook, close = round(total * 0.1), round(total * 0.2)
    per = (total - hook - close) // max(len(segments), 1)
    scenes, t0 = [Scene(start=0, end=hook, voice="Hook", screen=f"Title card \"GTA 6 trends · {b.date:%b} {b.date.day}\" "
                                                                f"and {config.HOST_NAME}")], hook
    cards = [Card(file="cards/title.png", shows=f"\"GTA 6 trends · {b.date:%b} {b.date.day}\", data by Trend Radar")]
    for i, s in enumerate(segments, 1):
        end = t0 + per if i < len(segments) else total - close
        cards.append(Card(file=f"cards/segment-{i}.png",
                          shows=" + ".join(f"#{x.topic.rank} {x.topic.name} · {round(x.topic.score)}/100 · "
                                           f"{x.topic.share * 100:.1f}% · {x.movement}" for x in s.topics)))
        scenes.append(Scene(start=t0, end=end, voice=f"{s.label}: the data, its movement, one cited finding",
                            screen=f"cards/segment-{i}.png" + (" (rank-movement chart)" if s.kind == "riser" else "")))
        t0 = end
    scenes.append(Scene(start=total - close, end=total, voice="Why it matters, the owner's line (4 s), what to watch",
                        screen="Host close-up with the owner's line as a caption, then cards/end.png"))
    cards.append(Card(file="cards/end.png", shows="\"Daily GTA 6 trends · AI host, real data · Trend Radar\""))

    return ContentPackage(
        package_id=f"{b.date}-{FORMAT}-en-v{brief_version}", format=FORMAT, language="en", host=config.HOST_NAME,
        data_brand="Trend Radar", target_length_seconds=total,
        status="approved" if brief_status == "approved" else "not approved (preview: don't publish)",
        brief_date=str(b.date), brief_version=brief_version, scores_at=at, movement=movement, facts=facts,
        segments=segments, breakout_videos=[v for v in b.breakout_videos if not EXCLUDED.search(v.title)],
        official_sources_in_our_data=official, script=script, scenes=scenes, cards=cards,
        previous_titles=previous_titles or [], rules=RULES,
    )


def markdown(p: ContentPackage) -> str:
    seg_md = []
    for i, s in enumerate(p.segments, 1):
        head = f"### Segment {i}: {s.label}" + (" (riser)" if s.kind == "riser" else "")
        lines = [head] + [f"- {x.topic.name}: #{x.topic.rank}, score {round(x.topic.score)}, {x.movement} "
                          f"(facts {', '.join(x.fact_ids)})" for x in s.topics]
        if s.keywords:
            lines.append(f"- What people call it: {', '.join(s.keywords)}")
        if s.leads:
            lines.append("\nStart here: the trending items under this topic. Read them, and their comments and replies "
                         "through the official APIs:")
            lines += [f"- \"{x.title}\" · {x.by} · {x.metric} · {x.url}" for x in s.leads]
        lines.append("\nFind out:")
        lines += [f"{n}. {q}" for n, q in enumerate(s.questions, 1)]
        seg_md.append("\n".join(lines))

    official = "\n".join(f"- {o.url}{' (truncated in the post: find the full page)' if o.truncated else ''} · found in "
                         f"{o.found_in}" for o in p.official_sources_in_our_data) or "- none found in today's items"
    breakout = "\n".join(f"- \"{v.title}\" · {v.channel} · {v.views_24h:,} views in 24h, {v.times_subscribers:g} times "
                         f"the channel's subscribers · {v.url}" for v in p.breakout_videos) or "- none today"
    script = ("\n".join("> " + line if line else ">" for line in p.script.splitlines()) if p.script else
              "No script draft yet: write one from the verified facts (hook → what the data shows → why it matters → "
              "what to watch next).")
    framing = ("**Movement: none.** No top topic changed rank in 6 hours: say they are *still leading* or *holding*, "
               "never that they are rising." if p.movement == "none" else
               "**Movement: some.** Say each topic's rank change exactly as listed.")

    return f"""# Video package: {p.format} · {p.brief_date}

| | |
|---|---|
| package_id | `{p.package_id}` |
| format | {p.format} |
| language | {p.language} |
| host | {p.host} (the Video Studio's character) |
| data brand | {p.data_brand} |
| target length | {p.target_length_seconds} s (hook, at most {config.PACKAGE_MAX_SEGMENTS} segments, close) |
| status | **{p.status}** |
| built from | Daily Brief v{p.brief_version}, scores at {p.scores_at}, last 24 hours |
| movement | {p.movement} |
| data cards | {", ".join(f"`{c.file}`" for c in p.cards)} (not rendered yet: draw them from the facts in our style) |
| previous titles | {"; ".join(p.previous_titles) or "none published yet"} |

You are the research and production assistant for **{p.host}**, a stylised AI host who tells GTA 6 creators which \
topics are rising, using data from **{p.data_brand}** (YouTube, Bluesky and gaming news, collected hourly through \
official APIs). Make one {p.target_length_seconds}-second vertical video (1080×1920) in English.

Work in two phases:
1. **Research** (section 2). Then stop and report your findings.
2. **Production** (section 3), after the report is reviewed.

## 1. Facts

Two kinds of fact may be said or shown as numbers or dates:
- `verified`: our data, listed below.
- `official`: from Rockstar Newswire, PlayStation, Xbox or a store page, added by you during research with the \
primary-source URL (resolve short links like bit.ly; never cite a news site as the source of an official fact).

| ID | Type | Fact | Value | Source |
|---|---|---|---|---|
{chr(10).join(f"| {f.id} | {f.type} | {f.label} | {f.value} | {f.source} |" for f in p.facts)}

{framing}

## 2. Research

Goal: find out **why** each topic is moving and **what viewers want to know**. Read comments and replies only through \
official APIs: YouTube Data API (`commentThreads.list`) and the Bluesky API (`app.bsky.feed.getPostThread`). Items \
about piracy, jailbreaks, leaks or cheats have been removed; don't research them.

{chr(10).join(chr(10) + m for m in seg_md).strip()}

### Official sources seen in our data
Check these first for `official` facts:
{official}

### Breakout videos: study why these work
Small channels getting far more views than they have subscribers. Note their title, hook and format; don't copy or \
show them.
{breakout}

**Report format:** for each segment, bullets of findings, each with a source link and a tag: `official` (primary \
source URL), `verified` (one of our facts) or `unverified-context`. End with one suggested angle per segment.

## 3. Production

**Script** (today's draft; keep its facts and framing, tighten to {p.target_length_seconds} s, add at most one cited \
finding per segment):
{script}

**Owner's line:** [OWNER COMMENTARY: added on the approval page. Leave a 4-second slot.]

| Time | Voice | On screen (our own graphics only) |
|---|---|---|
{chr(10).join(f"| {s.start}-{s.end}s | {s.voice} | {s.screen} |" for s in p.scenes)}

**Graphics:** our own style. Dark background, one green accent, bold monospaced numbers, simple bars and lines. No game \
art, logos, screenshots or thumbnails.

**Deliver:** the MP4 (1080×1920, {p.target_length_seconds} s or less, captions burned in); 3 title options (never \
{TITLE_BANNED} or all-caps words, different from the previous titles above); a caption that includes "AI host powered \
by real-time GTA 6 trend data from Trend Radar"; 3-5 hashtags.

## 4. Rules (non-negotiable)

{chr(10).join(f"- {r}" for r in p.rules)}
"""
