"""С9: рейтинг с коэффициентом стабильности ×1,2, санкциями и прозрачным расчётом."""

from datetime import date
from decimal import Decimal

import pytest_asyncio

from app.models import RatingRule, RatingSettings, Sanction, Season
from app.models.enums import RatingTier, RoleCode, SanctionKind
from tests.helpers import add_result, auth, make_athlete, make_competition, make_discipline, make_user, publish_protocol

API = "/api/v1"
SEASON_START, SEASON_END = date(2020, 1, 1), date(2020, 12, 31)  # закрытый сезон: результат не зависит от текущей даты


@pytest_asyncio.fixture
async def world(session):
    disc = await make_discipline(session, "algorithmic")
    admin = await make_user(session, [RoleCode.FEDERATION])
    season = Season(name="Сезон 2020", date_from=SEASON_START, date_to=SEASON_END)
    session.add(season)
    session.add(RatingSettings(stability_coef=Decimal("1.20"), stability_min_prizes=2))
    session.add_all(RatingRule(tier=RatingTier.REGIONAL, place=p, points=pts) for p, pts in ((1, 40), (2, 30), (3, 20)))
    await session.flush()

    birth = date(2005, 3, 3)
    x = await make_athlete(session, disc, birth=birth)  # два призовых места -> коэффициент
    y = await make_athlete(session, disc, birth=birth)  # одно призовое -> без коэффициента
    z = await make_athlete(session, disc, birth=birth)  # дисквалифицирован
    c1 = await make_competition(session, disc, [], admin, start=date(2020, 3, 10))
    c2 = await make_competition(session, disc, [], admin, start=date(2020, 9, 10))
    # Соревнование 1: X – 1 место (40), Y – 2 место (30), Z – 3 место (20)
    # Соревнование 2: X – 2 место (30), Y – 5 место (0 очков)
    for athlete, place in ((x, 1), (y, 2), (z, 3)):
        await add_result(session, c1, athlete, place)
    for athlete, place in ((x, 2), (y, 5)):
        await add_result(session, c2, athlete, place)
    await publish_protocol(session, c1, admin)
    await publish_protocol(session, c2, admin)
    session.add(Sanction(athlete_id=z.id, kind=SanctionKind.DISQUALIFICATION, date_from=date(2020, 6, 1), date_to=date(2021, 6, 1),
                         reason="Нарушение правил"))
    await session.flush()
    return {"season": season, "x": x, "y": y, "z": z, "viewer": auth(x, RoleCode.ATHLETE)}


async def get_rating(client, world):
    r = await client.get(f"{API}/rating", params={"season_id": world["season"].id, "discipline": "algorithmic"}, headers=world["viewer"])
    assert r.status_code == 200, r.text
    return r.json()["tables"][0]


async def test_stability_coefficient_applies_from_two_prizes(client, world):
    table = await get_rating(client, world)
    by_id = {i["athlete_id"]: i for i in table["items"]}

    x = by_id[world["x"].id]
    assert x["prizes"] == 2
    assert x["base_points"] == 70  # 40 + 30
    assert Decimal(x["coefficient"]) == Decimal("1.20")
    assert Decimal(x["total"]) == Decimal("84.00")  # 70 × 1,2

    y = by_id[world["y"].id]
    assert y["prizes"] == 1
    assert y["base_points"] == 30  # 5 место очков не даёт
    assert Decimal(y["coefficient"]) == Decimal("1")
    assert Decimal(y["total"]) == Decimal("30.00")

    assert [i["athlete_id"] for i in table["items"]] == [world["x"].id, world["y"].id]
    assert [i["place"] for i in table["items"]] == [1, 2]


async def test_calculation_is_transparent(client, world):
    x = {i["athlete_id"]: i for i in (await get_rating(client, world))["items"]}[world["x"].id]
    assert [(b["place"], b["points"]) for b in x["breakdown"]] == [(1, 40), (2, 30)]
    assert all(b["tier"] == "regional" for b in x["breakdown"])


async def test_sanctioned_athlete_is_excluded(client, world):
    table = await get_rating(client, world)
    assert world["z"].id not in [i["athlete_id"] for i in table["items"]]
    excluded = {e["athlete_id"]: e["reason"] for e in table["excluded"]}
    assert "Дисквалификация" in excluded[world["z"].id]


async def test_coefficient_and_points_are_configurable(client, session, world):
    settings_row = await session.scalar(RatingSettings.__table__.select())
    await session.execute(RatingSettings.__table__.update().values(stability_coef=Decimal("1.50")))
    await session.flush()
    x = {i["athlete_id"]: i for i in (await get_rating(client, world))["items"]}[world["x"].id]
    assert Decimal(x["total"]) == Decimal("105.00")  # 70 × 1,5
    assert settings_row is not None
