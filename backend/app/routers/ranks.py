from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import (
    AthleteProfile,
    CoachAthleteLink,
    Competition,
    Discipline,
    Rank,
    RankAssignment,
    RankRequest,
    Result,
    User,
)
from app.models.enums import LinkStatus, NotificationKind, RequestKind, RequestStatus, ResultStatus, RoleCode
from app.routers.results import latest_published
from app.schemas.judges import RequestDecision
from app.schemas.people import DisciplineRef, IdName, UserRef
from app.schemas.ranks import (
    ExpiringItem,
    ExpiringOut,
    MyRankOut,
    RankRequestIn,
    RankRequestOut,
    ResultBrief,
)
from app.services.common import full_name
from app.services.eligibility import active_link, unprocessable
from app.services.notifications import federation_user_ids, notify
from app.services.ranks import add_months, current_rank, evsk_match, expiring_items, make_validity

router = APIRouter(tags=["ranks"])

Session = Annotated[AsyncSession, Depends(get_session)]
Submitter = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE, RoleCode.COACH))]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
AthleteOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))]
ExpiryViewer = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION, RoleCode.ATHLETE, RoleCode.COACH, RoleCode.JUDGE))]


async def build_outs(session: AsyncSession, reqs: list[RankRequest]) -> list[RankRequestOut]:
    if not reqs:
        return []
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({r.athlete_id for r in reqs})))}
    ranks = {r.id: r for r in await session.scalars(select(Rank))}
    discs = {d.id: d for d in await session.scalars(select(Discipline))}
    comps = {c.id: c for c in await session.scalars(select(Competition).where(Competition.id.in_({r.competition_id for r in reqs})))}
    results = {r.id: r for r in await session.scalars(select(Result).where(Result.id.in_({r.result_id for r in reqs})))}
    assignments = {a.request_id: a for a in await session.scalars(
        select(RankAssignment).where(RankAssignment.request_id.in_([r.id for r in reqs])))}
    outs = []
    for r in reqs:
        a, res, comp = assignments.get(r.id), results[r.result_id], comps[r.competition_id]
        outs.append(RankRequestOut(
            id=r.id, athlete=UserRef(id=r.athlete_id, full_name=full_name(users[r.athlete_id])),
            rank=IdName(id=r.rank_id, name=ranks[r.rank_id].name),
            discipline=DisciplineRef(id=r.discipline_id, code=discs[r.discipline_id].code, name=discs[r.discipline_id].name),
            kind=r.kind, competition=IdName(id=comp.id, name=comp.title), result=ResultBrief(id=res.id, place=res.place, score=res.score),
            submitted_by_user_id=r.submitted_by_user_id, submitted_by_role=r.submitted_by_role, coach_id=r.coach_id, status=r.status,
            evsk_match=await evsk_match(session, ranks[r.rank_id], comp, res), created_at=r.created_at, decided_by=r.decided_by,
            decided_at=r.decided_at, decision_comment=r.decision_comment, order_number=a.order_number if a else None,
            order_date=a.order_date if a else None, valid_until=a.valid_until if a else None,
        ))
    return outs


@router.post("/ranks/requests", response_model=RankRequestOut, status_code=status.HTTP_201_CREATED,
             summary="Заявка на присвоение/подтверждение разряда: с тренером подаёт тренер, без тренера – спортсмен")
async def create_rank_request(data: RankRequestIn, request: Request, session: Session, current: Submitter) -> RankRequestOut:
    comp = await session.get(Competition, data.competition_id)
    if comp is None:
        raise unprocessable("Соревнование-основание не найдено")
    if current.active_role == RoleCode.ATHLETE:
        if data.athlete_id not in (None, current.user.id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Спортсмен может подать заявку только за себя")
        athlete_id = current.user.id
    else:
        if data.athlete_id is None:
            raise unprocessable("Укажите athlete_id спортсмена, за которого подаётся заявка")
        athlete_id = data.athlete_id
    athlete = await session.get(User, athlete_id)
    if athlete is None or await session.get(AthleteProfile, athlete_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Спортсмен не найден")

    link = await active_link(session, athlete_id, comp.discipline_id)
    if current.active_role == RoleCode.ATHLETE and link is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "У вас есть тренер по этой дисциплине: заявку на разряд подаёт тренер")
    if current.active_role == RoleCode.COACH and (link is None or link.coach_id != current.user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Спортсмен не привязан к вам по дисциплине соревнования")

    result = await session.get(Result, data.result_id)
    if result is None or result.competition_id != comp.id or result.athlete_id != athlete_id:
        raise unprocessable("Результат не принадлежит этому спортсмену в указанном соревновании")
    if result.status != ResultStatus.RANKED or result.place is None:
        raise unprocessable("Основанием может быть только результат участника в зачёте")
    if await latest_published(session, comp.id) is None:
        raise unprocessable("Результат не подтверждён: протокол соревнования ещё не опубликован")
    rank = await session.get(Rank, data.rank_id)
    if rank is None:
        raise unprocessable("Разряд не найден")

    current_ = await current_rank(session, athlete_id, comp.discipline_id)
    if data.kind == RequestKind.CONFIRM:
        if current_ is None or current_[1].id != rank.id:
            raise unprocessable("Подтвердить можно только имеющийся разряд по этой дисциплине")
    elif current_ is not None and rank.order_no <= current_[1].order_no:
        raise unprocessable(f"Присвоить можно только разряд выше имеющегося («{current_[1].name}»)")
    pending = await session.scalar(
        select(RankRequest.id).where(RankRequest.athlete_id == athlete_id, RankRequest.discipline_id == comp.discipline_id,
                                     RankRequest.status == RequestStatus.SUBMITTED).limit(1)
    )
    if pending is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "По этой дисциплине уже есть заявка на разряд, ожидающая рассмотрения")

    req = RankRequest(
        athlete_id=athlete_id, rank_id=rank.id, discipline_id=comp.discipline_id, kind=data.kind, competition_id=comp.id,
        result_id=result.id, submitted_by_user_id=current.user.id, submitted_by_role=current.active_role,
        coach_id=link.coach_id if link else None,
    )
    session.add(req)
    await session.flush()
    for uid in await federation_user_ids(session):
        await notify(session, uid, NotificationKind.RANK_REQUEST, "Заявка на разряд",
                     f"{full_name(athlete)}: {'присвоение' if data.kind == RequestKind.ASSIGN else 'подтверждение'} разряда «{rank.name}» "
                     f"по результату в «{comp.title}».", entity_type="rank_request", entity_id=req.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="rank_request.create", entity_type="rank_request", entity_id=req.id,
                     diff={"athlete_id": athlete_id, "rank_id": rank.id, "kind": data.kind.value, "result_id": result.id})
    await session.commit()
    await session.refresh(req)
    return (await build_outs(session, [req]))[0]


@router.get("/ranks/requests", response_model=list[RankRequestOut], summary="Мои заявки на разряд (спортсмен – свои, тренер – по подопечным)")
async def my_rank_requests(session: Session, current: Submitter) -> list[RankRequestOut]:
    col = RankRequest.athlete_id if current.active_role == RoleCode.ATHLETE else RankRequest.coach_id
    reqs = (await session.scalars(select(RankRequest).where(col == current.user.id).order_by(RankRequest.id.desc()))).all()
    return await build_outs(session, list(reqs))


@router.get("/federation/rank-requests", response_model=list[RankRequestOut], summary="Заявки на разряд (федерация)")
async def list_rank_requests(
    session: Session,
    current: FederationOnly,
    status_: Annotated[RequestStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[RankRequestOut]:
    stmt = select(RankRequest)
    if status_ is not None:
        stmt = stmt.where(RankRequest.status == status_)
    reqs = (await session.scalars(stmt.order_by(RankRequest.id.desc()).limit(limit))).all()
    return await build_outs(session, list(reqs))


@router.patch("/federation/rank-requests/{request_id}", response_model=RankRequestOut,
              summary="Утвердить приказ о присвоении разряда (дата приказа, срок действия) или отклонить")
async def decide_rank_request(request_id: int, data: RequestDecision, request: Request, session: Session, current: FederationOnly) -> RankRequestOut:
    req = await session.get(RankRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    if req.status != RequestStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Заявка уже рассмотрена (статус: {req.status.value})")
    rank = await session.get(Rank, req.rank_id)
    comp = await session.get(Competition, req.competition_id)
    athlete = await session.get(User, req.athlete_id)

    req.status, req.decided_by = data.status, current.user.id
    req.decided_at = datetime.now(timezone.utc)
    req.decision_comment = data.comment.strip() if data.comment else None
    if data.status == RequestStatus.APPROVED:
        order_date = data.order_date or date.today()
        if order_date > date.today():
            raise unprocessable("Дата приказа не может быть в будущем")
        if order_date < comp.end_date:
            raise unprocessable("Дата приказа не может быть раньше окончания соревнования-основания")
        valid_until = data.valid_until or (add_months(order_date, rank.validity_months) if rank.validity_months else None)
        if valid_until is not None and valid_until <= order_date:
            raise unprocessable("Срок действия должен быть позже даты приказа")
        session.add(RankAssignment(
            athlete_id=req.athlete_id, rank_id=rank.id, discipline_id=req.discipline_id, assigned_at=order_date, valid_until=valid_until,
            order_number=data.order_number.strip(), order_date=order_date, request_id=req.id,
        ))
        text = f"Разряд «{rank.name}» {'присвоен' if req.kind == RequestKind.ASSIGN else 'подтверждён'}, приказ № {data.order_number.strip()}" \
               + (f", действует до {valid_until:%d.%m.%Y}." if valid_until else ".")
    else:
        text = f"Заявка на разряд «{rank.name}» отклонена: {req.decision_comment}"
    await session.flush()
    for uid in {req.athlete_id, *([req.coach_id] if req.coach_id else [])}:
        await notify(session, uid, NotificationKind.RANK_REQUEST, "Решение по заявке на разряд",
                     f"{full_name(athlete)}: {text}", entity_type="rank_request", entity_id=req.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="rank_request.decide", entity_type="rank_request", entity_id=req.id,
                     diff={"status": data.status.value, "order_number": data.order_number})
    await session.commit()
    return (await build_outs(session, [req]))[0]


@router.get("/ranks/expiring", response_model=ExpiringOut,
            summary="Разряды и судейские категории, истекающие в ближайшие N дней (30/60)")
async def expiring(
    session: Session,
    current: ExpiryViewer,
    days: Annotated[int, Query(ge=1, le=365, description="Горизонт в днях, обычно 30 или 60")] = 30,
    include_expired: Annotated[bool, Query(description="Добавить уже истёкшие")] = False,
) -> ExpiringOut:
    today, role = date.today(), current.active_role
    pairs: set[tuple[int, int]] | None = None
    athlete_ids: set[int] | None = None
    judge_ids: set[int] | None = None
    ranks_on, cats_on = True, True
    if role == RoleCode.ATHLETE:
        athlete_ids, cats_on = {current.user.id}, False
    elif role == RoleCode.COACH:
        links = (await session.execute(
            select(CoachAthleteLink.athlete_id, CoachAthleteLink.discipline_id)
            .where(CoachAthleteLink.coach_id == current.user.id, CoachAthleteLink.status == LinkStatus.ACTIVE)
        )).all()
        pairs = {(a, d) for a, d in links}
        athlete_ids, cats_on = {a for a, _ in pairs}, False
    elif role == RoleCode.JUDGE:
        judge_ids, ranks_on = {current.user.id}, False

    items = await expiring_items(session, today, days, athlete_ids=athlete_ids, judge_ids=judge_ids,
                                 include_ranks=ranks_on, include_categories=cats_on, include_expired=include_expired)
    if pairs is not None:
        items = [i for i in items if (i["subject_id"], i["discipline_id"]) in pairs]
    return ExpiringOut(days=days, total=len(items), items=[ExpiringItem(**{k: v for k, v in i.items() if k != "discipline_id"}) for i in items])


@router.get("/athletes/me/ranks", response_model=list[MyRankOut], summary="Мои разряды по дисциплинам со сроками и предупреждениями")
async def my_ranks(session: Session, current: AthleteOnly) -> list[MyRankOut]:
    today = date.today()
    disc_ids = (await session.scalars(select(RankAssignment.discipline_id).where(RankAssignment.athlete_id == current.user.id).distinct())).all()
    discs = {d.id: d for d in await session.scalars(select(Discipline).where(Discipline.id.in_(disc_ids)))} if disc_ids else {}
    out = []
    for did in sorted(disc_ids):
        assignment, rank = await current_rank(session, current.user.id, did)
        pending = await session.scalar(select(RankRequest.id).where(
            RankRequest.athlete_id == current.user.id, RankRequest.discipline_id == did, RankRequest.status == RequestStatus.SUBMITTED).limit(1))
        out.append(MyRankOut(discipline=DisciplineRef(id=did, code=discs[did].code, name=discs[did].name),
                             rank=make_validity(rank.id, rank.name, assignment.assigned_at, assignment.valid_until, today),
                             pending_request=pending is not None))
    return out
