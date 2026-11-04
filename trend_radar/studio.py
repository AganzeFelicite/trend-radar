"""Video Studio brief (the "ready-made prompts" of P9.5): the text the owner hands to their own AI video system.
It says what our data shows (verified facts, each with its source), what to research and where to start (the trending
videos, posts and headlines under each topic, plus the breakout videos), how to build the video, and the rules.
Template only, no AI: every number in it comes from the Daily Brief.
"""

import re

from trend_radar import config
from trend_radar.brief import Brief, TopicFact

BLOCKED = re.compile(config.PACKAGE_BLOCKED_WORDS, re.I)

RULES = """- No third-party clips or thumbnails in the video. The videos, posts and headlines in the research section are \
for reading and citing only.
- No Rockstar/GTA logos, art, screenshots, characters or music.
- RADAR is a stylised, clearly-AI host, never a realistic human.
- The platform AI label must be switched on when posting (YouTube altered/synthetic content; TikTok AI-generated).
- No sensational claims: no "leaked", "confirmed", "cancelled" or "delayed" unless an official source says so (cite it); \
no fake urgency.
- No finance, money-making, health or legal topics.
- Any extra research must be cited and marked `unverified-context`. Only numbers from "Verified facts" may be shown or \
said as numbers.
- Never show or say commenters' names or handles; paraphrase what they say."""


def allowed(t: TopicFact) -> bool:
    """P9.8 sensitive-topic filter (blocklist; the AI classifier tag comes later)."""
    return t.slug not in config.PACKAGE_BLOCKED_TOPICS and not BLOCKED.search(t.name)


def _facts(b: Brief, topics: list[TopicFact]) -> list[str]:
    at = f"{b.scores_at:%Y-%m-%d %H:%M} UTC"
    rows = []
    for t in topics:
        for metric, label, value in (("public_rank", "rank", f"#{t.rank}"), ("score", "score (0-100)", f"{round(t.score)}"),
                                     ("attention", "share of the GTA 6 conversation, 24h", f"{t.share * 100:.1f}%"),
                                     ("sources", "sources it's active on", str(t.sources)),
                                     ("items", "posts and videos, 24h", str(t.items)),
                                     ("public_rank_6h_ago", "rank 6 hours ago", f"#{t.rank_6h_ago}" if t.rank_6h_ago else None),
                                     ("growth", "vs the previous 24h", f"{t.growth:.1f}x" if t.growth is not None else None)):
            if value is None:
                continue
            rows.append(f"| F{len(rows) + 1} | {t.name}: {label} | {value} | topic_scores · {t.slug} · {metric} · {at} |")
    return rows


def _research(b: Brief, t: TopicFact, why: str) -> str:
    e = b.evidence.get(t.slug)
    lines = [f"### {t.name}  ({why}: #{t.rank}, score {round(t.score)}, {t.share * 100:.1f}% of the conversation, "
             f"active on {t.sources} sources)"]
    if e and e.keywords:
        lines.append(f"What people call it: {', '.join(e.keywords)}")
    if e and (e.videos or e.posts or e.news):
        lines.append("Start here: the trending items under this topic. Read them and their comments/replies:")
        lines += [f"- Video: \"{v.title}\" · {v.by} · {v.metric} · {v.url}" for v in e.videos]
        lines += [f"- Bluesky post: \"{p.title}\" · {p.metric} · {p.url}" for p in e.posts]
        lines += [f"- News: \"{n.title}\" · {n.by} · {n.metric} · {n.url}" for n in e.news]
    lines += ["Find out:",
              f"1. What is actually happening with {t.name}? Separate official statements (Rockstar Newswire, platform "
              "holders, store pages) from rumours and speculation. Cite each.",
              "2. The 3 questions, complaints or claims that come up most in the comments and replies above "
              "(paraphrase, no usernames, rough share of comments).",
              "3. What do the top videos have in common (angle, title, hook in the first 5 seconds), and what do viewers "
              "say is missing? That gap is the angle for our video."]
    if t.rank_6h_ago and t.rank and t.rank_6h_ago > t.rank:
        lines.append(f"4. It climbed from #{t.rank_6h_ago} to #{t.rank} in 6 hours: which video, post or headline started it?")
    return "\n".join(lines)


def daily_radar(b: Brief, script: str | None, brief_version: int, brief_status: str) -> str:
    top3 = [t for t in b.top5 if allowed(t)][:3]
    r = b.biggest_riser
    riser = r if r and allowed(r) and r.slug not in {t.slug for t in top3} else None
    topics = top3 + ([riser] if riser else [])
    facts = _facts(b, topics)
    day = f"{b.date:%B} {b.date.day}, {b.date.year}"
    status = "APPROVED" if brief_status == "approved" else "NOT APPROVED YET (preview: don't publish from this)"

    research = [_research(b, t, f"top {i}") for i, t in enumerate(top3, 1)]
    if riser:
        research.append(_research(b, riser, "biggest riser"))
    breakout = "\n".join(f"- \"{v.title}\" · {v.channel} · {v.views_24h:,} views in 24h, {v.times_subscribers:g} times "
                         f"the channel's subscribers · {v.url}" for v in b.breakout_videos)

    scenes = [("0-5s", "Hook", f"Title card: \"GTA 6 Radar · {b.date:%b} {b.date.day}\" and the RADAR host")]
    slots = ["5-20s", "20-32s", "32-44s"]
    for slot, t in zip(slots, top3):
        scenes.append((slot, f"{t.name}: what the data shows, plus one cited finding",
                       f"Ranking card: #{t.rank} {t.name} · {round(t.score)}/100 · {t.share * 100:.1f}% of the conversation"))
    if riser:
        scenes.append(("44-50s", f"Riser: {riser.name}", f"Rank-movement chart: {riser.name} #{riser.rank_6h_ago} → #{riser.rank}"))
    scenes += [("50-55s", "Why it matters + owner's line", "Host close-up, caption of the owner's line"),
               ("55-60s", "What to watch / make next", "End card: \"Daily GTA 6 trends · AI anchor, real data\"")]

    script_block = ("\n".join("> " + line if line else ">" for line in script.splitlines()) if script else
                    "No script draft yet: write one from the verified facts, following hook → what the data shows → why "
                    "it matters → what to watch or make next.")

    return f"""# RADAR video brief: Daily Radar · {day}

Built from Trend Radar's Daily Brief v{brief_version} (scores at {b.scores_at:%H:%M} UTC, last {b.window_hours} hours). \
Status: **{status}**

You are the research and production assistant for **RADAR**, a stylised AI news anchor that tells GTA 6 creators \
which topics are rising, using Trend Radar's data (YouTube, Bluesky and gaming news, collected hourly through official \
APIs). Make one 60-second vertical video (1080×1920) in English.

Work in two phases:
1. **Research** (section 2). Then stop and report your findings in the format below.
2. **Production** (section 3), after the report is reviewed. Use findings only where they are cited.

## 1. Verified facts: the only numbers you may show or say

| ID | Fact | Value | Source |
|---|---|---|---|
{chr(10).join(facts)}

## 2. Research

Goal: find out **why** each topic is moving and **what viewers want to know**, so the video adds something a ranking \
can't. The trending videos under each topic are your starting point: read them, their comments, and the replies.

{chr(10).join(chr(10) + r for r in research).strip()}

### Breakout videos: study why these work
Small channels getting far more views than they have subscribers. Note their title, hook and format; don't copy or show \
them.
{breakout or "- none today"}

**Report format:** for each topic, bullets of findings. Each bullet has a source link and a tag: `verified` (an \
official source, or one of our facts above) or `unverified-context`. End with one suggested angle per topic.

## 3. Production

**Script** (today's draft; keep its facts, tighten the wording if needed, add at most one cited finding per topic):
{script_block}

**Owner's line:** [OWNER COMMENTARY: added on the approval page. Leave a 4-second slot for it.]

| Time | Voice | On screen (our own graphics only) |
|---|---|---|
{chr(10).join(f"| {a} | {v} | {s} |" for a, v, s in scenes)}

**Graphics:** our own style. Dark background, one green accent, bold monospaced numbers, simple bars and lines. No game \
art, logos, screenshots or thumbnails.

**Deliver:** the MP4 (1080×1920, 60 seconds or less, captions burned in); 3 title options (no "leaked", "confirmed", \
"insane", no all-caps); a caption that includes "AI anchor powered by real-time GTA 6 trend data"; 3-5 hashtags.

## 4. Rules (non-negotiable)

{RULES}
"""
