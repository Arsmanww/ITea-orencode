"""Реестр, журнал действий, связь тренер–спортсмен, санкции, справочник типов, ЕВСК в протоколе, календарь «подходят мне»."""

from datetime import date, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.models import CoachAthleteLink, CoachProfile, Notification, Rank, RankRequirement
from app.models.enums import CompetitionLevel, LinkStatus, NotificationKind, RoleCode
from tests.helpers import add_result, auth, make_age_group, make_athlete, make_competition, make_discipline, make_user, publish_protocol

API = "/api/v1"
START = date(date.today().year + 2, 6, 15)


@pytest_asyncio.fixture
async def world(session):
    algo = await make_discipline(session, "algorithmic")
    robo = await make_discipline(session, "robotics", "Программирование робототехники")
    teens = await make_age_group(session, "14–17 лет", 14, 17)
    admin = await make_user(session, [RoleCode.FEDERATION])
    coach = await make_user(session, [RoleCode.COACH], last_name="Тренеров")
    session.add(CoachProfile(user_id=coach.id))
    teen = await make_athlete(session, algo, birth=date(START.year - 15, 3, 1))
    adult = await make_athlete(session, robo, birth=date(START.year - 30, 3, 1))
    await session.flush()
    return {"algo": algo, "robo": robo, "teens": teens, "admin": admin, "coach": coach, "teen": teen, "adult": adult}


async def test_registry_filters_and_visibility(client, world):
    fed = auth(world["admin"], RoleCode.FEDERATION)
    r = await client.get(f"{API}/registry/athletes", params={"discipline_id": world["algo"].id}, headers=fed)
    assert r.status_code == 200
    ids = {a["id"] for a in r.json()["items"]}
    assert world["teen"].id in ids and world["adult"].id not in ids
    assert all(a["email"] for a in r.json()["items"])

    r = await client.get(f"{API}/registry/athletes", params={"q": world["teen"].last_name}, headers=auth(world["coach"], RoleCode.COACH))
    assert r.status_code == 200 and r.json()["total"] == 1
    assert r.json()["items"][0]["email"] is None  # тренеру контакты не отдаются

    assert (await client.get(f"{API}/registry/athletes", headers=auth(world["teen"], RoleCode.ATHLETE))).status_code == 403
    assert (await client.get(f"{API}/registry/coaches", headers=auth(world["coach"], RoleCode.COACH))).status_code == 403
    r = await client.get(f"{API}/registry/coaches", params={"q": "Тренеров"}, headers=fed)
    assert r.json()["total"] == 1


async def test_link_suspend_resume_end_with_history(client, session, world):
    link = CoachAthleteLink(coach_id=world["coach"].id, athlete_id=world["teen"].id, discipline_id=world["algo"].id,
                            status=LinkStatus.ACTIVE, initiated_by_user_id=world["coach"].id)
    session.add(link)
    await session.flush()
    coach, athlete = auth(world["coach"], RoleCode.COACH), auth(world["teen"], RoleCode.ATHLETE)

    r = await client.patch(f"{API}/links/{link.id}", json={"status": "suspended", "comment": "перерыв"}, headers=coach)
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    assert (await client.patch(f"{API}/links/{link.id}", json={"status": "suspended"}, headers=athlete)).status_code == 409
    assert (await client.patch(f"{API}/links/{link.id}", json={"status": "active"}, headers=athlete)).status_code == 200
    assert (await client.patch(f"{API}/links/{link.id}", json={"status": "ended"}, headers=athlete)).status_code == 200
    assert (await client.patch(f"{API}/links/{link.id}", json={"status": "active"}, headers=coach)).status_code == 409

    stranger = await make_user(session, [RoleCode.COACH])
    assert (await client.patch(f"{API}/links/{link.id}", json={"status": "ended"}, headers=auth(stranger, RoleCode.COACH))).status_code == 404

    history = (await client.get(f"{API}/links/{link.id}/history", headers=coach)).json()
    assert [(h["old_status"], h["new_status"]) for h in history] == [("active", "suspended"), ("suspended", "active"), ("active", "ended")]
    assert history[0]["comment"] == "перерыв"
    notified = (await session.scalars(select(Notification.user_id).where(Notification.kind == NotificationKind.LINK_REQUEST))).all()
    assert world["teen"].id in notified and world["coach"].id in notified


async def test_sanction_excludes_from_applications_and_is_audited(client, session, world):
    fed = auth(world["admin"], RoleCode.FEDERATION)
    comp = await make_competition(session, world["algo"], [world["teens"]], world["admin"], start=START)
    r = await client.post(f"{API}/federation/sanctions", headers=fed, json={
        "athlete_id": world["teen"].id, "kind": "disqualification", "date_from": str(date.today()), "date_to": str(START + timedelta(days=5)),
        "reason": "Нарушение регламента, рапорт главного судьи"})
    assert r.status_code == 201 and r.json()["active"] is True
    r = await client.post(f"{API}/competitions/{comp.id}/applications", json={}, headers=auth(world["teen"], RoleCode.ATHLETE))
    assert r.status_code == 422 and "дисквалификация" in r.json()["detail"]

    sanction_id = (await client.get(f"{API}/federation/sanctions", params={"active_only": True}, headers=fed)).json()[0]["id"]
    assert (await client.patch(f"{API}/federation/sanctions/{sanction_id}", json={"date_to": str(date.today() - timedelta(days=1))}, headers=fed)).status_code == 422
    assert (await client.patch(f"{API}/federation/sanctions/{sanction_id}", json={"date_to": str(date.today())}, headers=fed)).status_code == 200

    log = (await client.get(f"{API}/federation/audit-log", params={"action": "sanction."}, headers=fed)).json()
    assert [i["action"] for i in log["items"]] == ["sanction.end", "sanction.create"]
    assert log["items"][1]["user"]["id"] == world["admin"].id
    assert (await client.get(f"{API}/federation/audit-log", headers=auth(world["coach"], RoleCode.COACH))).status_code == 403
    assert (await client.post(f"{API}/federation/sanctions", headers=auth(world["coach"], RoleCode.COACH), json={})).status_code == 403


async def test_competition_types_reference(client, world):
    fed = auth(world["admin"], RoleCode.FEDERATION)
    r = await client.post(f"{API}/reference/competition-types", json={"name": "Олимпиада"}, headers=fed)
    assert r.status_code == 201
    type_id = r.json()["id"]
    assert (await client.post(f"{API}/reference/competition-types", json={"name": "олимпиада"}, headers=fed)).status_code == 409
    assert (await client.post(f"{API}/reference/competition-types", json={"name": "Кубок"}, headers=auth(world["coach"], RoleCode.COACH))).status_code == 403
    assert (await client.patch(f"{API}/reference/competition-types/{type_id}", json={"is_active": False}, headers=fed)).status_code == 200
    names = [t["name"] for t in (await client.get(f"{API}/reference/competition-types", headers=fed)).json()]
    assert "Олимпиада" not in names
    names = [t["name"] for t in (await client.get(f"{API}/reference/competition-types", params={"include_inactive": True}, headers=fed)).json()]
    assert "Олимпиада" in names


async def test_protocol_highlights_evsk_for_federation(client, session, world):
    rank = Rank(code="t3", name="III спортивный разряд (тест)", order_no=104, validity_months=24)
    session.add(rank)
    await session.flush()
    session.add(RankRequirement(rank_id=rank.id, level=CompetitionLevel.REGIONAL, max_place=1, min_participants=2))
    comp = await make_competition(session, world["algo"], [world["teens"]], world["admin"], start=date(2025, 3, 1))
    second = await make_athlete(session, world["algo"], birth=date(2010, 5, 5))
    await add_result(session, comp, world["teen"], 1, score=300)
    await add_result(session, comp, second, 2, score=200)
    await publish_protocol(session, comp, world["admin"])

    p = (await client.get(f"{API}/competitions/{comp.id}/protocol", headers=auth(world["admin"], RoleCode.FEDERATION))).json()
    assert [(e["athlete_id"], e["rank"], e["kind"]) for e in p["evsk"]] == [(world["teen"].id, rank.name, "assign")]
    p = (await client.get(f"{API}/competitions/{comp.id}/protocol", headers=auth(world["teen"], RoleCode.ATHLETE))).json()
    assert p["evsk"] == []


async def test_calendar_for_me_and_age_group(client, session, world):
    kids = await make_age_group(session, "10–13 лет", 10, 13)
    fits = await make_competition(session, world["algo"], [world["teens"]], world["admin"], start=START, title="Подходит")
    await make_competition(session, world["algo"], [kids], world["admin"], start=START, title="Младшие")
    await make_competition(session, world["robo"], [world["teens"]], world["admin"], start=START, title="Другая дисциплина")
    athlete = auth(world["teen"], RoleCode.ATHLETE)

    r = await client.get(f"{API}/competitions", params={"for_me": True}, headers=athlete)
    assert [c["id"] for c in r.json()["items"]] == [fits.id]
    r = await client.get(f"{API}/competitions", params={"age_group_id": kids.id}, headers=athlete)
    assert [c["title"] for c in r.json()["items"]] == ["Младшие"]
    assert (await client.get(f"{API}/competitions", params={"for_me": True}, headers=auth(world["coach"], RoleCode.COACH))).status_code == 422
