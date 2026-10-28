from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgeGroup,
    AthleteEnrollment,
    CoachAthleteLink,
    Competition,
    CompetitionAgeGroup,
    CompetitionApplication,
    Discipline,
    Sanction,
)
from app.models.enums import ApplicationStatus, CompetitionStatus, LinkStatus


def age_on(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


def ensure_registration_open(comp: Competition) -> None:
    if comp.status != CompetitionStatus.REGISTRATION_OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Приём заявок не ведётся (статус соревнования: {comp.status.value})")
    now = datetime.now(timezone.utc)
    if comp.registration_opens_at and now < comp.registration_opens_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Приём заявок ещё не начался")
    if comp.registration_deadline and now > comp.registration_deadline:
        raise HTTPException(status.HTTP_409_CONFLICT, "Приём заявок завершён")


def enrollment_conditions(comp: Competition, today: date):
    """Условия «спортсмен занимается дисциплиной соревнования».

    Занятия должны идти на день подачи заявки и не заканчиваться раньше старта соревнования.
    Требовать, чтобы они начались до даты старта, нельзя: заявки принимают, пока открыта
    регистрация, поэтому спортсмен, зарегистрировавшийся уже после начала соревнования,
    тоже имеет право заявиться.
    """
    until = max(today, comp.start_date)
    return (
        AthleteEnrollment.discipline_id == comp.discipline_id,
        AthleteEnrollment.start_date <= today,
        or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= until),
    )


async def active_link(session: AsyncSession, athlete_id: int, discipline_id: int) -> CoachAthleteLink | None:
    return await session.scalar(
        select(CoachAthleteLink).where(
            CoachAthleteLink.athlete_id == athlete_id,
            CoachAthleteLink.discipline_id == discipline_id,
            CoachAthleteLink.status == LinkStatus.ACTIVE,
        )
    )


async def validate_participation(session: AsyncSession, comp: Competition, athlete_id: int, birth_date: date) -> int:
    """Проверки допуска: дисциплина, возрастная группа, санкции, дубль заявки. Возвращает возраст на дату старта."""
    discipline = await session.get(Discipline, comp.discipline_id)
    enrolled = await session.scalar(
        select(AthleteEnrollment.id)
        .where(AthleteEnrollment.athlete_id == athlete_id, *enrollment_conditions(comp, date.today()))
        .limit(1)
    )
    if enrolled is None:
        raise unprocessable(f"Дисциплина не совпадает: спортсмен не занимается дисциплиной «{discipline.name}»")

    age = age_on(birth_date, comp.start_date)
    groups = (await session.scalars(
        select(AgeGroup).join(CompetitionAgeGroup, CompetitionAgeGroup.age_group_id == AgeGroup.id)
        .where(CompetitionAgeGroup.competition_id == comp.id).order_by(AgeGroup.min_age)
    )).all()
    if not any(g.min_age <= age <= g.max_age for g in groups):
        names = ", ".join(f"{g.name} ({g.min_age}–{g.max_age})" for g in groups)
        raise unprocessable(f"Возраст спортсмена на дату старта – {age} лет, он не входит в возрастные группы соревнования: {names}")

    sanction = await session.scalar(
        select(Sanction.id).where(
            Sanction.athlete_id == athlete_id,
            Sanction.date_from <= comp.start_date,
            or_(Sanction.date_to.is_(None), Sanction.date_to >= comp.start_date),
        ).limit(1)
    )
    if sanction is not None:
        raise unprocessable("У спортсмена действует дисквалификация или отстранение на дату проведения соревнования")

    duplicate = await session.scalar(
        select(CompetitionApplication.id).where(
            CompetitionApplication.competition_id == comp.id,
            CompetitionApplication.athlete_id == athlete_id,
            CompetitionApplication.status.in_([ApplicationStatus.PENDING, ApplicationStatus.APPROVED]),
        ).limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка этого спортсмена на соревнование уже подана")
    return age
