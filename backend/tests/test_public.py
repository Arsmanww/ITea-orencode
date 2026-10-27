"""Публичный лидерборд и лента: без авторизации, ФИО сокращены, фильтр по городу."""

from datetime import date
from decimal import Decimal

from app.models import Municipality, RatingRule, RatingSettings, Season
from app.models.enums import RatingTier, RoleCode
from tests.helpers import add_result, make_athlete, make_competition, make_discipline, make_user, publish_protocol

API = "/api/v1/public"


async def test_leaderboard_is_public_masked_and_filterable_by_city(client, session):
    today = date.today()
    disc = await make_discipline(session, "algorithmic")
    admin = await make_user(session, [RoleCode.FEDERATION])
    session.add(Season(name="Текущий", date_from=date(today.year, 1, 1), date_to=date(today.year, 12, 31)))
    session.add(RatingSettings())
    session.add_all(RatingRule(tier=RatingTier.REGIONAL, place=p, points=pts) for p, pts in ((1, 40), (2, 30), (3, 20)))
    orenburg, orsk = Municipality(name="г. Оренбург"), Municipality(name="г. Орск")
    session.add_all([orenburg, orsk])
    await session.flush()

    a = await make_athlete(session, disc, birth=date(2008, 1, 1))
    b = await make_athlete(session, disc, birth=date(2008, 2, 2))
    a.municipality_id, b.municipality_id = orenburg.id, orsk.id
    comp = await make_competition(session, disc, [], admin, start=date(today.year, 1, 1))
    await add_result(session, comp, a, 1)
    await add_result(session, comp, b, 2)
    await publish_protocol(session, comp, admin)

    everyone = await client.get(f"{API}/leaderboard", params={"discipline": "algorithmic"})  # без токена
    assert everyone.status_code == 200
    rows = everyone.json()
    assert [r["place"] for r in rows] == [1, 2]
    assert rows[0]["name"] == f"{a.last_name} {a.first_name[0]}."  # фамилия и инициал, без отчества
    assert Decimal(str(rows[0]["points"])) == Decimal("40")

    only_orsk = (await client.get(f"{API}/leaderboard", params={"discipline": "algorithmic", "municipality_id": orsk.id})).json()
    assert [r["name"] for r in only_orsk] == [f"{b.last_name} {b.first_name[0]}."]
    assert only_orsk[0]["place"] == 1 and only_orsk[0]["municipality"] == "г. Орск"

    assert (await client.get(f"{API}/leaderboard", params={"discipline": "nothing"})).status_code == 404

    feed = (await client.get(f"{API}/feed")).json()  # публичная лента опубликованных протоколов
    assert feed and feed[0]["title"] == comp.title
