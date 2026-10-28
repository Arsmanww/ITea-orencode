"""Дисквалификации и отстранения (федерация).

Действующая санкция исключает спортсмена из рейтинга (services/rating.py) и не даёт подать заявку
на соревнование, которое проходит в период её действия (services/eligibility.py).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import AthleteProfile, CoachAthleteLink, Competition, Sanction, User
from app.models.enums import LinkStatus, NotificationKind, RoleCode, SanctionKind
from app.schemas.people import IdName, UserRef
from app.services.common import full_name
from app.services.notifications import notify

router = APIRouter(prefix="/federation/sanctions", tags=["federation"])

Session = Annotated[AsyncSession, Depends(get_session)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
KIND_TITLE = {SanctionKind.DISQUALIFICATION: "Дисквалификация", SanctionKind.SUSPENSION: "Отстранение"}


class SanctionIn(BaseModel):
    athlete_id: int
    kind: SanctionKind
    date_from: date
    date_to: date | None = Field(default=None, description="Пусто – бессрочно до решения федерации")
    reason: str = Field(min_length=3, max_length=2000)
    competition_id: int | None = Field(default=None, description="Соревнование, на котором зафиксировано нарушение")

    @model_validator(mode="after")
    def _dates(self) -> "SanctionIn":
        if self.date_to is not None and self.date_to < self.date_from:
            raise ValueError("Дата окончания раньше даты начала")
        return self


class SanctionEnd(BaseModel):
    date_to: date = Field(description="Последний день действия санкции")


class SanctionOut(BaseModel):
    id: int
    athlete: UserRef
    kind: SanctionKind
    date_from: date
    date_to: date | None
    reason: str
    competition: IdName | None
    active: bool
    created_at: AwareDatetime


def _is_active(s: Sanction, today: date) -> bool:
    return s.date_from <= today and (s.date_to is None or s.date_to >= today)


async def _outs(session: AsyncSession, items: list[Sanction]) -> list[SanctionOut]:
    if not items:
        return []
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({s.athlete_id for s in items})))}
    comp_ids = {s.competition_id for s in items if s.competition_id}
    comps = {c.id: c for c in await session.scalars(select(Competition).where(Competition.id.in_(comp_ids)))} if comp_ids else {}
    today = date.today()
    return [
        SanctionOut(id=s.id, athlete=UserRef(id=s.athlete_id, full_name=full_name(users[s.athlete_id])), kind=s.kind, date_from=s.date_from,
                    date_to=s.date_to, reason=s.reason,
                    competition=IdName(id=s.competition_id, name=comps[s.competition_id].title) if s.competition_id else None,
                    active=_is_active(s, today), created_at=s.created_at)
        for s in items
    ]


async def _notify_parties(session: AsyncSession, s: Sanction, title: str, body: str) -> None:
    coaches = (await session.scalars(
        select(CoachAthleteLink.coach_id).where(CoachAthleteLink.athlete_id == s.athlete_id, CoachAthleteLink.status == LinkStatus.ACTIVE)
    )).all()
    for uid in {s.athlete_id, *coaches}:
        await notify(session, uid, NotificationKind.SANCTION, title, body, entity_type="sanction", entity_id=s.id)


@router.get("", response_model=list[SanctionOut], summary="Дисквалификации и отстранения")
async def list_sanctions(
    session: Session,
    current: FederationOnly,
    active_only: bool = False,
    athlete_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[SanctionOut]:
    stmt = select(Sanction)
    if athlete_id is not None:
        stmt = stmt.where(Sanction.athlete_id == athlete_id)
    if active_only:
        today = date.today()
        stmt = stmt.where(Sanction.date_from <= today, or_(Sanction.date_to.is_(None), Sanction.date_to >= today))
    items = (await session.scalars(stmt.order_by(Sanction.date_from.desc(), Sanction.id.desc()).limit(limit))).all()
    return await _outs(session, list(items))


@router.post("", response_model=SanctionOut, status_code=status.HTTP_201_CREATED,
             summary="Зафиксировать дисквалификацию или отстранение: спортсмен исключается из рейтинга на срок действия")
async def create_sanction(data: SanctionIn, request: Request, session: Session, current: FederationOnly) -> SanctionOut:
    if await session.get(AthleteProfile, data.athlete_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Спортсмен не найден")
    if data.competition_id is not None and await session.get(Competition, data.competition_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Соревнование не найдено")
    s = Sanction(athlete_id=data.athlete_id, kind=data.kind, date_from=data.date_from, date_to=data.date_to,
                 reason=data.reason.strip(), competition_id=data.competition_id)
    session.add(s)
    await session.flush()
    athlete = await session.get(User, data.athlete_id)
    period = f"с {data.date_from:%d.%m.%Y}" + (f" по {data.date_to:%d.%m.%Y}" if data.date_to else " до решения федерации")
    await _notify_parties(session, s, KIND_TITLE[data.kind],
                          f"{full_name(athlete)}: {KIND_TITLE[data.kind].lower()} {period}. Основание: {s.reason}. "
                          "На это время спортсмен не попадает в рейтинг и не допускается к заявкам.")
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="sanction.create",
                     entity_type="sanction", entity_id=s.id,
                     diff={"athlete_id": s.athlete_id, "kind": s.kind.value, "date_from": str(s.date_from), "date_to": str(s.date_to)})
    await session.commit()
    await session.refresh(s)
    return (await _outs(session, [s]))[0]


@router.patch("/{sanction_id}", response_model=SanctionOut, summary="Досрочно завершить санкцию (задать последний день действия)")
async def end_sanction(sanction_id: int, data: SanctionEnd, request: Request, session: Session, current: FederationOnly) -> SanctionOut:
    s = await session.get(Sanction, sanction_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Санкция не найдена")
    if data.date_to < s.date_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Дата окончания раньше даты начала")
    if s.date_to is not None and data.date_to > s.date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Срок можно только сократить")
    before = str(s.date_to)
    s.date_to = data.date_to
    athlete = await session.get(User, s.athlete_id)
    await _notify_parties(session, s, f"{KIND_TITLE[s.kind]} завершена",
                          f"{full_name(athlete)}: {KIND_TITLE[s.kind].lower()} действует по {data.date_to:%d.%m.%Y} включительно.")
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="sanction.end",
                     entity_type="sanction", entity_id=s.id, diff={"date_to": {"before": before, "after": str(data.date_to)}})
    await session.commit()
    return (await _outs(session, [s]))[0]
