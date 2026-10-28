from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import (
    AthleteProfile,
    CoachAthleteLink,
    Competition,
    Discipline,
    Protocol,
    Result,
    User,
)
from app.models.enums import LinkStatus, ProtocolStatus, RoleCode
from app.schemas.results import HistoryItem, HistoryOut
from app.services.common import full_name

router = APIRouter(prefix="/athletes", tags=["athletes"])

Session = Annotated[AsyncSession, Depends(get_session)]
HistoryViewer = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION, RoleCode.ATHLETE, RoleCode.COACH))]


async def build_history(
    session: AsyncSession, athlete_id: int, discipline_id: int | None, year: int | None, limit: int, offset: int
) -> HistoryOut:
    athlete = await session.get(User, athlete_id)
    if athlete is None or await session.get(AthleteProfile, athlete_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Спортсмен не найден")

    # в историю попадают только результаты опубликованных протоколов (актуальная версия)
    latest = (
        select(Protocol.competition_id.label("competition_id"), func.max(Protocol.version).label("version"))
        .where(Protocol.status == ProtocolStatus.PUBLISHED).group_by(Protocol.competition_id).subquery()
    )
    participants = (
        select(Result.competition_id.label("competition_id"), func.count().label("n")).group_by(Result.competition_id).subquery()
    )
    stmt = (
        select(Result, Competition, Discipline.name, Protocol, participants.c.n)
        .join(Competition, Competition.id == Result.competition_id)
        .join(Discipline, Discipline.id == Competition.discipline_id)
        .join(latest, latest.c.competition_id == Result.competition_id)
        .join(Protocol, (Protocol.competition_id == latest.c.competition_id) & (Protocol.version == latest.c.version))
        .join(participants, participants.c.competition_id == Result.competition_id)
        .where(Result.athlete_id == athlete_id)
    )
    if discipline_id is not None:
        stmt = stmt.where(Competition.discipline_id == discipline_id)
    if year is not None:
        stmt = stmt.where(extract("year", Competition.start_date) == year)

    rows = (await session.execute(stmt.order_by(Competition.start_date.desc(), Result.id.desc()))).all()
    items = [
        HistoryItem(
            result_id=r.id, competition_id=c.id, competition_title=c.title, discipline=disc_name, level=c.level, rating_tier=c.rating_tier,
            start_date=c.start_date, end_date=c.end_date, place=r.place, status=r.status, score=r.score,
            time_seconds=r.time_seconds, tasks_solved=r.tasks_solved, participants=n, protocol_id=p.id, protocol_number=p.number,
        )
        for r, c, disc_name, p, n in rows
    ]
    return HistoryOut(
        athlete_id=athlete_id, athlete_name=full_name(athlete), total=len(items),
        prizes=sum(1 for i in items if i.place is not None and i.place <= 3), items=items[offset : offset + limit],
    )


async def ensure_can_view_athlete(session: AsyncSession, current: CurrentUser, athlete_id: int) -> None:
    """Спортсмен видит себя, тренер – активных подопечных, федерация – всех."""
    if current.active_role == RoleCode.ATHLETE and athlete_id != current.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Спортсмен видит только свои данные")
    if current.active_role == RoleCode.COACH:
        linked = await session.scalar(
            select(CoachAthleteLink.id).where(
                CoachAthleteLink.coach_id == current.user.id,
                CoachAthleteLink.athlete_id == athlete_id,
                CoachAthleteLink.status == LinkStatus.ACTIVE,
            ).limit(1)
        )
        if linked is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Спортсмен не привязан к вам как к тренеру")


@router.get("/me/history", response_model=HistoryOut, summary="История выступлений текущего спортсмена")
async def my_history(
    session: Session,
    current: Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))],
    discipline_id: int | None = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HistoryOut:
    return await build_history(session, current.user.id, discipline_id, year, limit, offset)


@router.get("/{athlete_id}/history", response_model=HistoryOut,
            summary="История выступлений: федерация – любого, тренер – подопечных, спортсмен – свою")
async def athlete_history(
    athlete_id: int,
    session: Session,
    current: HistoryViewer,
    discipline_id: int | None = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HistoryOut:
    await ensure_can_view_athlete(session, current, athlete_id)
    return await build_history(session, athlete_id, discipline_id, year, limit, offset)
