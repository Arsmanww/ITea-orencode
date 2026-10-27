from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user
from app.models import (
    AthleteEnrollment,
    AthleteProfile,
    CoachAthleteLink,
    CoachProfile,
    CompetitionJudge,
    Discipline,
    JudgeProfile,
    Municipality,
    Organization,
    User,
)
from app.models.enums import LinkStatus, RoleCode, TrainingStage
from app.routers.athlete_profile import ConsentOut, consent_out
from app.schemas.auth import UserOut
from app.schemas.people import DisciplineRef, ValidityInfo
from app.services import max_bot
from app.services.common import full_name
from app.services.eligibility import age_on
from app.services.ranks import current_rank, make_validity

router = APIRouter(prefix="/me", tags=["profile"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]


class NotificationSettings(BaseModel):
    in_app: bool = True
    email: str
    max_bot_configured: bool
    max_bot_username: str | None
    max_bound: bool


class MaxLinkOut(BaseModel):
    code: str = Field(description="Одноразовый код; его можно отправить боту сообщением")
    link: str | None = Field(description="Ссылка https://max.ru/<бот>?start=<код>: открыть и нажать «Начать»")
    expires_at: datetime


def _settings_out(current: CurrentUser) -> NotificationSettings:
    return NotificationSettings(
        email=current.user.email, max_bot_configured=max_bot.max_enabled(), max_bot_username=settings.max_bot_username or None,
        max_bound=bool(current.user.max_user_id),
    )


@router.get("/notification-settings", response_model=NotificationSettings, summary="Каналы уведомлений пользователя")
async def notification_settings(current: Authed) -> NotificationSettings:
    return _settings_out(current)


@router.post("/max/link", response_model=MaxLinkOut,
             summary="Получить одноразовую ссылку привязки MAX (действует 15 минут)")
async def max_link(request: Request, session: Session, current: Authed) -> MaxLinkOut:
    if not max_bot.max_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Бот MAX на платформе не настроен")
    code, expires_at = max_bot.new_link_code()
    current.user.max_link_code, current.user.max_link_expires_at = code, expires_at
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="profile.max_link_issued", entity_type="user", entity_id=current.user.id)
    await session.commit()
    return MaxLinkOut(code=code, link=max_bot.deep_link(code), expires_at=expires_at)


@router.delete("/max", response_model=NotificationSettings, summary="Отвязать MAX")
async def unbind_max(request: Request, session: Session, current: Authed) -> NotificationSettings:
    current.user.max_user_id = current.user.max_link_code = current.user.max_link_expires_at = None
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="profile.max_unbind", entity_type="user", entity_id=current.user.id)
    await session.commit()
    return _settings_out(current)


class ProfileDiscipline(BaseModel):
    discipline: DisciplineRef
    organization: str | None
    training_stage: TrainingStage | None
    since: date
    rank: ValidityInfo | None
    coach: str | None


class AthleteBlock(BaseModel):
    disciplines: list[ProfileDiscipline]
    starts: int
    prizes: int
    antidoping_course_date: date | None
    antidoping_cert_url: str | None
    guardian_name: str | None
    guardian_phone: str | None


class CoachBlock(BaseModel):
    organization: str | None
    athletes: int
    disciplines: list[str]


class JudgeBlock(BaseModel):
    organization: str | None
    category: ValidityInfo | None
    assignments: int


class MyProfileOut(BaseModel):
    """Карточка пользователя: общие данные плюс блок на каждую роль аккаунта."""

    user: UserOut
    full_name: str
    age: int
    municipality: str | None
    roles: list[RoleCode]
    active_role: RoleCode
    registered_at: AwareDatetime
    consent: ConsentOut
    max_bound: bool
    athlete: AthleteBlock | None
    coach: CoachBlock | None
    judge: JudgeBlock | None


async def _athlete_block(session: AsyncSession, user_id: int, today: date) -> AthleteBlock | None:
    from app.routers.athletes import build_history

    profile = await session.get(AthleteProfile, user_id)
    if profile is None:
        return None
    rows = (await session.execute(
        select(AthleteEnrollment, Discipline, Organization.name)
        .join(Discipline, Discipline.id == AthleteEnrollment.discipline_id)
        .outerjoin(Organization, Organization.id == AthleteEnrollment.organization_id)
        .where(AthleteEnrollment.athlete_id == user_id, AthleteEnrollment.end_date.is_(None))
        .order_by(Discipline.id)
    )).all()
    coaches = {
        discipline_id: full_name(coach)
        for discipline_id, coach in (await session.execute(
            select(CoachAthleteLink.discipline_id, User).join(User, User.id == CoachAthleteLink.coach_id)
            .where(CoachAthleteLink.athlete_id == user_id, CoachAthleteLink.status == LinkStatus.ACTIVE)
        )).all()
    }
    disciplines = []
    for enrollment, discipline, organization in rows:
        assignment = await current_rank(session, user_id, discipline.id)
        disciplines.append(ProfileDiscipline(
            discipline=DisciplineRef(id=discipline.id, code=discipline.code, name=discipline.name),
            organization=organization, training_stage=enrollment.training_stage, since=enrollment.start_date,
            rank=make_validity(assignment[1].id, assignment[1].name, assignment[0].assigned_at, assignment[0].valid_until, today) if assignment else None,
            coach=coaches.get(discipline.id),
        ))
    history = await build_history(session, user_id, None, None, 1, 0)
    return AthleteBlock(
        disciplines=disciplines, starts=history.total, prizes=history.prizes,
        antidoping_course_date=profile.antidoping_course_date, antidoping_cert_url=profile.antidoping_cert_url,
        guardian_name=profile.guardian_name, guardian_phone=profile.guardian_phone,
    )


async def _coach_block(session: AsyncSession, user_id: int) -> CoachBlock | None:
    profile = await session.get(CoachProfile, user_id)
    if profile is None:
        return None
    organization = await session.get(Organization, profile.organization_id) if profile.organization_id else None
    active = (CoachAthleteLink.coach_id == user_id, CoachAthleteLink.status == LinkStatus.ACTIVE)
    disciplines = (await session.scalars(
        select(Discipline.name).join(CoachAthleteLink, CoachAthleteLink.discipline_id == Discipline.id)
        .where(*active).distinct().order_by(Discipline.name)
    )).all()
    athletes = await session.scalar(select(func.count(func.distinct(CoachAthleteLink.athlete_id))).where(*active))
    return CoachBlock(organization=organization.name if organization else None, athletes=athletes or 0,
                      disciplines=list(disciplines))


async def _judge_block(session: AsyncSession, user_id: int, today: date) -> JudgeBlock | None:
    from app.routers.judges import latest_category

    profile = await session.get(JudgeProfile, user_id)
    if profile is None:
        return None
    organization = await session.get(Organization, profile.organization_id) if profile.organization_id else None
    latest = await latest_category(session, user_id)
    assignments = await session.scalar(select(func.count()).select_from(CompetitionJudge).where(CompetitionJudge.judge_id == user_id))
    return JudgeBlock(
        organization=organization.name if organization else None,
        category=make_validity(latest[1].id, latest[1].name, latest[0].assigned_at, latest[0].valid_until, today) if latest else None,
        assignments=assignments or 0,
    )


@router.get("/profile", response_model=MyProfileOut, summary="Мой профиль: общие данные и блок по каждой роли аккаунта")
async def my_profile(session: Session, current: Authed) -> MyProfileOut:
    user, today = current.user, date.today()
    municipality = await session.get(Municipality, user.municipality_id) if user.municipality_id else None
    return MyProfileOut(
        user=UserOut.model_validate(user), full_name=full_name(user), age=age_on(user.birth_date, today),
        municipality=municipality.name if municipality else None, roles=current.roles, active_role=current.active_role,
        registered_at=user.created_at, consent=await consent_out(session, user.id), max_bound=bool(user.max_user_id),
        athlete=await _athlete_block(session, user.id, today) if RoleCode.ATHLETE in current.roles else None,
        coach=await _coach_block(session, user.id) if RoleCode.COACH in current.roles else None,
        judge=await _judge_block(session, user.id, today) if RoleCode.JUDGE in current.roles else None,
    )
