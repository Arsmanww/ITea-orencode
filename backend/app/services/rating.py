"""Рейтинг спортсменов региона (С9): очки за место по уровню соревнования, коэффициент стабильности.

Расчёт выполняется налету по опубликованным протоколам, поэтому любую цифру можно проверить:
в ответе по каждому спортсмену приведены исходные результаты, применённые очки и коэффициент.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgeGroup,
    AthleteEnrollment,
    Competition,
    Discipline,
    Organization,
    Protocol,
    Rank,
    RankAssignment,
    RatingRule,
    RatingSettings,
    Result,
    Sanction,
    Season,
    User,
)
from app.models.enums import ProtocolStatus, RatingTier, ResultStatus
from app.schemas.people import DisciplineRef
from app.schemas.rating import BreakdownItem, ExcludedItem, RatingItem, RatingTable
from app.services.common import full_name
from app.services.eligibility import age_on

PRIZE_PLACES = 3


@dataclass
class RatingConfig:
    coefficient: Decimal
    min_prizes: int
    points: dict[tuple[RatingTier, int], int]


async def load_config(session: AsyncSession) -> RatingConfig:
    settings = await session.scalar(select(RatingSettings).order_by(RatingSettings.id).limit(1))
    rules = (await session.scalars(select(RatingRule))).all()
    return RatingConfig(
        coefficient=settings.stability_coef if settings else Decimal("1.20"),
        min_prizes=settings.stability_min_prizes if settings else 2,
        points={(r.tier, r.place): r.points for r in rules},
    )


def as_of_date(season: Season, today: date) -> date:
    return min(today, season.date_to)


async def current_rank_orders(session: AsyncSession, discipline_id: int, as_of: date) -> dict[int, Rank]:
    """Действующий на дату разряд по дисциплине для каждого спортсмена."""
    rows = (await session.execute(
        select(RankAssignment, Rank).join(Rank, Rank.id == RankAssignment.rank_id)
        .where(RankAssignment.discipline_id == discipline_id, RankAssignment.assigned_at <= as_of)
        .order_by(RankAssignment.assigned_at, RankAssignment.id)
    )).all()
    result: dict[int, Rank] = {}
    for assignment, rank in rows:
        if assignment.valid_until is None or assignment.valid_until >= as_of:
            result[assignment.athlete_id] = rank
        else:
            result.pop(assignment.athlete_id, None)
    return result


async def compute_rating(
    session: AsyncSession,
    season: Season,
    discipline: Discipline,
    config: RatingConfig,
    today: date,
    *,
    age_group: AgeGroup | None = None,
    min_rank: Rank | None = None,
    limit: int = 100,
) -> RatingTable:
    as_of = as_of_date(season, today)

    # последняя опубликованная версия протокола каждого соревнования
    latest = (
        select(Protocol.competition_id.label("competition_id"), func.max(Protocol.version).label("version"))
        .where(Protocol.status == ProtocolStatus.PUBLISHED).group_by(Protocol.competition_id).subquery()
    )
    rows = (await session.execute(
        select(Result, Competition)
        .join(Competition, Competition.id == Result.competition_id)
        .join(latest, latest.c.competition_id == Competition.id)
        .where(Competition.discipline_id == discipline.id, Competition.end_date >= season.date_from,
               Competition.end_date <= season.date_to, Result.status == ResultStatus.RANKED)
        .order_by(Competition.end_date)
    )).all()

    by_athlete: dict[int, list[tuple[Result, Competition]]] = {}
    for result, comp in rows:
        by_athlete.setdefault(result.athlete_id, []).append((result, comp))
    if not by_athlete:
        return RatingTable(discipline=DisciplineRef(id=discipline.id, code=discipline.code, name=discipline.name),
                           total_athletes=0, items=[], excluded=[])

    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(by_athlete)))}
    sanctions = (await session.scalars(
        select(Sanction).where(Sanction.athlete_id.in_(by_athlete), Sanction.date_from <= as_of,
                               or_(Sanction.date_to.is_(None), Sanction.date_to >= as_of))
    )).all()
    sanctioned = {s.athlete_id: s for s in sanctions}
    orgs = {}
    for athlete_id, org_name in (await session.execute(
        select(AthleteEnrollment.athlete_id, Organization.name)
        .join(Organization, Organization.id == AthleteEnrollment.organization_id)
        .where(AthleteEnrollment.athlete_id.in_(by_athlete), AthleteEnrollment.discipline_id == discipline.id)
        .order_by(AthleteEnrollment.start_date)
    )).all():
        orgs[athlete_id] = org_name
    ranks = await current_rank_orders(session, discipline.id, as_of)

    items: list[RatingItem] = []
    excluded: list[ExcludedItem] = []
    for athlete_id, results in by_athlete.items():
        user = users[athlete_id]
        if athlete_id in sanctioned:
            s = sanctioned[athlete_id]
            until = f" до {s.date_to:%d.%m.%Y}" if s.date_to else ""
            kind = "Дисквалификация" if s.kind.value == "disqualification" else "Отстранение"
            excluded.append(ExcludedItem(athlete_id=athlete_id, athlete_name=full_name(user), reason=f"{kind}{until}"))
            continue
        age = age_on(user.birth_date, as_of)
        if age_group is not None and not (age_group.min_age <= age <= age_group.max_age):
            continue
        rank = ranks.get(athlete_id)
        if min_rank is not None and (rank is None or rank.order_no < min_rank.order_no):
            continue

        breakdown = [
            BreakdownItem(competition_id=c.id, title=c.title, date=c.end_date, tier=c.rating_tier, place=r.place,
                          points=config.points.get((c.rating_tier, r.place), 0) if r.place and r.place <= PRIZE_PLACES else 0)
            for r, c in results
        ]
        base = sum(b.points for b in breakdown)
        prizes = sum(1 for b in breakdown if b.place and b.place <= PRIZE_PLACES)
        coef = config.coefficient if prizes >= config.min_prizes else Decimal("1")
        items.append(RatingItem(
            place=0, athlete_id=athlete_id, athlete_name=full_name(user), birth_date=user.birth_date, age=age,
            organization=orgs.get(athlete_id), rank=rank.name if rank else None, base_points=base, prizes=prizes,
            coefficient=coef, total=(Decimal(base) * coef).quantize(Decimal("0.01")), breakdown=breakdown,
        ))

    items.sort(key=lambda i: (-i.total, -i.prizes, -sum(1 for b in i.breakdown if b.place == 1), i.athlete_name))
    place, previous = 0, None
    for index, item in enumerate(items, start=1):
        key = (item.total, item.prizes)
        if key != previous:
            place, previous = index, key
        item.place = place
    return RatingTable(discipline=DisciplineRef(id=discipline.id, code=discipline.code, name=discipline.name),
                       total_athletes=len(items), items=items[:limit], excluded=excluded)
