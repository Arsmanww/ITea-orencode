from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import (
    AthleteEnrollment,
    AthleteProfile,
    CoachAthleteLink,
    CoachLinkHistory,
    Discipline,
    User,
)
from app.models.enums import LinkStatus, NotificationKind, RoleCode
from app.schemas.coach_links import (
    CoachAthleteOut,
    CoachRequestAnswer,
    CoachRequestDecision,
    LinkHistoryOut,
    LinkOut,
    LinkRequestIn,
    LinkStatusChange,
)
from app.schemas.people import DisciplineRef, UserRef
from app.services.common import full_name
from app.services.eligibility import age_on, unprocessable
from app.services.notifications import notify
from app.services.ranks import current_rank, make_validity

coach_router = APIRouter(prefix="/coach", tags=["coach"])
athlete_router = APIRouter(prefix="/athlete", tags=["athlete"])

Session = Annotated[AsyncSession, Depends(get_session)]
CoachOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.COACH))]
AthleteOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))]

OPEN_STATUSES = (LinkStatus.PENDING, LinkStatus.ACTIVE, LinkStatus.SUSPENDED)


async def build_link_outs(session: AsyncSession, links: list[CoachAthleteLink]) -> list[LinkOut]:
    if not links:
        return []
    user_ids = {l.coach_id for l in links} | {l.athlete_id for l in links}
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(user_ids)))}
    discs = {d.id: d for d in await session.scalars(select(Discipline))}
    return [
        LinkOut(
            id=l.id, status=l.status,
            coach=UserRef(id=l.coach_id, full_name=full_name(users[l.coach_id])),
            athlete=UserRef(id=l.athlete_id, full_name=full_name(users[l.athlete_id])),
            discipline=DisciplineRef(id=l.discipline_id, code=discs[l.discipline_id].code, name=discs[l.discipline_id].name),
            requested_at=l.requested_at, confirmed_at=l.confirmed_at, ended_at=l.ended_at,
        )
        for l in links
    ]


def _history(link: CoachAthleteLink, old: LinkStatus | None, new: LinkStatus, by: int, comment: str | None) -> CoachLinkHistory:
    return CoachLinkHistory(link_id=link.id, old_status=old, new_status=new, changed_by=by, comment=comment)


@coach_router.post("/athletes/link-request", response_model=LinkOut, status_code=status.HTTP_201_CREATED,
                   summary="Тренер отправляет запрос на привязку спортсмена по дисциплине")
async def create_link_request(data: LinkRequestIn, request: Request, session: Session, current: CoachOnly) -> LinkOut:
    if data.athlete_id is not None:
        athlete = await session.get(User, data.athlete_id)
    else:
        athlete = await session.scalar(select(User).where(User.email == data.athlete_email.strip().lower()))
    if athlete is None or await session.get(AthleteProfile, athlete.id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Спортсмен не найден")
    if athlete.id == current.user.id:
        raise unprocessable("Нельзя привязать самого себя")
    discipline = await session.get(Discipline, data.discipline_id)
    if discipline is None:
        raise unprocessable("Дисциплина не найдена")

    today = date.today()
    enrolled = await session.scalar(
        select(AthleteEnrollment.id).where(
            AthleteEnrollment.athlete_id == athlete.id, AthleteEnrollment.discipline_id == discipline.id,
            AthleteEnrollment.start_date <= today, or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= today),
        ).limit(1)
    )
    if enrolled is None:
        raise unprocessable(f"Спортсмен не занимается дисциплиной «{discipline.name}»")

    same = await session.scalar(
        select(CoachAthleteLink.id).where(
            CoachAthleteLink.coach_id == current.user.id, CoachAthleteLink.athlete_id == athlete.id,
            CoachAthleteLink.discipline_id == discipline.id, CoachAthleteLink.status.in_(OPEN_STATUSES),
        ).limit(1)
    )
    if same is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Запрос или связка с этим спортсменом по дисциплине уже существует")
    other = await session.scalar(
        select(CoachAthleteLink.id).where(
            CoachAthleteLink.athlete_id == athlete.id, CoachAthleteLink.discipline_id == discipline.id,
            CoachAthleteLink.status == LinkStatus.ACTIVE,
        ).limit(1)
    )
    if other is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "У спортсмена уже есть тренер по этой дисциплине")

    link = CoachAthleteLink(coach_id=current.user.id, athlete_id=athlete.id, discipline_id=discipline.id,
                            status=LinkStatus.PENDING, initiated_by_user_id=current.user.id)
    session.add(link)
    await session.flush()
    session.add(_history(link, None, LinkStatus.PENDING, current.user.id, "Запрос на привязку"))
    await notify(session, athlete.id, NotificationKind.LINK_REQUEST, "Запрос на привязку тренера",
                 f"Тренер {full_name(current.user)} просит привязать вас по дисциплине «{discipline.name}».",
                 entity_type="coach_athlete_link", entity_id=link.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="coach_link.request", entity_type="coach_athlete_link", entity_id=link.id,
                     diff={"athlete_id": athlete.id, "discipline_id": discipline.id})
    await session.commit()
    await session.refresh(link)
    return (await build_link_outs(session, [link]))[0]


@coach_router.get("/athletes", response_model=list[CoachAthleteOut], summary="Подопечные тренера (по умолчанию подтверждённые)")
async def coach_athletes(
    session: Session,
    current: CoachOnly,
    status_: Annotated[LinkStatus | None, Query(alias="status")] = LinkStatus.ACTIVE,
    with_suspended: Annotated[bool, Query(description="Вместе с активными показать приостановленные связи")] = False,
    discipline_id: int | None = None,
) -> list[CoachAthleteOut]:
    stmt = select(CoachAthleteLink).where(CoachAthleteLink.coach_id == current.user.id)
    if status_ is not None and with_suspended and status_ == LinkStatus.ACTIVE:
        stmt = stmt.where(CoachAthleteLink.status.in_([LinkStatus.ACTIVE, LinkStatus.SUSPENDED]))
    elif status_ is not None:
        stmt = stmt.where(CoachAthleteLink.status == status_)
    if discipline_id is not None:
        stmt = stmt.where(CoachAthleteLink.discipline_id == discipline_id)
    links = (await session.scalars(stmt.order_by(CoachAthleteLink.id))).all()
    if not links:
        return []
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({l.athlete_id for l in links})))}
    discs = {d.id: d for d in await session.scalars(select(Discipline))}
    today = date.today()
    out = []
    for l in links:
        u, d = users[l.athlete_id], discs[l.discipline_id]
        cur = await current_rank(session, l.athlete_id, l.discipline_id)
        out.append(CoachAthleteOut(
            link_id=l.id, athlete=UserRef(id=u.id, full_name=full_name(u)), birth_date=u.birth_date, age=age_on(u.birth_date, today),
            discipline=DisciplineRef(id=d.id, code=d.code, name=d.name), status=l.status, since=l.confirmed_at,
            rank=make_validity(cur[1].id, cur[1].name, cur[0].assigned_at, cur[0].valid_until, today) if cur else None,
        ))
    return out


@athlete_router.get("/coach-requests", response_model=list[LinkOut], summary="Входящие запросы тренеров (спортсмен)")
async def my_coach_requests(
    session: Session,
    current: AthleteOnly,
    status_: Annotated[LinkStatus | None, Query(alias="status")] = None,
) -> list[LinkOut]:
    stmt = select(CoachAthleteLink).where(CoachAthleteLink.athlete_id == current.user.id)
    if status_ is not None:
        stmt = stmt.where(CoachAthleteLink.status == status_)
    links = (await session.scalars(stmt.order_by(CoachAthleteLink.status != LinkStatus.PENDING, CoachAthleteLink.requested_at.desc()))).all()
    return await build_link_outs(session, list(links))


@athlete_router.patch("/coach-requests/{link_id}", response_model=LinkOut, summary="Подтвердить (accepted) или отклонить (rejected) запрос тренера")
async def answer_coach_request(link_id: int, data: CoachRequestDecision, request: Request, session: Session, current: AthleteOnly) -> LinkOut:
    link = await session.get(CoachAthleteLink, link_id)
    if link is None or link.athlete_id != current.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запрос не найден")
    if link.status != LinkStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Запрос уже обработан (статус: {link.status.value})")

    now = datetime.now(timezone.utc)
    if data.status == CoachRequestAnswer.ACCEPTED:
        other = await session.scalar(
            select(CoachAthleteLink.id).where(
                CoachAthleteLink.athlete_id == link.athlete_id, CoachAthleteLink.discipline_id == link.discipline_id,
                CoachAthleteLink.status == LinkStatus.ACTIVE, CoachAthleteLink.id != link.id,
            ).limit(1)
        )
        if other is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "У вас уже есть активный тренер по этой дисциплине")
        link.status, link.confirmed_at = LinkStatus.ACTIVE, now
        comment, title = data.comment or "Привязка подтверждена спортсменом", "Спортсмен подтвердил привязку"
    else:
        link.status, link.ended_at = LinkStatus.ENDED, now
        comment, title = data.comment or "Запрос отклонён спортсменом", "Спортсмен отклонил запрос на привязку"
    session.add(_history(link, LinkStatus.PENDING, link.status, current.user.id, comment))
    await notify(session, link.coach_id, NotificationKind.LINK_REQUEST, title,
                 f"{full_name(current.user)}: {comment}", entity_type="coach_athlete_link", entity_id=link.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="coach_link.answer", entity_type="coach_athlete_link", entity_id=link.id,
                     diff={"result": link.status.value})
    await session.commit()
    return (await build_link_outs(session, [link]))[0]


links_router = APIRouter(prefix="/links", tags=["coach"])
LinkParty = Annotated[CurrentUser, Depends(require_role(RoleCode.COACH, RoleCode.ATHLETE))]
LinkViewer = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION, RoleCode.COACH, RoleCode.ATHLETE))]

# допустимые переходы по инициативе тренера или спортсмена (pending обрабатывается в coach-requests)
LINK_TRANSITIONS: dict[LinkStatus, set[LinkStatus]] = {
    LinkStatus.PENDING: {LinkStatus.ENDED},
    LinkStatus.ACTIVE: {LinkStatus.SUSPENDED, LinkStatus.ENDED},
    LinkStatus.SUSPENDED: {LinkStatus.ACTIVE, LinkStatus.ENDED},
    LinkStatus.ENDED: set(),
}
LINK_VERBS = {LinkStatus.SUSPENDED: "приостановил(а)", LinkStatus.ACTIVE: "возобновил(а)", LinkStatus.ENDED: "завершил(а)"}


async def _own_link(session: AsyncSession, link_id: int, current: CurrentUser) -> CoachAthleteLink:
    link = await session.get(CoachAthleteLink, link_id)
    party = {RoleCode.COACH: link.coach_id, RoleCode.ATHLETE: link.athlete_id}.get(current.active_role) if link else None
    if link is None or (current.active_role != RoleCode.FEDERATION and party != current.user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Связь не найдена")
    return link


@links_router.patch("/{link_id}", response_model=LinkOut,
                    summary="Приостановить, возобновить или завершить связь тренер–спортсмен (любая из сторон)")
async def change_link_status(link_id: int, data: LinkStatusChange, request: Request, session: Session, current: LinkParty) -> LinkOut:
    link = await _own_link(session, link_id, current)
    if data.status not in LINK_TRANSITIONS[link.status]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Переход {link.status.value} → {data.status.value} недопустим")
    if link.status == LinkStatus.PENDING and current.active_role != RoleCode.COACH:
        raise HTTPException(status.HTTP_409_CONFLICT, "На запрос тренера ответьте через «Подтвердить» или «Отклонить»")
    if data.status == LinkStatus.ACTIVE:
        other = await session.scalar(
            select(CoachAthleteLink.id).where(
                CoachAthleteLink.athlete_id == link.athlete_id, CoachAthleteLink.discipline_id == link.discipline_id,
                CoachAthleteLink.status == LinkStatus.ACTIVE, CoachAthleteLink.id != link.id,
            ).limit(1)
        )
        if other is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "У спортсмена уже есть активный тренер по этой дисциплине")
    old = link.status
    link.status = data.status
    if data.status == LinkStatus.ENDED:
        link.ended_at = datetime.now(timezone.utc)
    comment = data.comment.strip() if data.comment and data.comment.strip() else None
    session.add(_history(link, old, data.status, current.user.id, comment))
    discipline = await session.get(Discipline, link.discipline_id)
    other_side = link.athlete_id if current.active_role == RoleCode.COACH else link.coach_id
    who = "Тренер" if current.active_role == RoleCode.COACH else "Спортсмен"
    await notify(session, other_side, NotificationKind.LINK_REQUEST, "Изменён статус связи тренер–спортсмен",
                 f"{who} {full_name(current.user)} {LINK_VERBS[data.status]} связь по дисциплине «{discipline.name}»."
                 + (f" Комментарий: {comment}" if comment else ""), entity_type="coach_athlete_link", entity_id=link.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="coach_link.status", entity_type="coach_athlete_link", entity_id=link.id,
                     diff={"from": old.value, "to": data.status.value, "comment": comment})
    await session.commit()
    return (await build_link_outs(session, [link]))[0]


@links_router.get("/{link_id}/history", response_model=list[LinkHistoryOut], summary="История изменений связи тренер–спортсмен")
async def link_history(link_id: int, session: Session, current: LinkViewer) -> list[LinkHistoryOut]:
    link = await _own_link(session, link_id, current)
    rows = (await session.execute(
        select(CoachLinkHistory, User).join(User, User.id == CoachLinkHistory.changed_by)
        .where(CoachLinkHistory.link_id == link.id).order_by(CoachLinkHistory.changed_at, CoachLinkHistory.id)
    )).all()
    return [LinkHistoryOut(old_status=h.old_status, new_status=h.new_status, changed_by=UserRef(id=u.id, full_name=full_name(u)),
                           changed_at=h.changed_at, comment=h.comment) for h, u in rows]
