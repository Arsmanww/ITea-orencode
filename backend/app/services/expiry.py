"""Контроль сроков: уведомления об истечении разрядов и судейских категорий.

Спортсмен, его активные тренеры и федерация предупреждаются за 60, 30 и 7 дней в личном кабинете,
а на почту приходит предупреждение за 7 дней.
Та же проверка напоминает о закрытии приёма заявок и о сроке ходатайств на премии Губернатора (services/deadlines.py).
Повторы исключает dedup_key: на каждый порог одно уведомление на получателя.
"""

import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.models import CoachAthleteLink
from app.models.enums import LinkStatus, NotificationKind
from app.services.deadlines import run_deadline_check
from app.services.notifications import federation_user_ids, notify
from app.services.ranks import expiring_items

logger = logging.getLogger("fsp.expiry")
THRESHOLDS = (60, 30, 7)
FINAL_WARNING_DAYS = 7  # во внешний канал уходит только последнее предупреждение
CHECK_INTERVAL_SECONDS = 3600


async def run_expiry_check(session: AsyncSession, today: date) -> int:
    """Создаёт недостающие уведомления. Возвращает число созданных."""
    created = 0
    federation = await federation_user_ids(session)
    for item in await expiring_items(session, today, max(THRESHOLDS)):
        threshold = min(t for t in THRESHOLDS if t >= item["days_left"])
        until = item["valid_until"].strftime("%d.%m.%Y")
        left = item["days_left"]
        if item["kind"] == "rank":
            coaches = (await session.scalars(
                select(CoachAthleteLink.coach_id).where(
                    CoachAthleteLink.athlete_id == item["subject_id"],
                    CoachAthleteLink.discipline_id == item["discipline_id"],
                    CoachAthleteLink.status == LinkStatus.ACTIVE,
                )
            )).all()
            kind = NotificationKind.RANK_EXPIRING
            what = f"Разряд «{item['title']}» ({item['discipline']})"
            recipients = {item["subject_id"], *coaches, *federation}
        else:
            kind = NotificationKind.CATEGORY_EXPIRING
            what = f"Судейская категория «{item['title']}»"
            recipients = {item["subject_id"], *federation}
        title = f"Истекает срок: {what}"
        body = f"{what}, {item['subject_name']}: действует до {until}, осталось дней: {left}."
        for user_id in recipients:
            created += await notify(
                session, user_id, kind, title, body, entity_type=item["kind"], entity_id=item["assignment_id"],
                dedup_key=f"{item['kind']}-exp:{item['assignment_id']}:{threshold}:{user_id}",
                external=threshold == FINAL_WARNING_DAYS,
            )
    created += await run_deadline_check(session, datetime.now(timezone.utc))
    await session.commit()
    return created


async def expiry_loop() -> None:
    """Фоновая задача: проверка при старте и далее каждый час (приём заявок закрывается по часам)."""
    while True:
        try:
            async with async_session_maker() as session:
                created = await run_expiry_check(session, date.today())
            logger.info("Проверка сроков: создано уведомлений %s", created)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка проверки сроков")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
