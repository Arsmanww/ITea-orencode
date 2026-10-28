from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import AthleteProfile, CompetitionApplication, Team, User
from app.models.enums import ApplicationStatus, NotificationKind, RoleCode
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationModerate,
    ApplicationOut,
    AthleteRef,
    TeamRef,
)
from app.services.common import full_name, get_competition_or_404
from app.services.eligibility import active_link, ensure_registration_open, unprocessable, validate_participation
from app.services.notifications import notify

router = APIRouter(prefix="/competitions/{competition_id}/applications", tags=["applications"])

Session = Annotated[AsyncSession, Depends(get_session)]
Submitter = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE, RoleCode.COACH))]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
AnyApplicationRole = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION, RoleCode.ATHLETE, RoleCode.COACH))]


async def build_outs(session: AsyncSession, apps: list[CompetitionApplication]) -> list[ApplicationOut]:
    if not apps:
        return []
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({a.athlete_id for a in apps})))}
    team_ids = {a.team_id for a in apps if a.team_id}
    teams = {t.id: t for t in await session.scalars(select(Team).where(Team.id.in_(team_ids)))} if team_ids else {}
    return [
        ApplicationOut(
            id=a.id, competition_id=a.competition_id,
            athlete=AthleteRef(id=a.athlete_id, full_name=full_name(users[a.athlete_id]), birth_date=users[a.athlete_id].birth_date),
            team=TeamRef(id=a.team_id, name=teams[a.team_id].name) if a.team_id else None,
            status=a.status, age_on_start=a.age_on_start, submitted_by_user_id=a.submitted_by_user_id,
            submitted_by_role=a.submitted_by_role, coach_id=a.coach_id, moderated_by=a.moderated_by,
            moderated_at=a.moderated_at, moderation_comment=a.moderation_comment, created_at=a.created_at,
        )
        for a in apps
    ]


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED,
             summary="Подать заявку: спортсмен за себя (без тренера) или тренер за подопечного")
async def create_application(competition_id: int, data: ApplicationCreate, request: Request, session: Session, current: Submitter) -> ApplicationOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    ensure_registration_open(comp)

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
        raise HTTPException(status.HTTP_403_FORBIDDEN, "У спортсмена есть тренер по этой дисциплине: заявку подаёт тренер")
    if current.active_role == RoleCode.COACH and (link is None or link.coach_id != current.user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Спортсмен не привязан к вам по дисциплине соревнования")

    age = await validate_participation(session, comp, athlete_id, athlete.birth_date)

    team = None
    if comp.is_team:
        name = (data.team_name or "").strip()
        if not name:
            raise unprocessable("Соревнование командное: укажите team_name")
        team = await session.scalar(select(Team).where(Team.competition_id == comp.id, Team.name == name))
        if team is None:
            team = Team(competition_id=comp.id, name=name, coach_id=link.coach_id if link else None)
            session.add(team)
            await session.flush()

    app = CompetitionApplication(
        competition_id=comp.id, athlete_id=athlete_id, team_id=team.id if team else None,
        submitted_by_user_id=current.user.id, submitted_by_role=current.active_role,
        coach_id=link.coach_id if link else None, status=ApplicationStatus.PENDING, age_on_start=age,
    )
    session.add(app)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Заявка этого спортсмена на соревнование уже подана") from None
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="application.create", entity_type="competition_application", entity_id=app.id,
                     diff={"competition_id": comp.id, "athlete_id": athlete_id, "age_on_start": age})
    await session.commit()
    await session.refresh(app)
    return (await build_outs(session, [app]))[0]


@router.get("", response_model=list[ApplicationOut], summary="Заявки на соревнование (федерация – все, остальные – свои)")
async def list_applications(
    competition_id: int,
    session: Session,
    current: AnyApplicationRole,
    status_: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
) -> list[ApplicationOut]:
    await get_competition_or_404(session, competition_id, current.active_role)
    stmt = select(CompetitionApplication).where(CompetitionApplication.competition_id == competition_id)
    if current.active_role == RoleCode.ATHLETE:
        stmt = stmt.where(CompetitionApplication.athlete_id == current.user.id)
    elif current.active_role == RoleCode.COACH:
        stmt = stmt.where(CompetitionApplication.coach_id == current.user.id)
    if status_ is not None:
        stmt = stmt.where(CompetitionApplication.status == status_)
    apps = (await session.scalars(stmt.order_by(CompetitionApplication.id))).all()
    return await build_outs(session, list(apps))


@router.patch("/{app_id}", response_model=ApplicationOut, summary="Модерация заявки (федерация): approved / rejected")
async def moderate_application(competition_id: int, app_id: int, data: ApplicationModerate, request: Request, session: Session, current: FederationOnly) -> ApplicationOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    app = await session.get(CompetitionApplication, app_id)
    if app is None or app.competition_id != competition_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заявка не найдена")
    if app.status != ApplicationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Заявка уже рассмотрена (статус: {app.status.value})")
    app.status = data.status
    app.moderated_by = current.user.id
    app.moderated_at = datetime.now(timezone.utc)
    app.moderation_comment = data.comment.strip() if data.comment else None
    verdict = "одобрена" if data.status == ApplicationStatus.APPROVED else "отклонена"
    athlete = await session.get(User, app.athlete_id)
    for uid in {app.athlete_id, *([app.coach_id] if app.coach_id else [])}:
        await notify(session, uid, NotificationKind.APPLICATION_STATUS, f"Заявка {verdict}",
                     f"{full_name(athlete)}: заявка на «{comp.title}» {verdict}."
                     + (f" Причина: {app.moderation_comment}" if app.moderation_comment else ""),
                     entity_type="competition_application", entity_id=app.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="application.moderate", entity_type="competition_application", entity_id=app.id,
                     diff={"status": data.status.value, "comment": app.moderation_comment})
    await session.commit()
    return (await build_outs(session, [app]))[0]
