"""Уведомления в мессенджер MAX: привязка по одноразовому коду, очередь и отправка; рассылка об открытии регистрации."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import Notification, NotificationDelivery
from app.models.enums import Channel, CompetitionStatus, DeliveryStatus, NotificationKind, RoleCode
from app.services import max_bot
from app.services.deadlines import run_deadline_check
from app.services.notifications import notify
from tests.helpers import auth, make_age_group, make_athlete, make_competition, make_discipline, make_user

API = "/api/v1"


@pytest.fixture
def max_on(monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", "test-max-token")
    monkeypatch.setattr(settings, "max_bot_username", "fsp56_bot")


def started(user_id: int, payload: str | None) -> dict:
    return {"update_type": "bot_started", "timestamp": 1, "chat_id": 777, "user": {"user_id": user_id, "first_name": "Тест"}, "payload": payload}


async def test_link_by_deep_link_code(client, session, max_on):
    user = await make_user(session, [RoleCode.ATHLETE])
    headers = auth(user, RoleCode.ATHLETE)

    r = await client.post(f"{API}/me/max/link", headers=headers)
    assert r.status_code == 200
    link = r.json()
    assert link["link"] == f"https://max.ru/fsp56_bot?start={link['code']}"

    # чужой или выдуманный код не привязывает
    assert "не найден" in await max_bot.handle_update(session, started(5001, "wrong-code-123"))
    assert user.max_user_id is None

    reply = await max_bot.handle_update(session, started(5001, link["code"]))
    assert "привязан" in reply
    s = (await client.get(f"{API}/me/notification-settings", headers=headers)).json()
    assert s["max_bound"] is True and s["max_bot_configured"] is True
    # код одноразовый
    assert "не найден" in await max_bot.handle_update(session, started(5002, link["code"]))


async def test_code_sent_as_message_and_expiry(client, session, max_on):
    user = await make_user(session, [RoleCode.COACH])
    code = (await client.post(f"{API}/me/max/link", headers=auth(user, RoleCode.COACH))).json()["code"]
    user.max_link_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    message = {"update_type": "message_created", "message": {"sender": {"user_id": 6001}, "recipient": {"chat_id": 1}, "body": {"text": f"/start {code}"}}}
    assert "устарел" in await max_bot.handle_update(session, message)
    assert user.max_user_id is None

    code = (await client.post(f"{API}/me/max/link", headers=auth(user, RoleCode.COACH))).json()["code"]
    message["message"]["body"]["text"] = code
    assert "привязан" in await max_bot.handle_update(session, message)
    assert user.max_user_id == "6001"


async def test_link_requires_configured_bot(client, session, monkeypatch):
    monkeypatch.setattr(settings, "max_bot_token", "")
    user = await make_user(session, [RoleCode.JUDGE])
    assert (await client.post(f"{API}/me/max/link", headers=auth(user, RoleCode.JUDGE))).status_code == 503


async def test_notification_queued_and_dispatched(session, max_on, monkeypatch):
    user = await make_user(session, [RoleCode.ATHLETE])
    user.max_user_id = "7001"
    sent: list[tuple[str, str]] = []

    async def fake_send(user_id: str, text: str):
        sent.append((user_id, text))
        return True, None

    monkeypatch.setattr(max_bot, "send_message", fake_send)
    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Заявка одобрена", "Текст")
    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Только в кабинете", "Текст", external=False)
    assert await max_bot.dispatch_pending(session) == 1
    assert sent == [("7001", "Заявка одобрена\n\nТекст")]
    delivery = await session.scalar(select(NotificationDelivery).where(NotificationDelivery.channel == Channel.MAX))
    assert delivery.status == DeliveryStatus.SENT and delivery.sent_at is not None

    # после отвязки новые уведомления в MAX не ставятся
    user.max_user_id = None
    await notify(session, user.id, NotificationKind.APPLICATION_STATUS, "Ещё", "Текст")
    assert await max_bot.dispatch_pending(session) == 0


async def test_registration_open_notifies_eligible(client, session):
    algo = await make_discipline(session, "algorithmic")
    teens = await make_age_group(session, "14–17 лет", 14, 17)
    admin = await make_user(session, [RoleCode.FEDERATION])
    start = date(date.today().year + 1, 6, 15)
    comp = await make_competition(session, algo, [teens], admin, start=start, status=CompetitionStatus.PUBLISHED)
    fits = await make_athlete(session, algo, birth=date(start.year - 15, 1, 1))
    too_old = await make_athlete(session, algo, birth=date(start.year - 30, 1, 1))
    other = await make_athlete(session, None, birth=date(start.year - 15, 1, 1))

    r = await client.patch(f"{API}/competitions/{comp.id}", json={"status": "registration_open"}, headers=auth(admin, RoleCode.FEDERATION))
    assert r.status_code == 200
    got = set((await session.scalars(
        select(Notification.user_id).where(Notification.kind == NotificationKind.REGISTRATION_OPEN, Notification.entity_id == comp.id)
    )).all())
    assert fits.id in got and too_old.id not in got and other.id not in got


async def test_deadline_and_governor_reminders(session):
    algo = await make_discipline(session, "algorithmic")
    teens = await make_age_group(session, "14–17 лет", 14, 17)
    admin = await make_user(session, [RoleCode.FEDERATION])
    start = date(date.today().year + 1, 6, 15)
    comp = await make_competition(session, algo, [teens], admin, start=start)
    late = await make_athlete(session, algo, birth=date(start.year - 15, 1, 1))
    now = comp.registration_deadline - timedelta(days=2)

    assert await run_deadline_check(session, now) >= 2
    assert await run_deadline_check(session, now) == 0  # повторная проверка не дублирует
    kinds = (await session.execute(
        select(Notification.user_id, Notification.title).where(Notification.kind == NotificationKind.DEADLINE_SOON)
    )).all()
    assert (late.id, "Скоро закрытие приёма заявок") in kinds and (admin.id, "Скоро закрытие приёма заявок") in kinds

    jan = datetime(now.year + 1, 1, 26, 9, tzinfo=timezone.utc)
    await run_deadline_check(session, jan)
    governor = await session.scalar(select(Notification).where(Notification.user_id == admin.id, Notification.title == "Ходатайства на премии Губернатора"))
    assert governor is not None and f"01.02.{jan.year}" in governor.body
