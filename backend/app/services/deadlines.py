"""Уведомления о соревнованиях и сроках федерации (п. 8 кейса).

- открытие регистрации: спортсменам, которые проходят по дисциплине и возрасту, и их тренерам;
- приближение окончания приёма заявок: тем же адресатам, кто ещё не подал заявку, и федерации;
- срок подачи ходатайств на премии Губернатора (до 1 февраля): федерации.
Повторы исключает dedup_key, поэтому проверки можно запускать сколько угодно раз.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgeGroup,
    AthleteEnrollment,
    CoachAthleteLink,
    Competition,
    CompetitionAgeGroup,
    CompetitionApplication,
    User,
)
from app.models.enums import ApplicationStatus, CompetitionStatus, LinkStatus, NotificationKind
from app.services.eligibility import age_on, enrollment_conditions
from app.services.notifications import federation_user_ids, notify

DEADLINE_WARNING_DAYS = 3
GOVERNOR_DEADLINE = (2, 1)  # 1 февраля
GOVERNOR_WARNING_DAYS = (30, 7)


async def eligible_audience(session: AsyncSession, comp: Competition) -> tuple[set[int], set[int]]:
    """(спортсмены, тренеры): кто занимается дисциплиной на дату старта и проходит в возрастные группы."""
    groups = (await session.scalars(
        select(AgeGroup).join(CompetitionAgeGroup, CompetitionAgeGroup.age_group_id == AgeGroup.id)
        .where(CompetitionAgeGroup.competition_id == comp.id)
    )).all()
    rows = (await session.execute(
        select(User.id, User.birth_date).join(AthleteEnrollment, AthleteEnrollment.athlete_id == User.id)
        .where(User.is_active.is_(True), *enrollment_conditions(comp, date.today()))
        .distinct()
    )).all()
    athletes = {uid for uid, birth in rows if any(g.min_age <= age_on(birth, comp.start_date) <= g.max_age for g in groups)}
    coaches = set((await session.scalars(
        select(CoachAthleteLink.coach_id).where(CoachAthleteLink.athlete_id.in_(athletes), CoachAthleteLink.status == LinkStatus.ACTIVE,
                                                CoachAthleteLink.discipline_id == comp.discipline_id)
    )).all()) if athletes else set()
    return athletes, coaches


def _deadline_text(comp: Competition) -> str:
    if comp.registration_deadline is None:
        return ""
    local = comp.registration_deadline.astimezone(timezone(timedelta(hours=5)))
    return f" Приём заявок до {local:%d.%m.%Y %H:%M} (Оренбург)."


async def notify_registration_open(session: AsyncSession, comp: Competition) -> int:
    """Рассылка об открытии регистрации. Коммит делает вызывающий код."""
    athletes, coaches = await eligible_audience(session, comp)
    created = 0
    for uid in athletes | coaches:
        whom = "вы проходите по дисциплине и возрасту" if uid in athletes else "в соревновании могут участвовать ваши спортсмены"
        created += await notify(
            session, uid, NotificationKind.REGISTRATION_OPEN, "Открыта регистрация",
            f"«{comp.title}», {comp.start_date:%d.%m.%Y}: {whom}.{_deadline_text(comp)}",
            entity_type="competition", entity_id=comp.id, dedup_key=f"reg-open:{comp.id}:{uid}",
        )
    return created


async def run_deadline_check(session: AsyncSession, now: datetime) -> int:
    """Напоминания о закрытии приёма заявок и о сроке ходатайств на премии Губернатора. Коммит – у вызывающего."""
    created = 0
    federation = await federation_user_ids(session)
    comps = (await session.scalars(
        select(Competition).where(Competition.status == CompetitionStatus.REGISTRATION_OPEN,
                                  Competition.registration_deadline.is_not(None),
                                  Competition.registration_deadline > now,
                                  Competition.registration_deadline <= now + timedelta(days=DEADLINE_WARNING_DAYS))
    )).all()
    for comp in comps:
        athletes, coaches = await eligible_audience(session, comp)
        applied = set((await session.scalars(
            select(CompetitionApplication.athlete_id).where(
                CompetitionApplication.competition_id == comp.id,
                CompetitionApplication.status.in_([ApplicationStatus.PENDING, ApplicationStatus.APPROVED]))
        )).all())
        pending = (await session.scalars(
            select(CompetitionApplication.id).where(CompetitionApplication.competition_id == comp.id,
                                                    CompetitionApplication.status == ApplicationStatus.PENDING)
        )).all()
        title = "Скоро закрытие приёма заявок"
        for uid in (athletes - applied) | coaches:
            created += await notify(session, uid, NotificationKind.DEADLINE_SOON, title,
                                    f"«{comp.title}»: заявка ещё не подана.{_deadline_text(comp)}",
                                    entity_type="competition", entity_id=comp.id, dedup_key=f"reg-deadline:{comp.id}:{uid}")
        for uid in federation:
            created += await notify(session, uid, NotificationKind.DEADLINE_SOON, title,
                                    f"«{comp.title}»: заявок на модерации – {len(pending)}.{_deadline_text(comp)}",
                                    entity_type="competition", entity_id=comp.id, dedup_key=f"reg-deadline:{comp.id}:{uid}")
    created += await _governor_reminder(session, now.date(), federation)
    return created


async def _governor_reminder(session: AsyncSession, today: date, federation: list[int]) -> int:
    deadline = date(today.year if (today.month, today.day) <= GOVERNOR_DEADLINE else today.year + 1, *GOVERNOR_DEADLINE)
    left = (deadline - today).days
    if left > max(GOVERNOR_WARNING_DAYS):
        return 0
    threshold = min(t for t in GOVERNOR_WARNING_DAYS if t >= left)
    created = 0
    for uid in federation:
        created += await notify(
            session, uid, NotificationKind.DEADLINE_SOON, "Ходатайства на премии Губернатора",
            f"Срок подачи ходатайств на премии за спортивные результаты (Указ № 93-ук) – до {deadline:%d.%m.%Y}, осталось дней: {left}. "
            f"Основание – опубликованные протоколы за {deadline.year - 1} год.",
            dedup_key=f"governor:{deadline.year}:{threshold}:{uid}", external=threshold == min(GOVERNOR_WARNING_DAYS),
        )
    return created
