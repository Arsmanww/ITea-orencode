"""Кабинет федерации: дашборд и очередь заявок на соревнования."""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import (
    AthleteEnrollment,
    AuditLog,
    CoachAthleteLink,
    Competition,
    CompetitionApplication,
    JudgeCategoryAssignment,
    JudgeCategoryRequest,
    RankAssignment,
    RankRequest,
    User,
)
from app.models.enums import ApplicationStatus, CompetitionStatus, LinkStatus, RequestStatus, RoleCode
from app.routers.applications import build_outs as build_application_outs
from app.schemas.applications import ApplicationOut
from app.schemas.people import UserRef
from app.services.common import full_name
from app.services.ranks import expiring_items

router = APIRouter(prefix="/federation", tags=["federation"])
Session = Annotated[AsyncSession, Depends(get_session)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
OREN_TZ = timezone(timedelta(hours=5))


class Metrics(BaseModel):
    athletes: int
    coaches: int
    judges: int
    competitions_this_year: int
    participants_this_year: int
    ranks_assigned_this_year: int


class Attention(BaseModel):
    applications_pending: int
    rank_requests_pending: int
    judge_requests_pending: int
    expiring_30: int
    expiring_60: int
    registration_open: int


class UpcomingItem(BaseModel):
    id: int
    title: str
    start_date: date
    status: CompetitionStatus
    registration_deadline: AwareDatetime | None
    pending_applications: int


class DashboardOut(BaseModel):
    metrics: Metrics
    attention: Attention
    upcoming: list[UpcomingItem]


class QueueItem(ApplicationOut):
    competition_title: str


@router.get("/dashboard", response_model=DashboardOut, summary="Дашборд федерации: показатели, требующие внимания, ближайшие соревнования")
async def dashboard(session: Session, current: FederationOnly) -> DashboardOut:
    today = date.today()
    active = (AthleteEnrollment.start_date <= today, or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= today))
    year = func.extract("year", Competition.start_date) == today.year

    async def scalar(stmt) -> int:
        return (await session.scalar(stmt)) or 0

    metrics = Metrics(
        athletes=await scalar(select(func.count(func.distinct(AthleteEnrollment.athlete_id))).where(*active)),
        coaches=await scalar(select(func.count(func.distinct(CoachAthleteLink.coach_id))).where(CoachAthleteLink.status == LinkStatus.ACTIVE)),
        judges=await scalar(select(func.count(func.distinct(JudgeCategoryAssignment.judge_id)))
                            .where(or_(JudgeCategoryAssignment.valid_until.is_(None), JudgeCategoryAssignment.valid_until >= today))),
        competitions_this_year=await scalar(select(func.count()).select_from(Competition).where(year, Competition.status != CompetitionStatus.DRAFT)),
        participants_this_year=await scalar(
            select(func.count(func.distinct(CompetitionApplication.athlete_id))).join(Competition, Competition.id == CompetitionApplication.competition_id)
            .where(year, CompetitionApplication.status == ApplicationStatus.APPROVED)),
        ranks_assigned_this_year=await scalar(select(func.count()).select_from(RankAssignment).where(func.extract("year", RankAssignment.assigned_at) == today.year)),
    )
    e30 = await expiring_items(session, today, 30)
    e60 = await expiring_items(session, today, 60)
    attention = Attention(
        applications_pending=await scalar(select(func.count()).select_from(CompetitionApplication).where(CompetitionApplication.status == ApplicationStatus.PENDING)),
        rank_requests_pending=await scalar(select(func.count()).select_from(RankRequest).where(RankRequest.status == RequestStatus.SUBMITTED)),
        judge_requests_pending=await scalar(select(func.count()).select_from(JudgeCategoryRequest).where(JudgeCategoryRequest.status == RequestStatus.SUBMITTED)),
        expiring_30=len(e30), expiring_60=len(e60),
        registration_open=await scalar(select(func.count()).select_from(Competition).where(Competition.status == CompetitionStatus.REGISTRATION_OPEN)),
    )
    comps = (await session.scalars(
        select(Competition).where(Competition.status != CompetitionStatus.DRAFT, Competition.status != CompetitionStatus.CANCELLED,
                                  Competition.end_date >= today).order_by(Competition.start_date).limit(6)
    )).all()
    pending = dict((await session.execute(
        select(CompetitionApplication.competition_id, func.count()).where(CompetitionApplication.status == ApplicationStatus.PENDING,
                                                                          CompetitionApplication.competition_id.in_([c.id for c in comps]))
        .group_by(CompetitionApplication.competition_id)
    )).all()) if comps else {}
    return DashboardOut(
        metrics=metrics, attention=attention,
        upcoming=[UpcomingItem(id=c.id, title=c.title, start_date=c.start_date, status=c.status, registration_deadline=c.registration_deadline,
                               pending_applications=pending.get(c.id, 0)) for c in comps],
    )


@router.get("/applications", response_model=list[QueueItem], summary="Очередь заявок на соревнования по всем турнирам (по умолчанию — на модерации)")
async def applications_queue(
    session: Session,
    current: FederationOnly,
    status_: Annotated[ApplicationStatus | None, Query(alias="status")] = ApplicationStatus.PENDING,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[QueueItem]:
    stmt = select(CompetitionApplication, Competition.title).join(Competition, Competition.id == CompetitionApplication.competition_id)
    if status_ is not None:
        stmt = stmt.where(CompetitionApplication.status == status_)
    rows = (await session.execute(stmt.order_by(CompetitionApplication.id.desc()).limit(limit))).all()
    outs = await build_application_outs(session, [a for a, _ in rows])
    titles = {a.id: t for a, t in rows}
    return [QueueItem(**o.model_dump(), competition_title=titles[o.id]) for o in outs]


class AuditItem(BaseModel):
    id: int
    created_at: AwareDatetime
    user: UserRef | None
    active_role: RoleCode | None
    action: str
    entity_type: str
    entity_id: int | None
    diff: dict[str, Any] | None
    ip: str | None


class AuditPage(BaseModel):
    items: list[AuditItem]
    total: int
    limit: int
    offset: int
    actions: list[str]


@router.get("/audit-log", response_model=AuditPage, summary="Журнал действий: кто, когда и что сделал")
async def audit_log(
    session: Session,
    current: FederationOnly,
    action: Annotated[str | None, Query(max_length=100, description="Код действия или его начало, например application.")] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=100, description="Фамилия или email автора")] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    stmt = select(AuditLog, User).outerjoin(User, User.id == AuditLog.user_id)
    if action:
        stmt = stmt.where(AuditLog.action.startswith(action))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.last_name.ilike(like), User.email.ilike(like)))
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=OREN_TZ))
    if date_to:
        stmt = stmt.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=OREN_TZ))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset))).all()
    actions = sorted((await session.scalars(select(AuditLog.action).distinct())).all())
    return AuditPage(
        items=[AuditItem(id=a.id, created_at=a.created_at, user=UserRef(id=u.id, full_name=full_name(u)) if u else None,
                         active_role=a.active_role, action=a.action, entity_type=a.entity_type, entity_id=a.entity_id, diff=a.diff, ip=a.ip)
               for a, u in rows],
        total=total, limit=limit, offset=offset, actions=actions,
    )
