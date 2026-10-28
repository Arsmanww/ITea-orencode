from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Competition,
    Discipline,
    JudgeCategory,
    JudgeCategoryAssignment,
    Rank,
    RankAssignment,
    RankRequest,
    RankRequirement,
    Result,
    User,
)
from app.models.enums import RequestStatus, ResultStatus
from app.services.common import full_name

WARNING_DAYS = 60


def days_left(valid_until: date | None, today: date) -> int | None:
    return None if valid_until is None else (valid_until - today).days


def add_months(d: date, months: int) -> date:
    import calendar

    y, m = divmod(d.month - 1 + months, 12)
    y, m = y + d.year, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


async def current_rank(session: AsyncSession, athlete_id: int, discipline_id: int) -> tuple[RankAssignment, Rank] | None:
    """Последнее присвоение по дисциплине (в том числе истёкшее – разряд остаётся достигнутым)."""
    row = (await session.execute(
        select(RankAssignment, Rank).join(Rank, Rank.id == RankAssignment.rank_id)
        .where(RankAssignment.athlete_id == athlete_id, RankAssignment.discipline_id == discipline_id)
        .order_by(RankAssignment.assigned_at.desc(), RankAssignment.id.desc()).limit(1)
    )).first()
    return (row[0], row[1]) if row else None


async def evsk_match(session: AsyncSession, rank: Rank, comp: Competition, result: Result) -> bool | None:
    """Подсказка: может ли результат соответствовать требованиям ЕВСК (None – требования не заданы)."""
    reqs = (await session.scalars(
        select(RankRequirement).where(
            RankRequirement.rank_id == rank.id, RankRequirement.level == comp.level,
            or_(RankRequirement.discipline_id.is_(None), RankRequirement.discipline_id == comp.discipline_id),
        )
    )).all()
    if not reqs:
        return None
    participants = await session.scalar(
        select(func.count()).select_from(Result).where(Result.competition_id == comp.id, Result.status == ResultStatus.RANKED)
    ) or 0
    return any(
        result.place is not None and result.place <= r.max_place and (r.min_participants is None or participants >= r.min_participants)
        for r in reqs
    )


def _latest(model: Any, partition: tuple) -> Any:
    rn = func.row_number().over(partition_by=partition, order_by=(model.assigned_at.desc(), model.id.desc())).label("rn")
    return select(model.id.label("id"), rn).subquery()


async def expiring_items(
    session: AsyncSession,
    today: date,
    horizon_days: int,
    *,
    athlete_ids: set[int] | None = None,
    judge_ids: set[int] | None = None,
    include_ranks: bool = True,
    include_categories: bool = True,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    """Текущие разряды и судейские категории, срок которых истекает в ближайшие horizon_days дней.

    Учитывается только последнее присвоение по (спортсмен, дисциплина) или по судье.
    """
    limit = today + timedelta(days=horizon_days)
    items: list[dict[str, Any]] = []

    if include_ranks and athlete_ids != set():
        latest = _latest(RankAssignment, (RankAssignment.athlete_id, RankAssignment.discipline_id))
        stmt = (
            select(RankAssignment, Rank, Discipline, User)
            .join(latest, latest.c.id == RankAssignment.id)
            .join(Rank, Rank.id == RankAssignment.rank_id)
            .join(Discipline, Discipline.id == RankAssignment.discipline_id)
            .join(User, User.id == RankAssignment.athlete_id)
            .where(latest.c.rn == 1, RankAssignment.valid_until.is_not(None), RankAssignment.valid_until <= limit)
        )
        if not include_expired:
            stmt = stmt.where(RankAssignment.valid_until >= today)
        if athlete_ids is not None:
            stmt = stmt.where(RankAssignment.athlete_id.in_(athlete_ids))
        for a, rank, disc, user in (await session.execute(stmt)).all():
            items.append(dict(kind="rank", assignment_id=a.id, subject_id=user.id, subject_name=full_name(user), title=rank.name,
                              discipline=disc.name, discipline_id=disc.id, valid_until=a.valid_until,
                              days_left=days_left(a.valid_until, today), expired=a.valid_until < today))

    if include_categories and judge_ids != set():
        latest = _latest(JudgeCategoryAssignment, (JudgeCategoryAssignment.judge_id,))
        stmt = (
            select(JudgeCategoryAssignment, JudgeCategory, User)
            .join(latest, latest.c.id == JudgeCategoryAssignment.id)
            .join(JudgeCategory, JudgeCategory.id == JudgeCategoryAssignment.category_id)
            .join(User, User.id == JudgeCategoryAssignment.judge_id)
            .where(latest.c.rn == 1, JudgeCategoryAssignment.valid_until.is_not(None), JudgeCategoryAssignment.valid_until <= limit)
        )
        if not include_expired:
            stmt = stmt.where(JudgeCategoryAssignment.valid_until >= today)
        if judge_ids is not None:
            stmt = stmt.where(JudgeCategoryAssignment.judge_id.in_(judge_ids))
        for a, cat, user in (await session.execute(stmt)).all():
            items.append(dict(kind="judge_category", assignment_id=a.id, subject_id=user.id, subject_name=full_name(user), title=cat.name,
                              discipline=None, discipline_id=None, valid_until=a.valid_until,
                              days_left=days_left(a.valid_until, today), expired=a.valid_until < today))

    items.sort(key=lambda i: (i["valid_until"], i["subject_name"]))
    return items


def make_validity(id_: int, name: str, assigned_at: date | None, valid_until: date | None, today: date):
    """Срок действия с предупреждением: истёк или осталось не больше WARNING_DAYS."""
    from app.schemas.people import ValidityInfo

    left = days_left(valid_until, today)
    expired = left is not None and left < 0
    return ValidityInfo(
        id=id_, name=name, assigned_at=assigned_at, valid_until=valid_until, days_left=left,
        expired=expired, warning=expired or (left is not None and left <= WARNING_DAYS),
    )


async def evsk_candidates(session: AsyncSession, comp: Competition) -> list[dict[str, Any]]:
    """Подсветка протокола: чей результат может соответствовать разрядным требованиям ЕВСК.

    Для каждого участника в зачёте берётся самый высокий разряд, требования которого выполнены
    (уровень соревнования, место, число участников в зачёте). Возвращаются только те, кому это даёт
    присвоение более высокого разряда или подтверждение имеющегося."""
    reqs = (await session.execute(
        select(RankRequirement, Rank).join(Rank, Rank.id == RankRequirement.rank_id)
        .where(RankRequirement.level == comp.level,
               or_(RankRequirement.discipline_id.is_(None), RankRequirement.discipline_id == comp.discipline_id))
    )).all()
    if not reqs:
        return []
    results = (await session.execute(
        select(Result, User).join(User, User.id == Result.athlete_id)
        .where(Result.competition_id == comp.id, Result.status == ResultStatus.RANKED, Result.place.is_not(None))
        .order_by(Result.place)
    )).all()
    participants = len(results)
    pending = set((await session.scalars(
        select(RankRequest.athlete_id).where(RankRequest.competition_id == comp.id, RankRequest.status == RequestStatus.SUBMITTED)
    )).all())
    out = []
    for result, user in results:
        matched = [rank for req, rank in reqs
                   if result.place <= req.max_place and (req.min_participants is None or participants >= req.min_participants)]
        if not matched:
            continue
        best = max(matched, key=lambda r: r.order_no)
        current = await current_rank(session, user.id, comp.discipline_id)
        current_rank_ = current[1] if current else None
        if current_rank_ is not None and current_rank_.order_no > best.order_no:
            continue
        out.append(dict(athlete_id=user.id, full_name=full_name(user), place=result.place, rank_id=best.id, rank=best.name,
                        current_rank=current_rank_.name if current_rank_ else None,
                        kind="confirm" if current_rank_ is not None and current_rank_.id == best.id else "assign",
                        request_pending=user.id in pending))
    return out
