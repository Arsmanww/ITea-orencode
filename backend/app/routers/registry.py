"""Реестр: спортсмены, тренеры, судьи и организации с поиском и фильтрами (кабинет федерации).

Спортсменов в реестре ищет и тренер – чтобы отправить запрос на привязку; ему отдаётся
сокращённая карточка без контактов.
"""

from datetime import date
from typing import Annotated, Generic, TypeVar

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import (
    AgeGroup,
    AthleteEnrollment,
    AthleteProfile,
    CoachAthleteLink,
    CoachProfile,
    CompetitionJudge,
    Discipline,
    JudgeCategory,
    JudgeCategoryAssignment,
    JudgeProfile,
    Municipality,
    Organization,
    Rank,
    RankAssignment,
    User,
)
from app.models.enums import Gender, LinkStatus, OrgType, RoleCode, TrainingStage
from app.schemas.people import DisciplineRef
from app.services.common import full_name
from app.services.eligibility import age_on

router = APIRouter(prefix="/registry", tags=["registry"])

Session = Annotated[AsyncSession, Depends(get_session)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
AthleteSearcher = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION, RoleCode.COACH))]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
Search = Annotated[str | None, Query(max_length=100, description="Часть ФИО (для федерации – и email)")]

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class AthleteDiscipline(BaseModel):
    discipline: DisciplineRef
    organization: str | None
    training_stage: TrainingStage | None
    since: date
    rank: str | None
    rank_valid_until: date | None
    coach: str | None


class AthleteRow(BaseModel):
    id: int
    full_name: str
    birth_date: date
    age: int
    gender: Gender
    municipality: str | None
    email: str | None  # только для федерации
    disciplines: list[AthleteDiscipline]


class CoachRow(BaseModel):
    id: int
    full_name: str
    organization: str | None
    municipality: str | None
    disciplines: list[str]
    athletes: int
    is_judge: bool


class JudgeRow(BaseModel):
    id: int
    full_name: str
    organization: str | None
    municipality: str | None
    category: str | None
    valid_until: date | None
    expired: bool
    assignments: int


class OrganizationRow(BaseModel):
    id: int
    name: str
    type: OrgType
    municipality: str
    address: str | None
    disciplines: list[str]
    athletes: int
    coaches: int


def _active_enrollment(today: date):
    return (AthleteEnrollment.start_date <= today, or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= today))


def _name_filter(stmt: Select, q: str | None, with_email: bool) -> Select:
    if not q or not q.strip():
        return stmt
    conds = []
    for word in q.strip().split()[:3]:
        like = f"%{word}%"
        cols = [User.last_name.ilike(like), User.first_name.ilike(like), User.patronymic.ilike(like)]
        if with_email:
            cols.append(User.email.ilike(like))
        conds.append(or_(*cols))
    return stmt.where(*conds)


def _current_ranks(today: date):
    """Подзапрос: действующее (последнее и не истёкшее) присвоение разряда по спортсмену и дисциплине."""
    rn = func.row_number().over(
        partition_by=(RankAssignment.athlete_id, RankAssignment.discipline_id),
        order_by=(RankAssignment.assigned_at.desc(), RankAssignment.id.desc()),
    ).label("rn")
    latest = select(RankAssignment.id, RankAssignment.athlete_id, RankAssignment.discipline_id, RankAssignment.rank_id,
                    RankAssignment.valid_until, rn).subquery()
    return (select(latest.c.athlete_id, latest.c.discipline_id, latest.c.rank_id, latest.c.valid_until)
            .where(latest.c.rn == 1, or_(latest.c.valid_until.is_(None), latest.c.valid_until >= today)).subquery())


async def _municipalities(session: AsyncSession) -> dict[int, str]:
    return {m.id: m.name for m in await session.scalars(select(Municipality))}


@router.get("/athletes", response_model=Page[AthleteRow], summary="Реестр спортсменов: поиск и фильтры по дисциплине, организации, разряду, возрасту, муниципалитету")
async def registry_athletes(
    session: Session,
    current: AthleteSearcher,
    q: Search = None,
    discipline_id: int | None = None,
    organization_id: Annotated[int | None, Query(description="0 – «без организации»")] = None,
    rank_id: Annotated[int | None, Query(description="Действующий разряд (с учётом дисциплины, если она выбрана)")] = None,
    age_group_id: int | None = None,
    municipality_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[AthleteRow]:
    today = date.today()
    federation = current.active_role == RoleCode.FEDERATION
    enrolled = select(AthleteEnrollment.athlete_id).where(*_active_enrollment(today))
    if discipline_id is not None:
        enrolled = enrolled.where(AthleteEnrollment.discipline_id == discipline_id)
    if organization_id is not None:
        enrolled = enrolled.where(AthleteEnrollment.organization_id.is_(None) if organization_id == 0
                                  else AthleteEnrollment.organization_id == organization_id)
    stmt = select(User.id).join(AthleteProfile, AthleteProfile.user_id == User.id).where(User.is_active.is_(True), User.id.in_(enrolled))
    stmt = _name_filter(stmt, q, federation)
    if municipality_id is not None:
        stmt = stmt.where(User.municipality_id == municipality_id)
    if age_group_id is not None:
        group = await session.get(AgeGroup, age_group_id)
        if group is not None:
            age = func.date_part("year", func.age(today, User.birth_date))
            stmt = stmt.where(age >= group.min_age, age <= group.max_age)
    if rank_id is not None:
        ranks = _current_ranks(today)
        has_rank = select(ranks.c.athlete_id).where(ranks.c.rank_id == rank_id)
        if discipline_id is not None:
            has_rank = has_rank.where(ranks.c.discipline_id == discipline_id)
        stmt = stmt.where(User.id.in_(has_rank))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    ids = list((await session.scalars(stmt.order_by(User.last_name, User.first_name, User.id).limit(limit).offset(offset))).all())
    if not ids:
        return Page(items=[], total=total, limit=limit, offset=offset)

    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}
    munis = await _municipalities(session)
    enrollments = (await session.execute(
        select(AthleteEnrollment, Discipline, Organization.name)
        .join(Discipline, Discipline.id == AthleteEnrollment.discipline_id)
        .outerjoin(Organization, Organization.id == AthleteEnrollment.organization_id)
        .where(AthleteEnrollment.athlete_id.in_(ids), *_active_enrollment(today)).order_by(Discipline.id)
    )).all()
    ranks = _current_ranks(today)
    rank_of = {(a, d): (name, until) for a, d, name, until in (await session.execute(
        select(ranks.c.athlete_id, ranks.c.discipline_id, Rank.name, ranks.c.valid_until)
        .join(Rank, Rank.id == ranks.c.rank_id).where(ranks.c.athlete_id.in_(ids))
    )).all()}
    coach_of = {(a, d): full_name(c) for a, d, c in (await session.execute(
        select(CoachAthleteLink.athlete_id, CoachAthleteLink.discipline_id, User).join(User, User.id == CoachAthleteLink.coach_id)
        .where(CoachAthleteLink.athlete_id.in_(ids), CoachAthleteLink.status == LinkStatus.ACTIVE)
    )).all()}
    by_athlete: dict[int, list[AthleteDiscipline]] = {}
    for e, d, org in enrollments:
        rank = rank_of.get((e.athlete_id, d.id))
        by_athlete.setdefault(e.athlete_id, []).append(AthleteDiscipline(
            discipline=DisciplineRef(id=d.id, code=d.code, name=d.name), organization=org, training_stage=e.training_stage,
            since=e.start_date, rank=rank[0] if rank else None, rank_valid_until=rank[1] if rank else None,
            coach=coach_of.get((e.athlete_id, d.id)),
        ))
    items = [
        AthleteRow(id=u.id, full_name=full_name(u), birth_date=u.birth_date, age=age_on(u.birth_date, today), gender=u.gender,
                   municipality=munis.get(u.municipality_id) if u.municipality_id else None, email=u.email if federation else None,
                   disciplines=by_athlete.get(u.id, []))
        for u in (users[i] for i in ids)
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/coaches", response_model=Page[CoachRow], summary="Реестр тренеров")
async def registry_coaches(
    session: Session,
    current: FederationOnly,
    q: Search = None,
    discipline_id: int | None = None,
    organization_id: int | None = None,
    municipality_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[CoachRow]:
    stmt = select(User, CoachProfile).join(CoachProfile, CoachProfile.user_id == User.id).where(User.is_active.is_(True))
    stmt = _name_filter(stmt, q, True)
    if organization_id is not None:
        stmt = stmt.where(CoachProfile.organization_id == organization_id)
    if municipality_id is not None:
        stmt = stmt.where(User.municipality_id == municipality_id)
    if discipline_id is not None:
        stmt = stmt.where(User.id.in_(select(CoachAthleteLink.coach_id).where(
            CoachAthleteLink.discipline_id == discipline_id, CoachAthleteLink.status == LinkStatus.ACTIVE)))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.order_by(User.last_name, User.first_name).limit(limit).offset(offset))).all()
    ids = [u.id for u, _ in rows]
    orgs = {o.id: o.name for o in await session.scalars(select(Organization))}
    munis = await _municipalities(session)
    links = (await session.execute(
        select(CoachAthleteLink.coach_id, Discipline.name, func.count())
        .join(Discipline, Discipline.id == CoachAthleteLink.discipline_id)
        .where(CoachAthleteLink.coach_id.in_(ids), CoachAthleteLink.status == LinkStatus.ACTIVE)
        .group_by(CoachAthleteLink.coach_id, Discipline.name)
    )).all() if ids else []
    judges = set((await session.scalars(select(JudgeProfile.user_id).where(JudgeProfile.user_id.in_(ids)))).all()) if ids else set()
    items = [
        CoachRow(id=u.id, full_name=full_name(u), organization=orgs.get(p.organization_id) if p.organization_id else None,
                 municipality=munis.get(u.municipality_id) if u.municipality_id else None,
                 disciplines=sorted(name for cid, name, _ in links if cid == u.id),
                 athletes=sum(n for cid, _, n in links if cid == u.id), is_judge=u.id in judges)
        for u, p in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/judges", response_model=Page[JudgeRow], summary="Реестр судей с категориями и сроками действия")
async def registry_judges(
    session: Session,
    current: FederationOnly,
    q: Search = None,
    category_id: Annotated[int | None, Query(description="Текущая категория судьи")] = None,
    organization_id: int | None = None,
    municipality_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[JudgeRow]:
    today = date.today()
    rn = func.row_number().over(partition_by=JudgeCategoryAssignment.judge_id,
                                order_by=(JudgeCategoryAssignment.assigned_at.desc(), JudgeCategoryAssignment.id.desc())).label("rn")
    latest_all = select(JudgeCategoryAssignment.judge_id, JudgeCategoryAssignment.category_id, JudgeCategoryAssignment.valid_until, rn).subquery()
    latest = select(latest_all.c.judge_id, latest_all.c.category_id, latest_all.c.valid_until).where(latest_all.c.rn == 1).subquery()
    stmt = (select(User, JudgeProfile, latest.c.category_id, latest.c.valid_until)
            .join(JudgeProfile, JudgeProfile.user_id == User.id)
            .outerjoin(latest, latest.c.judge_id == User.id).where(User.is_active.is_(True)))
    stmt = _name_filter(stmt, q, True)
    if category_id is not None:
        stmt = stmt.where(latest.c.category_id == category_id)
    if organization_id is not None:
        stmt = stmt.where(JudgeProfile.organization_id == organization_id)
    if municipality_id is not None:
        stmt = stmt.where(User.municipality_id == municipality_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.order_by(User.last_name, User.first_name).limit(limit).offset(offset))).all()
    ids = [u.id for u, *_ in rows]
    cats = {c.id: c.name for c in await session.scalars(select(JudgeCategory))}
    orgs = {o.id: o.name for o in await session.scalars(select(Organization))}
    munis = await _municipalities(session)
    counts = dict((await session.execute(
        select(CompetitionJudge.judge_id, func.count()).where(CompetitionJudge.judge_id.in_(ids)).group_by(CompetitionJudge.judge_id)
    )).all()) if ids else {}
    items = [
        JudgeRow(id=u.id, full_name=full_name(u), organization=orgs.get(p.organization_id) if p.organization_id else None,
                 municipality=munis.get(u.municipality_id) if u.municipality_id else None,
                 category=cats.get(cat) if cat else None, valid_until=until, expired=until is not None and until < today,
                 assignments=counts.get(u.id, 0))
        for u, p, cat, until in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/organizations", response_model=Page[OrganizationRow], summary="Реестр организаций, ведущих спортивную подготовку")
async def registry_organizations(
    session: Session,
    current: FederationOnly,
    q: Search = None,
    type_: Annotated[OrgType | None, Query(alias="type")] = None,
    discipline_id: int | None = None,
    municipality_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[OrganizationRow]:
    today = date.today()
    stmt = select(Organization)
    if q and q.strip():
        stmt = stmt.where(Organization.name.ilike(f"%{q.strip()}%"))
    if type_ is not None:
        stmt = stmt.where(Organization.type == type_)
    if municipality_id is not None:
        stmt = stmt.where(Organization.municipality_id == municipality_id)
    if discipline_id is not None:
        stmt = stmt.where(Organization.id.in_(select(AthleteEnrollment.organization_id).where(
            AthleteEnrollment.discipline_id == discipline_id, *_active_enrollment(today))))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    orgs = (await session.scalars(stmt.order_by(Organization.name).limit(limit).offset(offset))).all()
    ids = [o.id for o in orgs]
    munis = await _municipalities(session)
    athletes = dict((await session.execute(
        select(AthleteEnrollment.organization_id, func.count(func.distinct(AthleteEnrollment.athlete_id)))
        .where(AthleteEnrollment.organization_id.in_(ids), *_active_enrollment(today)).group_by(AthleteEnrollment.organization_id)
    )).all()) if ids else {}
    disciplines = (await session.execute(
        select(AthleteEnrollment.organization_id, Discipline.name).join(Discipline, Discipline.id == AthleteEnrollment.discipline_id)
        .where(AthleteEnrollment.organization_id.in_(ids), *_active_enrollment(today)).distinct()
    )).all() if ids else []
    coaches = dict((await session.execute(
        select(CoachProfile.organization_id, func.count()).where(CoachProfile.organization_id.in_(ids)).group_by(CoachProfile.organization_id)
    )).all()) if ids else {}
    items = [
        OrganizationRow(id=o.id, name=o.name, type=o.type, municipality=munis[o.municipality_id], address=o.address,
                        disciplines=sorted(n for oid, n in disciplines if oid == o.id), athletes=athletes.get(o.id, 0),
                        coaches=coaches.get(o.id, 0))
        for o in orgs
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)

