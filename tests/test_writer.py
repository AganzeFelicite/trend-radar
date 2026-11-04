"""AI writing with a fake Claude: no API calls."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_api import marts

from trend_radar import brief, writer
from trend_radar.db import ConnectorRun, Draft, engine

GOOD = writer.Drafts(
    email_subject="{{t1.name}} leads GTA 6 talk",
    email_body="{{t1.name}} is at {{t1.rank}} with {{t1.score}} out of 100. Study {{video1.title}} by {{video1.channel}}.",
    telegram="Top 5 today: {{t1.name}} ({{t1.score}}).",
    today="{{t1.name}} holds {{t1.share}} of the GTA 6 conversation in the last 24 hours.",
    scripts=[writer.Script(format="daily_radar", hook="One topic owns GTA 6 today.",
                           what_the_data_shows="{{t1.name}} scores {{t1.score}}.", why_it_matters="Viewers want it.",
                           what_next="Watch whether {{t1.name}} holds.")],
)


def fake(*replies):
    calls = []

    def caller(system, user):
        calls.append(user)
        return replies[len(calls) - 1], 30_000, 2_000  # tokens in, out
    return caller, calls


def drafts():
    with Session(engine) as s:
        return {d.kind: d for d in s.scalars(select(Draft))}


def last_run():
    with Session(engine) as s:
        return s.scalars(select(ConnectorRun).where(ConnectorRun.source == "writer").order_by(ConnectorRun.id.desc())).first()


def test_validator_rejects_invented_numbers_unknown_placeholders_and_topics_outside_the_brief():
    allowed = {"t1.name", "t1.score"}
    assert writer.problems("{{t1.name}} hit {{t1.score}} in GTA 6, top 5, 24 hours, out of 100", allowed, ["quiet"]) == []
    assert writer.problems("{{t1.name}} hit 92 today", allowed, []) == ["number typed instead of a placeholder: '92'"]
    assert writer.problems("Top 5:\n1. {{t1.name}}\n2) {{t1.name}}", allowed, []) == []  # list markers are formatting
    assert writer.problems("Ranked 1. {{t1.name}}", allowed, []) != []  # but not mid-line
    assert writer.problems("{{t1.score}} and {{t9.score}}", allowed, []) == ["unknown placeholder {{t9.score}}"]
    assert writer.problems("Also watch the Quiet Zone", allowed, ["quiet zone"]) == ["topic not in the brief: 'quiet zone'"]
    assert writer.fill("{{t1.name}}: {{t1.score}}", {"t1.name": "Pre-load", "t1.score": "80"}) == "Pre-load: 80"


def test_write_retries_a_rejected_draft_then_stores_filled_text_and_cost():
    marts()
    brief.build()
    bad = GOOD.model_copy(update={"telegram": "Pre-load hits 92 today!"})  # invented number
    caller, calls = fake(bad, GOOD)

    writer.write(caller)

    assert len(calls) == 2 and "number typed instead of a placeholder: '92'" in calls[1]
    d = drafts()
    assert set(d) == {"email", "telegram", "today", "script_daily_radar"}
    assert all(x.status == "draft" for x in d.values())
    assert d["telegram"].text == "Top 5 today: Pre-load (80)." and d["telegram"].template.startswith("Top 5 today: {{t1.name}}")
    assert "Pre-load guide by Small" in d["email"].text  # breakout video filled in the email
    run = last_run()
    assert (run.status, run.quota_used) == ("ok", 2 * (30_000 * 0.10 + 2_000 * 0.50))  # micro-dollars, both calls


def test_video_in_a_script_is_flagged_after_the_retry():
    marts()
    brief.build()
    leaky = GOOD.model_copy(update={"scripts": [GOOD.scripts[0].model_copy(update={"hook": "Look at {{video1.title}}"})]})
    caller, calls = fake(leaky, leaky)

    writer.write(caller)

    d = drafts()["script_daily_radar"]
    assert d.status == "flagged" and "unknown placeholder {{video1.title}}" in d.problems
    assert (last_run().status, len(calls)) == ("partial", 2)


def test_cap_reached_means_no_call():
    marts()
    brief.build()
    with Session(engine) as s:  # $3.999 already spent this month
        s.add(ConnectorRun(source="writer", job="drafts", status="ok", items_count=0, quota_used=3_999_000))
        s.commit()
    caller, calls = fake(GOOD)

    writer.write(caller)

    assert calls == [] and drafts() == {}
    run = last_run()
    assert run.status == "capped" and "cap $4.00 reached ($4.00 spent" in run.error


def test_script_facts_carry_movement_and_only_segment_topics_are_allowed():
    marts()
    brief.build()
    with Session(engine) as s:
        b = brief.Brief.model_validate(s.scalars(select(brief.DailyBrief)).one().json)
    f = writer.facts(b)
    assert f["t1.movement"] == "not in the ranking 6 hours ago" and f["movement"] == "some"
    caller, _ = fake(GOOD.model_copy(update={"scripts": [GOOD.scripts[0].model_copy(update={"hook": "{{pick.name}} rises"})]}),
                     GOOD.model_copy(update={"scripts": [GOOD.scripts[0].model_copy(update={"hook": "{{pick.name}} rises"})]}))
    writer.write(caller)
    assert "unknown placeholder {{pick.name}}" in drafts()["script_daily_radar"].problems  # pick isn't a segment
