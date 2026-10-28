"""С3: заявка проверяется на сервере по возрасту и дисциплине."""

from datetime import date, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.models import AthleteEnrollment, CoachAthleteLink, CoachProfile
from app.models.enums import LinkStatus, RoleCode
from tests.helpers import auth, make_age_group, make_athlete, make_competition, make_discipline, make_user

API = "/api/v1"
START = date(date.today().year + 2, 6, 15)  # дата старта в будущем: возраст не «уплывает» со временем


def born(age_on_start: int) -> date:
    return date(START.year - age_on_start, 1, 1)


@pytest_asyncio.fixture
async def setup(session):
    algo = await make_discipline(session, "algorithmic")
    robo = await make_discipline(session, "robotics", "Программирование робототехники")
    teens = await make_age_group(session, "14–17 лет", 14, 17)
    admin = await make_user(session, [RoleCode.FEDERATION])
    comp = await make_competition(session, algo, [teens], admin, start=START)
    return {"algo": algo, "robo": robo, "comp": comp, "admin": admin}


async def apply(client, comp_id: int, user, body=None, role=RoleCode.ATHLETE):
    return await client.post(f"{API}/competitions/{comp_id}/applications", json=body or {}, headers=auth(user, role))


async def test_age_outside_group_is_rejected(client, session, setup):
    too_young = await make_athlete(session, setup["algo"], birth=born(12))
    too_old = await make_athlete(session, setup["algo"], birth=born(20))

    for athlete, age in ((too_young, 12), (too_old, 20)):
        r = await apply(client, setup["comp"].id, athlete)
        assert r.status_code == 422, r.text
        assert f"{age} лет" in r.json()["detail"]
        assert "14–17" in r.json()["detail"]


async def test_age_in_group_is_accepted_with_age_snapshot(client, session, setup):
    athlete = await make_athlete(session, setup["algo"], birth=born(15))
    r = await apply(client, setup["comp"].id, athlete)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["age_on_start"] == 15
    assert body["submitted_by_role"] == "athlete"


async def test_discipline_mismatch_is_rejected(client, session, setup):
    robot_only = await make_athlete(session, setup["robo"], birth=born(15))
    r = await apply(client, setup["comp"].id, robot_only)
    assert r.status_code == 422
    assert "не занимается дисциплиной" in r.json()["detail"]


async def test_duplicate_application_conflicts(client, session, setup):
    athlete = await make_athlete(session, setup["algo"], birth=born(16))
    assert (await apply(client, setup["comp"].id, athlete)).status_code == 201
    assert (await apply(client, setup["comp"].id, athlete)).status_code == 409


async def test_athlete_with_coach_cannot_apply_but_coach_can(client, session, setup):
    athlete = await make_athlete(session, setup["algo"], birth=born(15))
    coach = await make_user(session, [RoleCode.COACH])
    session.add(CoachProfile(user_id=coach.id))
    await session.flush()
    session.add(CoachAthleteLink(coach_id=coach.id, athlete_id=athlete.id, discipline_id=setup["algo"].id, status=LinkStatus.ACTIVE,
                                 initiated_by_user_id=coach.id))
    await session.flush()

    own = await apply(client, setup["comp"].id, athlete)
    assert own.status_code == 403
    assert "тренер" in own.json()["detail"]

    by_coach = await apply(client, setup["comp"].id, coach, {"athlete_id": athlete.id}, role=RoleCode.COACH)
    assert by_coach.status_code == 201, by_coach.text
    assert by_coach.json()["submitted_by_role"] == "coach"
    assert by_coach.json()["coach_id"] == coach.id


async def test_athlete_enrolled_after_start_can_apply(client, session, setup):
    """Спортсмен зарегистрировался, когда соревнование уже шло: приём заявок открыт – значит, заявку принимаем."""
    started = await make_competition(session, setup["algo"], [await make_age_group(session, "14–17 лет", 14, 17)],
                                     setup["admin"], start=date.today() - timedelta(days=1))
    newcomer = await make_athlete(session, setup["algo"], birth=born(16), enrolled_since=date.today())

    r = await apply(client, started.id, newcomer)
    assert r.status_code == 201, r.json()


async def test_finished_enrollment_blocks_application(client, session, setup):
    """Занятия по дисциплине закончились – к заявке не допускаем."""
    quit_athlete = await make_athlete(session, setup["algo"], birth=born(16))
    enrollment = await session.scalar(select(AthleteEnrollment).where(AthleteEnrollment.athlete_id == quit_athlete.id))
    enrollment.end_date = date.today() - timedelta(days=1)
    await session.flush()

    r = await apply(client, setup["comp"].id, quit_athlete)
    assert r.status_code == 422 and "не занимается дисциплиной" in r.json()["detail"]
