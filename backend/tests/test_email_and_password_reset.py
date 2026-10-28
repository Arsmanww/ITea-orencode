"""Почта как внешний канал уведомлений и восстановление пароля («Забыли пароль?»)."""

import secrets as secrets_module
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import password_strength_error
from app.models import Notification, NotificationDelivery, PasswordResetToken, User
from app.models.enums import Channel, DeliveryStatus, NotificationKind, RoleCode
from app.services import email as email_service
from app.services.notifications import notify
from app.services.password_reset import consume_reset_token, hash_token, issue_reset_token
from tests.helpers import PASSWORD, auth, get_role, make_discipline, make_user

API = "/api/v1"
STRONG = "NovyParol1!"


@pytest.fixture
def smtp_on(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.test.example.com")


async def issue_reset_token_and_get_raw(session, user) -> str:
    """issue_reset_token сам генерирует токен и не возвращает его — подсматриваем за secrets.token_urlsafe."""
    captured: dict[str, str] = {}
    original = secrets_module.token_urlsafe

    def capturing(n: int) -> str:
        token = original(n)
        captured["token"] = token
        return token

    secrets_module.token_urlsafe = capturing
    try:
        await issue_reset_token(session, user)
    finally:
        secrets_module.token_urlsafe = original
    return captured["token"]


async def test_register_rejects_weak_password(client):
    payload = {
        "email": "weak@test.example.com", "password": "short", "last_name": "Слабый", "first_name": "Пароль",
        "birth_date": "2000-01-01", "gender": "male", "discipline_ids": [], "consent": True,
    }
    r = await client.post(f"{API}/auth/register", json=payload)
    assert r.status_code == 422


def test_password_strength_rules():
    assert "8 символов" in password_strength_error("Ab1!")
    assert "хватает" in password_strength_error("alllowercase1!")
    assert "хватает" in password_strength_error("ALLUPPERCASE1!")
    assert "хватает" in password_strength_error("NoDigitsHere!")
    assert "хватает" in password_strength_error("NoSpecial123")
    assert password_strength_error("Normal123!") is None


async def test_notification_queued_only_when_email_configured_and_enabled(session, smtp_on, monkeypatch):
    user = await make_user(session, [RoleCode.ATHLETE])
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, text: str):
        sent.append((to, subject))
        return True, None

    monkeypatch.setattr(email_service, "send_email", fake_send)

    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Заявка одобрена", "Текст")
    assert await email_service.dispatch_pending(session) == 1
    assert sent == [(user.email, "Заявка одобрена")]
    delivery = await session.scalar(select(NotificationDelivery).where(NotificationDelivery.channel == Channel.EMAIL))
    assert delivery.status == DeliveryStatus.SENT and delivery.sent_at is not None

    # выключенный тумблер — письмо не ставится в очередь
    user.email_notifications_enabled = False
    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Ещё одна", "Текст")
    assert await email_service.dispatch_pending(session) == 0

    # только в кабинет, внешний канал явно выключен для этого события
    user.email_notifications_enabled = True
    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Только в кабинете", "Текст", external=False)
    assert await email_service.dispatch_pending(session) == 0


async def test_notification_not_queued_without_smtp(session, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    user = await make_user(session, [RoleCode.ATHLETE])
    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Заявка одобрена", "Текст")
    assert await email_service.dispatch_pending(session) == 0


async def test_toggle_email_notifications(client, session):
    user = await make_user(session, [RoleCode.ATHLETE])
    headers = auth(user, RoleCode.ATHLETE)

    r = await client.get(f"{API}/me/notification-settings", headers=headers)
    assert r.status_code == 200 and r.json()["email_notifications_enabled"] is True

    r = await client.put(f"{API}/me/notification-settings", json={"enabled": False}, headers=headers)
    assert r.status_code == 200 and r.json()["email_notifications_enabled"] is False
    await session.refresh(user)
    assert user.email_notifications_enabled is False


async def test_forgot_password_same_message_for_unknown_email(client, session):
    r = await client.post(f"{API}/auth/forgot-password", json={"email": "nobody@test.example.com"})
    assert r.status_code == 200
    known_message = r.json()["detail"]
    assert await session.scalar(select(PasswordResetToken)) is None

    user = await make_user(session, [RoleCode.ATHLETE])
    r2 = await client.post(f"{API}/auth/forgot-password", json={"email": user.email})
    assert r2.status_code == 200
    assert r2.json()["detail"] == known_message
    assert await session.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)) is not None


async def test_forgot_password_logs_link_without_smtp(client, session, monkeypatch, caplog):
    monkeypatch.setattr(settings, "smtp_host", "")
    user = await make_user(session, [RoleCode.ATHLETE])
    with caplog.at_level("WARNING", logger="fsp.password_reset"):
        r = await client.post(f"{API}/auth/forgot-password", json={"email": user.email})
    assert r.status_code == 200
    assert any("reset-password?token=" in m for m in caplog.messages)


async def test_reset_password_full_flow(client, session):
    user = await make_user(session, [RoleCode.ATHLETE])
    raw_token = await issue_reset_token_and_get_raw(session, user)
    await session.commit()

    r = await client.post(f"{API}/auth/reset-password", json={"token": raw_token, "new_password": STRONG})
    assert r.status_code == 200

    old_login = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert old_login.status_code == 401
    new_login = await client.post(f"{API}/auth/login", json={"email": user.email, "password": STRONG})
    assert new_login.status_code == 200

    # токен одноразовый
    r2 = await client.post(f"{API}/auth/reset-password", json={"token": raw_token, "new_password": "AnotherPass1!"})
    assert r2.status_code == 400


async def test_reset_password_rejects_expired_token(client, session):
    user = await make_user(session, [RoleCode.ATHLETE])
    raw = "expired-raw-token-0123456789"
    session.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw),
                                   expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    await session.commit()
    r = await client.post(f"{API}/auth/reset-password", json={"token": raw, "new_password": STRONG})
    assert r.status_code == 400


async def test_reset_password_rejects_unknown_token(client):
    r = await client.post(f"{API}/auth/reset-password", json={"token": "does-not-exist-anywhere-0000", "new_password": STRONG})
    assert r.status_code == 400


async def test_reset_password_rejects_weak_password(session, client):
    user = await make_user(session, [RoleCode.ATHLETE])
    raw = "weak-password-attempt-raw-token"
    session.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw),
                                   expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
    await session.commit()
    r = await client.post(f"{API}/auth/reset-password", json={"token": raw, "new_password": "weak"})
    assert r.status_code == 422


async def test_consume_reset_token_service_directly(session):
    user = await make_user(session, [RoleCode.ATHLETE])
    raw = "direct-service-raw-token-abcxyz"
    session.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw),
                                   expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
    await session.flush()
    got = await consume_reset_token(session, raw)
    assert got is not None and got.id == user.id
    assert await consume_reset_token(session, raw) is None  # одноразовость


def _patch_send_email(monkeypatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, text: str):
        sent.append((to, subject))
        return True, None

    monkeypatch.setattr(email_service, "send_email", fake_send)
    return sent


async def test_register_sends_welcome_email_without_inapp_notification(client, session, smtp_on, monkeypatch):
    sent = _patch_send_email(monkeypatch)
    disc = await make_discipline(session)
    await get_role(session, RoleCode.ATHLETE)
    await session.commit()

    payload = {
        "email": "welcome@test.example.com", "password": STRONG, "last_name": "Новиков", "first_name": "Иван",
        "birth_date": "2000-01-01", "gender": "male", "discipline_ids": [disc.id], "consent": True,
    }
    r = await client.post(f"{API}/auth/register", json=payload)
    assert r.status_code == 201

    assert len(sent) == 1
    to, subject = sent[0]
    assert to == "welcome@test.example.com" and "Регистрация" in subject

    user = await session.scalar(select(User).where(User.email == "welcome@test.example.com"))
    rows = (await session.scalars(select(Notification.id).where(Notification.user_id == user.id))).all()
    assert rows == []  # письмо не создаёт запись в личном кабинете


async def test_login_sends_alert_email_without_inapp_notification(client, session, smtp_on, monkeypatch):
    user = await make_user(session, [RoleCode.ATHLETE])
    sent = _patch_send_email(monkeypatch)

    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200

    assert len(sent) == 1
    to, subject = sent[0]
    assert to == user.email and "вход" in subject.lower()

    rows = (await session.scalars(select(Notification.id).where(Notification.user_id == user.id))).all()
    assert rows == []


async def test_login_alert_respects_disabled_toggle(client, session, smtp_on, monkeypatch):
    user = await make_user(session, [RoleCode.ATHLETE])
    user.email_notifications_enabled = False
    await session.commit()
    sent = _patch_send_email(monkeypatch)

    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200
    assert sent == []


async def test_login_alert_skipped_without_smtp(client, session, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    user = await make_user(session, [RoleCode.ATHLETE])
    sent = _patch_send_email(monkeypatch)

    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200
    assert sent == []
