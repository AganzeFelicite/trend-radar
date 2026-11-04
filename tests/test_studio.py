from test_api import client, marts

from trend_radar import brief, studio
from trend_radar.brief import TopicFact


def test_studio_prompt_has_verified_facts_research_leads_and_rules():
    marts()
    brief.build()

    md = client.get("/api/admin/studio-prompt").text

    assert "| F1 | Pre-load: rank | #1 | topic_scores · preload · public_rank · 2026-11-04 05:00 UTC |" in md
    assert '- Video: "Pre-load guide" · Small · 50,000 views in 24h · https://y/v1' in md  # trending under the topic
    assert '- News: "Pre-load starts Nov 10" · IGN' in md
    assert "Bluesky post: \"Pre-loading now\" · 40 likes, reposts and replies in 24h" in md
    assert "What people call it: pre load, november 10" in md
    assert "### Breakout videos" in md and "Map tour" in md
    assert "NOT APPROVED YET" in md and "No script draft yet" in md
    assert studio.RULES in md
    assert client.get("/api/admin/studio-prompt?download=1").headers["content-disposition"].endswith('.md"')


def test_sensitive_topics_never_reach_a_package():
    t = dict(rank=1, rank_6h_ago=None, score=50, share=0.1, growth=None, sources=3, items=9, channels=9)
    assert not studio.allowed(TopicFact(slug="mark-tilbury-savings", name="Mark Tilbury Savings", **t))
    assert not studio.allowed(TopicFact(slug="crypto-scam", name="Crypto Investing", **t))
    assert studio.allowed(TopicFact(slug="preload", name="Pre-load", **t))
