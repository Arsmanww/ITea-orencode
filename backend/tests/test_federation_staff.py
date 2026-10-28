"""Федерация заводит аккаунт тренера/судьи (не самрегистрация) – POST /federation/staff."""

import secrets as secrets_module

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import CoachProfile, Consent, JudgeProfile, Municipality, Organization, User
from app.models.enums import OrgType, RoleCode
from app.services import password_reset as password_reset_module
from tests.helpers import PASSWORD, auth, get_role, make_user

API = "/api/v1"


@pytest.fixture
def smtp_on(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test.example.com")


def _patch_send_email(monkeypatch) -> list[tuple[str, str]]:
    """federation.py шлёт письмо через issue_reset_token(), который использует свой собственный
    импорт send_email – патчим именно в app.services.password_reset, а не в app.services.email."""
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, text: str):
        sent.append((to, subject))
        return True, None

    monkeypatch.setattr(password_reset_module, "send_email", fake_send)
    return sent


async def make_org(session) -> Organization:
    m = Municipality(name=f"Тестовый район {secrets_module.token_hex(4)}")
    session.add(m)
    await session.flush()
    o = Organization(name="Тестовая спортшкола", type=OrgType.SPORTS_SCHOOL, municipality_id=m.id)
    session.add(o)
    await session.flush()
    return o


async def test_only_federation_can_create_staff(client, session):
    org = await make_org(session)
    athlete = await make_user(session, [RoleCode.ATHLETE])
    payload = {
        "email": "newcoach@test.example.com", "last_name": "Иванов", "first_name": "Пётр", "birth_date": "1985-01-01",
        "gender": "male", "role": "coach", "organization_id": org.id, "consent": True,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(athlete, RoleCode.ATHLETE))
    assert r.status_code == 403


async def test_create_new_coach_sends_activation_email_and_creates_profile(client, session, smtp_on, monkeypatch):
    sent = _patch_send_email(monkeypatch)
    org = await make_org(session)
    fed = await make_user(session, [RoleCode.FEDERATION])
    await get_role(session, RoleCode.COACH)

    payload = {
        "email": "newcoach@test.example.com", "last_name": "Иванов", "first_name": "Пётр", "birth_date": "1985-01-01",
        "gender": "male", "role": "coach", "organization_id": org.id, "bio": "Тренер", "consent": True,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(fed, RoleCode.FEDERATION))
    assert r.status_code == 201
    body = r.json()
    assert body["created_new_user"] is True and body["role"] == "coach"

    assert len(sent) == 1
    to, subject = sent[0]
    assert to == "newcoach@test.example.com" and "Доступ на платформу" in subject

    user = await session.scalar(select(User).where(User.email == "newcoach@test.example.com"))
    assert user is not None
    profile = await session.get(CoachProfile, user.id)
    assert profile is not None and profile.organization_id == org.id and profile.bio == "Тренер"
    consent = await session.scalar(select(Consent).where(Consent.user_id == user.id))
    assert consent is not None and consent.signed_by_name == "Иванов Пётр"


async def test_create_new_judge_creates_profile_without_consent(client, session, smtp_on, monkeypatch):
    _patch_send_email(monkeypatch)
    fed = await make_user(session, [RoleCode.FEDERATION])
    await get_role(session, RoleCode.JUDGE)

    payload = {
        "email": "newjudge@test.example.com", "last_name": "Петров", "first_name": "Иван", "birth_date": "1980-01-01",
        "gender": "male", "role": "judge", "consent": False,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(fed, RoleCode.FEDERATION))
    assert r.status_code == 201

    user = await session.scalar(select(User).where(User.email == "newjudge@test.example.com"))
    assert await session.get(JudgeProfile, user.id) is not None
    assert await session.scalar(select(Consent).where(Consent.user_id == user.id)) is None


async def test_adding_role_to_existing_user_does_not_send_email(client, session, smtp_on, monkeypatch):
    sent = _patch_send_email(monkeypatch)
    fed = await make_user(session, [RoleCode.FEDERATION])
    athlete = await make_user(session, [RoleCode.ATHLETE])
    await get_role(session, RoleCode.COACH)

    payload = {
        "email": athlete.email, "last_name": athlete.last_name, "first_name": athlete.first_name,
        "birth_date": "2000-01-01", "gender": "male", "role": "coach", "consent": True,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(fed, RoleCode.FEDERATION))
    assert r.status_code == 201
    assert r.json()["created_new_user"] is False
    assert sent == []  # аккаунт уже существует – писем про активацию не шлём

    assert await session.get(CoachProfile, athlete.id) is not None


async def test_duplicate_role_rejected(client, session):
    fed = await make_user(session, [RoleCode.FEDERATION])
    coach = await make_user(session, [RoleCode.COACH])
    session.add(CoachProfile(user_id=coach.id))
    await session.commit()

    payload = {
        "email": coach.email, "last_name": coach.last_name, "first_name": coach.first_name,
        "birth_date": "1990-01-01", "gender": "male", "role": "coach", "consent": True,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(fed, RoleCode.FEDERATION))
    assert r.status_code == 409


async def test_role_restricted_to_coach_or_judge(client, session):
    fed = await make_user(session, [RoleCode.FEDERATION])
    payload = {
        "email": "x@test.example.com", "last_name": "Х", "first_name": "Х",
        "birth_date": "1990-01-01", "gender": "male", "role": "federation", "consent": True,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(fed, RoleCode.FEDERATION))
    assert r.status_code == 422


async def test_activation_link_lets_new_coach_set_password_and_login(client, session, smtp_on, monkeypatch):
    # перехватываем токен именно из app.services.password_reset (пароль-заглушка в federation.py
    # генерируется через свой собственный импорт `secrets` и нас не интересует)
    import app.services.password_reset as pw_reset_module

    captured: dict[str, str] = {}
    real_token_urlsafe = pw_reset_module.secrets.token_urlsafe

    def capture_reset_token(n: int) -> str:
        token = real_token_urlsafe(n)
        captured["token"] = token
        return token

    monkeypatch.setattr(pw_reset_module.secrets, "token_urlsafe", capture_reset_token)
    _patch_send_email(monkeypatch)

    fed = await make_user(session, [RoleCode.FEDERATION])
    await get_role(session, RoleCode.JUDGE)
    payload = {
        "email": "activate@test.example.com", "last_name": "Судьин", "first_name": "Семён", "birth_date": "1975-01-01",
        "gender": "male", "role": "judge", "consent": True,
    }
    r = await client.post(f"{API}/federation/staff", json=payload, headers=auth(fed, RoleCode.FEDERATION))
    assert r.status_code == 201
    assert "token" in captured

    new_password = "ActivatedPass1!"
    r2 = await client.post(f"{API}/auth/reset-password", json={"token": captured["token"], "new_password": new_password})
    assert r2.status_code == 200

    login = await client.post(f"{API}/auth/login", json={"email": "activate@test.example.com", "password": new_password})
    assert login.status_code == 200
