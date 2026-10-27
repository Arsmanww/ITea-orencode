"""Д10: справка об участии с QR-кодом и публичная проверка подлинности."""

import zipfile
from datetime import date
from io import BytesIO

import pytest_asyncio

from app.models.enums import RoleCode
from tests.helpers import add_result, auth, make_athlete, make_competition, make_discipline, make_user, publish_protocol

API = "/api/v1"


@pytest_asyncio.fixture
async def world(session):
    disc = await make_discipline(session, "algorithmic")
    admin = await make_user(session, [RoleCode.FEDERATION])
    athlete = await make_athlete(session, disc, birth=date(2008, 5, 5))
    other = await make_athlete(session, disc, birth=date(2008, 6, 6))
    comp = await make_competition(session, disc, [], admin, start=date(2025, 5, 10), title="Чемпионат для справки")
    result = await add_result(session, comp, athlete, 1, score=500)
    await add_result(session, comp, other, 2, score=400)
    return {"disc": disc, "admin": admin, "athlete": athlete, "other": other, "comp": comp, "result": result,
            "h": auth(athlete, RoleCode.ATHLETE), "h_other": auth(other, RoleCode.ATHLETE)}


async def test_certificate_issue_and_public_verification(client, session, world):
    await publish_protocol(session, world["comp"], world["admin"])

    created = await client.post(f"{API}/athletes/me/certificates", json={"result_id": world["result"].id}, headers=world["h"])
    assert created.status_code == 201, created.text
    cert = created.json()
    assert cert["number"].startswith("ФСП-56-2025-")
    assert cert["verify_url"].endswith(f"/verify/{cert['verify_token']}")

    # повторный запрос возвращает ту же справку
    again = await client.post(f"{API}/athletes/me/certificates", json={"result_id": world["result"].id}, headers=world["h"])
    assert again.status_code == 200 and again.json()["number"] == cert["number"]

    # публичная проверка: без авторизации; видны ФИО, турнир, место, дисциплина
    public = await client.get(f"{API}/public/certificates/{cert['verify_token']}")
    assert public.status_code == 200
    data = public.json()
    assert data["valid"] is True
    assert data["athlete_name"].startswith("Спортсменов")
    assert data["competition_title"] == "Чемпионат для справки"
    assert data["discipline"] == "Программирование алгоритмическое"
    assert data["place"] == 1 and data["participants"] == 2
    assert "birth_date" not in data  # персональные данные наружу не отдаём


async def test_qr_png_and_docx_export(client, session, world):
    await publish_protocol(session, world["comp"], world["admin"])
    cert = (await client.post(f"{API}/athletes/me/certificates", json={"result_id": world["result"].id}, headers=world["h"])).json()

    qr = await client.get(f"{API}/public/certificates/{cert['verify_token']}/qr.png")
    assert qr.status_code == 200 and qr.headers["content-type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG")

    doc = await client.get(f"{API}/athletes/me/certificates/{cert['id']}/export", headers=world["h"])
    assert doc.status_code == 200
    with zipfile.ZipFile(BytesIO(doc.content)) as z:
        assert "word/document.xml" in z.namelist()
        assert any(n.startswith("word/media/") for n in z.namelist())  # QR вставлен в документ
        assert cert["number"] in z.read("word/document.xml").decode()


async def test_certificate_rules(client, session, world):
    # протокол не опубликован
    r = await client.post(f"{API}/athletes/me/certificates", json={"result_id": world["result"].id}, headers=world["h"])
    assert r.status_code == 422

    await publish_protocol(session, world["comp"], world["admin"])
    # чужой результат
    foreign = await client.post(f"{API}/athletes/me/certificates", json={"result_id": world["result"].id}, headers=world["h_other"])
    assert foreign.status_code == 404
    # неизвестный токен
    assert (await client.get(f"{API}/public/certificates/00000000-0000-4000-8000-000000000000")).status_code == 404
    # справки доступны только роли спортсмена
    coach = await make_user(session, [RoleCode.COACH])
    assert (await client.get(f"{API}/athletes/me/certificates", headers=auth(coach, RoleCode.COACH))).status_code == 403
