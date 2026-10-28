"""Кабинет федерации: дашборд, очередь заявок и учётные записи тренеров/судей."""

import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AwareDatetime, BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import ROLE_TITLES, CurrentUser, load_roles, require_role
from app.core.security import hash_password
from app.models import (
    AthleteEnrollment,
    AuditLog,
    CoachAthleteLink,
    CoachProfile,
    Competition,
    CompetitionApplication,
    Consent,
    JudgeCategoryAssignment,
    JudgeCategoryRequest,
    JudgeProfile,
    Municipality,
    Organization,
    RankAssignment,
    RankRequest,
    Role,
    User,
    UserRole,
)
from app.models.enums import ApplicationStatus, CompetitionStatus, Gender, LinkStatus, RequestStatus, RoleCode
from app.routers.applications import build_outs as build_application_outs
from app.schemas.applications import ApplicationOut
from app.schemas.people import UserRef
from app.services.common import full_name
from app.services.password_reset import issue_reset_token
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


@router.get("/applications", response_model=list[QueueItem], summary="Очередь заявок на соревнования по всем турнирам (по умолчанию – на модерации)")
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


class CreateStaffIn(BaseModel):
    """Федерация заводит тренера или судью: это не самрегистрация – пароль задаёт сам
    тренер/судья по ссылке из письма (как при восстановлении пароля)."""

    email: EmailStr = Field(max_length=255)
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    patronymic: str | None = Field(default=None, max_length=100)
    birth_date: date
    gender: Gender
    phone: str | None = Field(default=None, max_length=32)
    municipality_id: int | None = None
    organization_id: int | None = None
    role: Literal[RoleCode.COACH, RoleCode.JUDGE]
    bio: str | None = Field(default=None, max_length=2000, description="Только для тренера")
    consent: bool = Field(description="Федерация уже получила согласие на обработку ПДн офлайн")


class StaffCreatedOut(BaseModel):
    user_id: int
    email: str
    role: RoleCode
    created_new_user: bool = Field(description="False – роль добавлена к уже существующему аккаунту (мульти-роль)")


@router.post("/staff", response_model=StaffCreatedOut, status_code=status.HTTP_201_CREATED,
             summary="Завести аккаунт тренера или судьи (или добавить роль существующему пользователю)")
async def create_staff(data: CreateStaffIn, request: Request, session: Session, current: FederationOnly) -> StaffCreatedOut:
    if data.organization_id and await session.get(Organization, data.organization_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Организация не найдена")
    if data.municipality_id and await session.get(Municipality, data.municipality_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Муниципалитет не найден")

    email = data.email.strip().lower()
    role_row = await session.scalar(select(Role).where(Role.code == data.role))
    user = await session.scalar(select(User).where(User.email == email))
    created_new_user = user is None

    if user is None:
        # Пароль никому не известен – реальный пароль задаётся по ссылке сброса из письма ниже.
        user = User(
            email=email, password_hash=hash_password(secrets.token_urlsafe(32)), last_name=data.last_name.strip(),
            first_name=data.first_name.strip(), patronymic=(data.patronymic or "").strip() or None,
            birth_date=data.birth_date, gender=data.gender, phone=data.phone, municipality_id=data.municipality_id,
        )
        session.add(user)
        await session.flush()
    elif data.role in await load_roles(session, user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"У пользователя уже есть роль «{ROLE_TITLES[data.role]}»")

    session.add(UserRole(user_id=user.id, role_id=role_row.id))
    if data.role == RoleCode.COACH:
        if await session.get(CoachProfile, user.id) is None:
            session.add(CoachProfile(user_id=user.id, organization_id=data.organization_id, bio=data.bio))
    else:
        if await session.get(JudgeProfile, user.id) is None:
            session.add(JudgeProfile(user_id=user.id, organization_id=data.organization_id))

    if created_new_user and data.consent:
        session.add(Consent(user_id=user.id, signed_by_name=f"{user.last_name} {user.first_name}", is_guardian=False, file_id=None))

    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="federation.staff_create",
                     entity_type="user", entity_id=user.id, diff={"email": email, "role": data.role.value, "new_user": created_new_user})
    await session.commit()

    if created_new_user:
        await issue_reset_token(session, user, purpose="activation")
        await session.commit()

    return StaffCreatedOut(user_id=user.id, email=user.email, role=data.role, created_new_user=created_new_user)
