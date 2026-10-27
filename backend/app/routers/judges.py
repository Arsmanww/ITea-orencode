from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import (
    Competition,
    CompetitionApplication,
    CompetitionJudge,
    JudgeCategory,
    JudgeCategoryAssignment,
    JudgeCategoryRequest,
    JudgePosition,
    JudgeProfile,
    User,
)
from app.models.enums import ApplicationStatus, CompetitionStatus, NotificationKind, RequestKind, RequestStatus, RoleCode
from app.schemas.judges import (
    CategoryRequestIn,
    CategoryRequestOut,
    CompetitionBrief,
    JudgeAssignIn,
    JudgeAssignmentOut,
    MyAssignmentsOut,
    RequestDecision,
)
from app.schemas.people import IdName, UserRef
from app.services.common import full_name, get_competition_or_404
from app.services.eligibility import unprocessable
from app.services.notifications import federation_user_ids, notify
from app.services.ranks import add_months, make_validity

Session = Annotated[AsyncSession, Depends(get_session)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
JudgeOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.JUDGE))]
Authed = Annotated[CurrentUser, Depends(get_current_user)]

collegium_router = APIRouter(prefix="/competitions/{competition_id}/judges", tags=["judges"])
judge_router = APIRouter(prefix="/judges/me", tags=["judges"])
federation_router = APIRouter(prefix="/federation/judge-requests", tags=["judges"])

CHIEF_POSITION = "Главный судья"


async def latest_category(session: AsyncSession, judge_id: int) -> tuple[JudgeCategoryAssignment, JudgeCategory] | None:
    row = (await session.execute(
        select(JudgeCategoryAssignment, JudgeCategory).join(JudgeCategory, JudgeCategory.id == JudgeCategoryAssignment.category_id)
        .where(JudgeCategoryAssignment.judge_id == judge_id)
        .order_by(JudgeCategoryAssignment.assigned_at.desc(), JudgeCategoryAssignment.id.desc()).limit(1)
    )).first()
    return (row[0], row[1]) if row else None


async def build_assignment_outs(session: AsyncSession, rows: list[CompetitionJudge]) -> list[JudgeAssignmentOut]:
    if not rows:
        return []
    comps = {c.id: c for c in await session.scalars(select(Competition).where(Competition.id.in_({r.competition_id for r in rows})))}
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({r.judge_id for r in rows})))}
    positions = {p.id: p for p in await session.scalars(select(JudgePosition))}
    return [
        JudgeAssignmentOut(
            id=r.id,
            competition=CompetitionBrief(id=r.competition_id, title=comps[r.competition_id].title, start_date=comps[r.competition_id].start_date,
                                         end_date=comps[r.competition_id].end_date, status=comps[r.competition_id].status),
            judge=UserRef(id=r.judge_id, full_name=full_name(users[r.judge_id])),
            position=IdName(id=r.position_id, name=positions[r.position_id].name), assigned_at=r.created_at,
        )
        for r in rows
    ]


async def build_request_outs(session: AsyncSession, reqs: list[JudgeCategoryRequest]) -> list[CategoryRequestOut]:
    if not reqs:
        return []
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({r.judge_id for r in reqs})))}
    cats = {c.id: c for c in await session.scalars(select(JudgeCategory))}
    assignments = {a.request_id: a for a in await session.scalars(
        select(JudgeCategoryAssignment).where(JudgeCategoryAssignment.request_id.in_([r.id for r in reqs])))}
    outs = []
    for r in reqs:
        a = assignments.get(r.id)
        outs.append(CategoryRequestOut(
            id=r.id, judge=UserRef(id=r.judge_id, full_name=full_name(users[r.judge_id])),
            category=IdName(id=r.category_id, name=cats[r.category_id].name), kind=r.kind, status=r.status, comment=r.comment,
            created_at=r.created_at, decided_by=r.decided_by, decided_at=r.decided_at, decision_comment=r.decision_comment,
            order_number=a.order_number if a else None, order_date=a.order_date if a else None, valid_until=a.valid_until if a else None,
        ))
    return outs


# ---------- судейская коллегия соревнования ----------

@collegium_router.post("", response_model=JudgeAssignmentOut, status_code=status.HTTP_201_CREATED,
                       summary="Назначить судью в коллегию соревнования (федерация)")
async def assign_judge(competition_id: int, data: JudgeAssignIn, request: Request, session: Session, current: FederationOnly) -> JudgeAssignmentOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    if comp.status in (CompetitionStatus.FINISHED, CompetitionStatus.CANCELLED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Судейскую коллегию завершённого или отменённого соревнования менять нельзя")
    if await session.get(JudgeProfile, data.judge_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Судья не найден")
    position = await session.get(JudgePosition, data.position_id)
    if position is None:
        raise unprocessable("Судейская должность не найдена")

    latest = await latest_category(session, data.judge_id)
    if latest is None or (latest[0].valid_until is not None and latest[0].valid_until < comp.end_date):
        raise unprocessable("У судьи нет судейской категории, действующей на дату окончания соревнования")
    participant = await session.scalar(
        select(CompetitionApplication.id).where(
            CompetitionApplication.competition_id == comp.id, CompetitionApplication.athlete_id == data.judge_id,
            CompetitionApplication.status.in_([ApplicationStatus.PENDING, ApplicationStatus.APPROVED]),
        ).limit(1)
    )
    if participant is not None:
        raise unprocessable("Судья участвует в этом соревновании как спортсмен: назначение невозможно")
    if await session.scalar(select(CompetitionJudge.id).where(CompetitionJudge.competition_id == comp.id, CompetitionJudge.judge_id == data.judge_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Судья уже назначен на это соревнование")
    if position.name == CHIEF_POSITION and await session.scalar(
        select(CompetitionJudge.id).where(CompetitionJudge.competition_id == comp.id, CompetitionJudge.position_id == position.id)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Главный судья на это соревнование уже назначен")

    row = CompetitionJudge(competition_id=comp.id, judge_id=data.judge_id, position_id=position.id, assigned_by=current.user.id)
    session.add(row)
    await session.flush()
    await notify(session, data.judge_id, NotificationKind.JUDGE_REQUEST, "Назначение на соревнование",
                 f"Вы назначены на «{comp.title}» ({comp.start_date:%d.%m.%Y}) в должности «{position.name}».",
                 entity_type="competition", entity_id=comp.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="judge.assign", entity_type="competition_judge", entity_id=row.id,
                     diff={"competition_id": comp.id, "judge_id": data.judge_id, "position": position.name})
    await session.commit()
    await session.refresh(row)
    return (await build_assignment_outs(session, [row]))[0]


@collegium_router.get("", response_model=list[JudgeAssignmentOut], summary="Судейская коллегия соревнования")
async def list_collegium(competition_id: int, session: Session, current: Authed) -> list[JudgeAssignmentOut]:
    await get_competition_or_404(session, competition_id, current.active_role)
    rows = (await session.scalars(
        select(CompetitionJudge).where(CompetitionJudge.competition_id == competition_id).order_by(CompetitionJudge.position_id, CompetitionJudge.id)
    )).all()
    return await build_assignment_outs(session, list(rows))


@collegium_router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Снять судью с соревнования (федерация)")
async def remove_judge(competition_id: int, assignment_id: int, request: Request, session: Session, current: FederationOnly) -> None:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    row = await session.get(CompetitionJudge, assignment_id)
    if row is None or row.competition_id != competition_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Назначение не найдено")
    if comp.status in (CompetitionStatus.FINISHED, CompetitionStatus.CANCELLED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Судейскую коллегию завершённого или отменённого соревнования менять нельзя")
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="judge.unassign", entity_type="competition_judge", entity_id=row.id,
                     diff={"competition_id": competition_id, "judge_id": row.judge_id})
    await session.delete(row)
    await session.commit()


# ---------- кабинет судьи ----------

@judge_router.get("/assignments", response_model=MyAssignmentsOut, summary="Мои назначения, история работы и срок категории")
async def my_assignments(session: Session, current: JudgeOnly) -> MyAssignmentsOut:
    today = date.today()
    rows = (await session.scalars(
        select(CompetitionJudge).join(Competition, Competition.id == CompetitionJudge.competition_id)
        .where(CompetitionJudge.judge_id == current.user.id).order_by(Competition.start_date.desc())
    )).all()
    outs = await build_assignment_outs(session, list(rows))
    latest = await latest_category(session, current.user.id)
    return MyAssignmentsOut(
        category=make_validity(latest[1].id, latest[1].name, latest[0].assigned_at, latest[0].valid_until, today) if latest else None,
        upcoming=sorted((o for o in outs if o.competition.end_date >= today), key=lambda o: o.competition.start_date),
        past=[o for o in outs if o.competition.end_date < today],
    )


@judge_router.post("/category-requests", response_model=CategoryRequestOut, status_code=status.HTTP_201_CREATED,
                   summary="Заявка на присвоение или подтверждение судейской категории")
async def create_category_request(data: CategoryRequestIn, request: Request, session: Session, current: JudgeOnly) -> CategoryRequestOut:
    category = await session.get(JudgeCategory, data.category_id)
    if category is None:
        raise unprocessable("Судейская категория не найдена")
    if await session.get(JudgeProfile, current.user.id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль судьи не найден")
    latest = await latest_category(session, current.user.id)
    if data.kind == RequestKind.CONFIRM:
        if latest is None or latest[1].id != category.id:
            raise unprocessable("Подтвердить можно только имеющуюся категорию")
    elif latest is not None and category.order_no <= latest[1].order_no:
        raise unprocessable(f"Присвоить можно только категорию выше имеющейся («{latest[1].name}»)")
    pending = await session.scalar(
        select(JudgeCategoryRequest.id).where(JudgeCategoryRequest.judge_id == current.user.id, JudgeCategoryRequest.status == RequestStatus.SUBMITTED).limit(1)
    )
    if pending is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "У вас уже есть заявка на категорию, ожидающая рассмотрения")

    req = JudgeCategoryRequest(judge_id=current.user.id, category_id=category.id, kind=data.kind, comment=data.comment)
    session.add(req)
    await session.flush()
    for uid in await federation_user_ids(session):
        await notify(session, uid, NotificationKind.JUDGE_REQUEST, "Заявка судьи на категорию",
                     f"{full_name(current.user)} просит {'присвоить' if data.kind == RequestKind.ASSIGN else 'подтвердить'} категорию «{category.name}».",
                     entity_type="judge_category_request", entity_id=req.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="judge_request.create", entity_type="judge_category_request", entity_id=req.id,
                     diff={"category_id": category.id, "kind": data.kind.value})
    await session.commit()
    await session.refresh(req)
    return (await build_request_outs(session, [req]))[0]


@judge_router.get("/category-requests", response_model=list[CategoryRequestOut], summary="Мои заявки на категорию")
async def my_category_requests(session: Session, current: JudgeOnly) -> list[CategoryRequestOut]:
    reqs = (await session.scalars(
        select(JudgeCategoryRequest).where(JudgeCategoryRequest.judge_id == current.user.id).order_by(JudgeCategoryRequest.id.desc())
    )).all()
    return await build_request_outs(session, list(reqs))


# ---------- рассмотрение федерацией ----------

@federation_router.get("", response_model=list[CategoryRequestOut], summary="Заявки судей на категорию (федерация)")
async def list_judge_requests(
    session: Session,
    current: FederationOnly,
    status_: Annotated[RequestStatus | None, Query(alias="status")] = None,
) -> list[CategoryRequestOut]:
    stmt = select(JudgeCategoryRequest)
    if status_ is not None:
        stmt = stmt.where(JudgeCategoryRequest.status == status_)
    reqs = (await session.scalars(stmt.order_by(JudgeCategoryRequest.id.desc()))).all()
    return await build_request_outs(session, list(reqs))


@federation_router.patch("/{request_id}", response_model=CategoryRequestOut,
                         summary="Утвердить категорию с приказом и сроком действия или отклонить заявку")
async def decide_judge_request(request_id: int, data: RequestDecision, request: Request, session: Session, current: FederationOnly) -> CategoryRequestOut:
    req = await session.get(JudgeCategoryRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    if req.status != RequestStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Заявка уже рассмотрена (статус: {req.status.value})")
    category = await session.get(JudgeCategory, req.category_id)

    req.status, req.decided_by = data.status, current.user.id
    req.decided_at = datetime.now(timezone.utc)
    req.decision_comment = data.comment.strip() if data.comment else None
    if data.status == RequestStatus.APPROVED:
        order_date = data.order_date or date.today()
        valid_until = data.valid_until or (add_months(order_date, category.validity_months) if category.validity_months else None)
        if valid_until is not None and valid_until <= order_date:
            raise unprocessable("Срок действия должен быть позже даты приказа")
        session.add(JudgeCategoryAssignment(
            judge_id=req.judge_id, category_id=category.id, assigned_at=order_date, valid_until=valid_until,
            order_number=data.order_number.strip(), order_date=order_date, request_id=req.id,
        ))
        text = f"Категория «{category.name}» утверждена, приказ № {data.order_number.strip()}" + (f", действует до {valid_until:%d.%m.%Y}." if valid_until else ".")
    else:
        text = f"Заявка на категорию «{category.name}» отклонена: {req.decision_comment}"
    await session.flush()
    await notify(session, req.judge_id, NotificationKind.JUDGE_REQUEST, "Решение по заявке на категорию", text,
                 entity_type="judge_category_request", entity_id=req.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="judge_request.decide", entity_type="judge_category_request", entity_id=req.id,
                     diff={"status": data.status.value, "order_number": data.order_number})
    await session.commit()
    return (await build_request_outs(session, [req]))[0]
