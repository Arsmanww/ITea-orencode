from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import (
    AgeGroup,
    AthleteEnrollment,
    CoachAthleteLink,
    Discipline,
    Organization,
    Rank,
    RatingRule,
    RatingSettings,
    Season,
    Squad,
    SquadMember,
    User,
)
from app.models.enums import LinkStatus, RoleCode, SquadStatus
from app.reports.squad_order_docx import build_squad_order_docx
from app.schemas.people import DisciplineRef, IdName
from app.schemas.rating import (
    RatingOut,
    RuleOut,
    SeasonOut,
    SettingsOut,
    SettingsUpdate,
    SquadApprove,
    SquadCreate,
    SquadMemberOut,
    SquadOut,
)
from app.services.common import full_name
from app.services.eligibility import unprocessable
from app.services.files import attachment
from app.services.rating import RatingConfig, as_of_date, compute_rating, current_rank_orders, load_config

router = APIRouter(tags=["rating"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def season_out(s: Season) -> SeasonOut:
    return SeasonOut(id=s.id, name=s.name, date_from=s.date_from, date_to=s.date_to)


async def resolve_season(session: AsyncSession, season_id: int | None) -> Season:
    if season_id is not None:
        season = await session.get(Season, season_id)
        if season is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Сезон не найден")
        return season
    today = date.today()
    season = await session.scalar(select(Season).where(Season.date_from <= today, Season.date_to >= today).limit(1))
    return season or await session.scalar(select(Season).order_by(Season.date_to.desc()).limit(1))


def settings_out(config: RatingConfig) -> SettingsOut:
    rules = [RuleOut(tier=t, place=p, points=pts) for (t, p), pts in sorted(config.points.items(), key=lambda kv: (kv[0][0].value, kv[0][1]))]
    return SettingsOut(stability_coef=config.coefficient, stability_min_prizes=config.min_prizes, rules=rules)


@router.get("/rating/seasons", response_model=list[SeasonOut], summary="Сезоны для рейтинга")
async def seasons(session: Session, current: Authed) -> list[SeasonOut]:
    return [season_out(s) for s in await session.scalars(select(Season).order_by(Season.date_from.desc()))]


@router.get("/rating", response_model=RatingOut,
            summary="Рейтинг спортсменов за сезон по дисциплинам с прозрачным расчётом баллов")
async def get_rating(
    session: Session,
    current: Authed,
    season_id: int | None = None,
    discipline_id: int | None = None,
    discipline: Annotated[str | None, Query(description="Код дисциплины, например algorithmic")] = None,
    age_group_id: int | None = None,
    min_rank_id: Annotated[int | None, Query(description="Минимальный действующий разряд по дисциплине")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> RatingOut:
    season = await resolve_season(session, season_id)
    config = await load_config(session)
    stmt = select(Discipline).order_by(Discipline.id)
    if discipline_id is not None:
        stmt = stmt.where(Discipline.id == discipline_id)
    if discipline is not None:
        stmt = stmt.where(Discipline.code == discipline)
    disciplines = (await session.scalars(stmt)).all()
    if not disciplines:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Дисциплина не найдена")
    age_group = await session.get(AgeGroup, age_group_id) if age_group_id else None
    if age_group_id and age_group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Возрастная группа не найдена")
    min_rank = await session.get(Rank, min_rank_id) if min_rank_id else None
    if min_rank_id and min_rank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Разряд не найден")

    today = date.today()
    tables = [await compute_rating(session, season, d, config, today, age_group=age_group, min_rank=min_rank, limit=limit) for d in disciplines]
    return RatingOut(
        season=season_out(season), as_of=as_of_date(season, today),
        age_group=IdName(id=age_group.id, name=age_group.name) if age_group else None,
        min_rank=IdName(id=min_rank.id, name=min_rank.name) if min_rank else None,
        settings=settings_out(config), tables=tables,
    )


@router.get("/rating/settings", response_model=SettingsOut, summary="Настройки расчёта рейтинга: таблица баллов и коэффициент")
async def get_rating_settings(session: Session, current: Authed) -> SettingsOut:
    return settings_out(await load_config(session))


@router.put("/rating/settings", response_model=SettingsOut, summary="Изменить настройки рейтинга (федерация)")
async def update_rating_settings(data: SettingsUpdate, request: Request, session: Session, current: FederationOnly) -> SettingsOut:
    row = await session.scalar(select(RatingSettings).order_by(RatingSettings.id).limit(1))
    if row is None:
        row = RatingSettings()
        session.add(row)
    if data.stability_coef is not None:
        row.stability_coef = data.stability_coef
    if data.stability_min_prizes is not None:
        row.stability_min_prizes = data.stability_min_prizes
    for rule in data.rules or []:
        existing = await session.scalar(select(RatingRule).where(RatingRule.tier == rule.tier, RatingRule.place == rule.place))
        if existing:
            existing.points = rule.points
        else:
            session.add(RatingRule(tier=rule.tier, place=rule.place, points=rule.points))
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="rating.settings_update",
                     entity_type="rating_settings", diff=data.model_dump(mode="json", exclude_none=True))
    await session.commit()
    return settings_out(await load_config(session))


# ---------- сборная региона ----------

async def build_squad_out(session: AsyncSession, squad: Squad) -> SquadOut:
    season = await session.get(Season, squad.season_id)
    discipline = await session.get(Discipline, squad.discipline_id)
    age_group = await session.get(AgeGroup, squad.age_group_id) if squad.age_group_id else None
    members = (await session.scalars(select(SquadMember).where(SquadMember.squad_id == squad.id).order_by(SquadMember.position))).all()
    ids = [m.athlete_id for m in members]
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    orgs: dict[int, str] = {}
    for athlete_id, name in (await session.execute(
        select(AthleteEnrollment.athlete_id, Organization.name).join(Organization, Organization.id == AthleteEnrollment.organization_id)
        .where(AthleteEnrollment.athlete_id.in_(ids), AthleteEnrollment.discipline_id == squad.discipline_id)
        .order_by(AthleteEnrollment.start_date)
    )).all():
        orgs[athlete_id] = name
    coaches = {}
    for athlete_id, coach in (await session.execute(
        select(CoachAthleteLink.athlete_id, User).join(User, User.id == CoachAthleteLink.coach_id)
        .where(CoachAthleteLink.athlete_id.in_(ids), CoachAthleteLink.discipline_id == squad.discipline_id,
               CoachAthleteLink.status == LinkStatus.ACTIVE)
    )).all():
        coaches[athlete_id] = full_name(coach)
    ranks = await current_rank_orders(session, squad.discipline_id, date.today())
    return SquadOut(
        id=squad.id, title=squad.title, season=season_out(season),
        discipline=DisciplineRef(id=discipline.id, code=discipline.code, name=discipline.name),
        age_group=IdName(id=age_group.id, name=age_group.name) if age_group else None, status=squad.status,
        order_number=squad.order_number, created_at=squad.created_at,
        members=[SquadMemberOut(position=m.position, athlete_id=m.athlete_id, athlete_name=full_name(users[m.athlete_id]),
                                birth_date=users[m.athlete_id].birth_date, rating_points=m.rating_points,
                                organization=orgs.get(m.athlete_id), rank=ranks[m.athlete_id].name if m.athlete_id in ranks else None,
                                coach=coaches.get(m.athlete_id), note=m.note) for m in members],
    )


@router.post("/squads", response_model=SquadOut, status_code=status.HTTP_201_CREATED,
             summary="Сохранить состав сборной региона, сформированный из рейтинга (федерация)")
async def create_squad(data: SquadCreate, request: Request, session: Session, current: FederationOnly) -> SquadOut:
    season = await session.get(Season, data.season_id)
    discipline = await session.get(Discipline, data.discipline_id)
    if season is None or discipline is None:
        raise unprocessable("Сезон или дисциплина не найдены")
    age_group = await session.get(AgeGroup, data.age_group_id) if data.age_group_id else None
    if data.age_group_id and age_group is None:
        raise unprocessable("Возрастная группа не найдена")

    table = await compute_rating(session, season, discipline, await load_config(session), date.today(),
                                 age_group=age_group, limit=100_000)
    by_id = {i.athlete_id: i for i in table.items}
    excluded = {e.athlete_id: e.reason for e in table.excluded}
    problems = [
        f"спортсмен {m.athlete_id}: {excluded[m.athlete_id]}" if m.athlete_id in excluded
        else f"спортсмен {m.athlete_id}: нет результатов в рейтинге этой дисциплины и сезона или не подходит возрастная группа"
        for m in data.members if m.athlete_id not in by_id
    ]
    if problems:
        raise unprocessable("В сборную можно включить только спортсменов из рейтинга: " + "; ".join(problems))

    squad = Squad(season_id=season.id, discipline_id=discipline.id, age_group_id=age_group.id if age_group else None,
                  title=data.title.strip(), status=SquadStatus.DRAFT, created_by=current.user.id)
    session.add(squad)
    await session.flush()
    session.add_all(
        SquadMember(squad_id=squad.id, athlete_id=m.athlete_id, position=pos, rating_points=Decimal(by_id[m.athlete_id].total), note=m.note)
        for pos, m in enumerate(data.members, start=1)
    )
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="squad.create",
                     entity_type="squad", entity_id=squad.id, diff={"members": [m.athlete_id for m in data.members]})
    await session.commit()
    await session.refresh(squad)
    return await build_squad_out(session, squad)


@router.get("/squads", response_model=list[SquadOut], summary="Составы сборной (федерация)")
async def list_squads(session: Session, current: FederationOnly, season_id: int | None = None, discipline_id: int | None = None) -> list[SquadOut]:
    stmt = select(Squad)
    if season_id is not None:
        stmt = stmt.where(Squad.season_id == season_id)
    if discipline_id is not None:
        stmt = stmt.where(Squad.discipline_id == discipline_id)
    return [await build_squad_out(session, s) for s in await session.scalars(stmt.order_by(Squad.id.desc()))]


async def _get_squad(session: AsyncSession, squad_id: int) -> Squad:
    squad = await session.get(Squad, squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Состав сборной не найден")
    return squad


@router.get("/squads/{squad_id}", response_model=SquadOut, summary="Состав сборной")
async def get_squad(squad_id: int, session: Session, current: FederationOnly) -> SquadOut:
    return await build_squad_out(session, await _get_squad(session, squad_id))


@router.post("/squads/{squad_id}/approve", response_model=SquadOut, summary="Утвердить состав приказом (номер приказа)")
async def approve_squad(squad_id: int, data: SquadApprove, request: Request, session: Session, current: FederationOnly) -> SquadOut:
    squad = await _get_squad(session, squad_id)
    if squad.status == SquadStatus.APPROVED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Состав уже утверждён")
    squad.status, squad.order_number = SquadStatus.APPROVED, data.order_number.strip()
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="squad.approve",
                     entity_type="squad", entity_id=squad.id, diff={"order_number": squad.order_number})
    await session.commit()
    return await build_squad_out(session, squad)


@router.get("/squads/{squad_id}/order-project", summary="Проект приказа о зачислении в сборную (.docx)")
async def squad_order_project(squad_id: int, request: Request, session: Session, current: FederationOnly):
    squad = await build_squad_out(session, await _get_squad(session, squad_id))
    content = build_squad_order_docx({
        "title": squad.title, "discipline": squad.discipline.name, "age_group": squad.age_group.name if squad.age_group else None,
        "season": squad.season.name.replace("Сезон ", ""), "order_number": squad.order_number,
        "members": [m.model_dump() for m in squad.members],
    })
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="report.squad_order",
                     entity_type="squad", entity_id=squad_id)
    await session.commit()
    return attachment(content, DOCX, f"squad-order-{squad_id}.docx", f"Проект приказа о сборной №{squad_id}.docx")
