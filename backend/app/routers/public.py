"""Публичный раздел без авторизации (Д11, «Навигатор для новичка»)."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import (
    AthleteEnrollment,
    Competition,
    ContentPage,
    Discipline,
    Municipality,
    Organization,
    Protocol,
    User,
)
from app.models.enums import CompetitionStatus, ProtocolStatus
from app.routers.competitions import build_outs
from app.routers.rating import resolve_season
from app.services.rating import compute_rating, load_config
from app.schemas.competitions import CompetitionOut

router = APIRouter(prefix="/public", tags=["public"])
Session = Annotated[AsyncSession, Depends(get_session)]


class PageOut(BaseModel):
    slug: str
    title: str
    body_md: str


class DisciplineCard(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    athletes: int


class OrganizationOut(BaseModel):
    id: int
    name: str
    type: str


class MunicipalityGroup(BaseModel):
    municipality: str
    organizations: list[OrganizationOut]


class Stats(BaseModel):
    athletes: int
    organizations: int
    competitions_this_year: int
    open_registrations: int


class RegionPoint(BaseModel):
    """Муниципалитет для карты региона: занимающиеся и организации подготовки."""

    name: str
    athletes: int
    organizations: int


class NavigatorOut(BaseModel):
    about: list[PageOut]
    guide: list[PageOut]
    disciplines: list[DisciplineCard]
    municipalities: list[MunicipalityGroup]
    upcoming: list[CompetitionOut]
    regions: list[RegionPoint]
    stats: Stats


@router.get("/navigator", response_model=NavigatorOut, summary="Навигатор для новичка: вид спорта, дисциплины, организации, ближайшие соревнования")
async def navigator(session: Session) -> NavigatorOut:
    today = date.today()
    pages = (await session.scalars(select(ContentPage).where(ContentPage.is_published).order_by(ContentPage.order_no))).all()
    disciplines = (await session.scalars(select(Discipline).order_by(Discipline.id))).all()
    counts = dict((await session.execute(
        select(AthleteEnrollment.discipline_id, func.count(func.distinct(AthleteEnrollment.athlete_id)))
        .where(AthleteEnrollment.start_date <= today, or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= today))
        .group_by(AthleteEnrollment.discipline_id)
    )).all())
    by_discipline = {p.discipline_id: p.body_md for p in pages if p.discipline_id}

    municipalities = {m.id: m.name for m in await session.scalars(select(Municipality).order_by(Municipality.name))}
    groups: dict[int, list[OrganizationOut]] = {}
    orgs = (await session.scalars(select(Organization).order_by(Organization.name))).all()
    for o in orgs:
        groups.setdefault(o.municipality_id, []).append(OrganizationOut(id=o.id, name=o.name, type=o.type.value))

    upcoming = (await session.scalars(
        select(Competition).where(Competition.status != CompetitionStatus.DRAFT, Competition.status != CompetitionStatus.CANCELLED,
                                  Competition.end_date >= today).order_by(Competition.start_date).limit(6)
    )).all()
    athletes = await session.scalar(
        select(func.count(func.distinct(AthleteEnrollment.athlete_id)))
        .where(AthleteEnrollment.start_date <= today, or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= today))
    )
    year_competitions = await session.scalar(
        select(func.count()).select_from(Competition).where(func.extract("year", Competition.start_date) == today.year, Competition.status != CompetitionStatus.DRAFT)
    )
    athletes_by_city = dict((await session.execute(
        select(User.municipality_id, func.count(func.distinct(AthleteEnrollment.athlete_id)))
        .join(User, User.id == AthleteEnrollment.athlete_id)
        .where(AthleteEnrollment.start_date <= today, or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= today))
        .group_by(User.municipality_id)
    )).all())
    regions = [
        RegionPoint(name=name, athletes=athletes_by_city.get(mid, 0), organizations=len(groups.get(mid, [])))
        for mid, name in municipalities.items()
    ]
    open_registrations = await session.scalar(select(func.count()).select_from(Competition).where(Competition.status == CompetitionStatus.REGISTRATION_OPEN))
    return NavigatorOut(
        about=[PageOut(slug=p.slug, title=p.title, body_md=p.body_md) for p in pages if not p.discipline_id and p.slug == "what-is"],
        guide=[PageOut(slug=p.slug, title=p.title, body_md=p.body_md) for p in pages if not p.discipline_id and p.slug != "what-is"],
        disciplines=[DisciplineCard(id=d.id, code=d.code, name=d.name, description=by_discipline.get(d.id), athletes=counts.get(d.id, 0)) for d in disciplines],
        municipalities=[MunicipalityGroup(municipality=municipalities[mid], organizations=items) for mid, items in sorted(groups.items(), key=lambda kv: municipalities[kv[0]])],
        upcoming=await build_outs(session, list(upcoming)),
        regions=regions,
        stats=Stats(athletes=athletes or 0, organizations=len(orgs), competitions_this_year=year_competitions or 0,
                    open_registrations=open_registrations or 0),
    )


@router.get("/options", summary="Справочники для формы регистрации (без авторизации)")
async def registration_options(session: Session) -> dict:
    return {
        "disciplines": [{"id": d.id, "name": d.name, "code": d.code} for d in await session.scalars(select(Discipline).order_by(Discipline.id))],
        "municipalities": [{"id": m.id, "name": m.name} for m in await session.scalars(select(Municipality).order_by(Municipality.name))],
        "organizations": [{"id": o.id, "name": o.name, "municipality_id": o.municipality_id}
                          for o in await session.scalars(select(Organization).order_by(Organization.name))],
    }


def mask_name(full: str) -> str:
    """«Макаров Сергей Дмитриевич» → «Макаров С.»: публично показываем только фамилию и инициал."""
    parts = full.split()
    return f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else full


class LeaderRow(BaseModel):
    place: int
    name: str
    organization: str | None
    municipality: str | None
    points: Decimal
    prizes: int


class FeedItem(BaseModel):
    competition_id: int
    title: str
    discipline: str
    published_at: AwareDatetime | None
    participants: int
    winner: str | None


@router.get("/leaderboard", response_model=list[LeaderRow], summary="Публичный лидерборд региона за текущий сезон (ФИО сокращены)")
async def leaderboard(
    session: Session,
    discipline: str = "algorithmic",
    municipality_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[LeaderRow]:
    disc = await session.scalar(select(Discipline).where(Discipline.code == discipline))
    if disc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Дисциплина не найдена")
    season = await resolve_season(session, None)
    table = await compute_rating(session, season, disc, await load_config(session), date.today(), limit=100_000)
    if not table.items:
        return []
    municipalities = {m.id: m.name for m in await session.scalars(select(Municipality))}
    athlete_city = dict((await session.execute(select(User.id, User.municipality_id).where(User.id.in_([i.athlete_id for i in table.items])))).all())
    rows = [i for i in table.items if municipality_id is None or athlete_city.get(i.athlete_id) == municipality_id][:limit]
    return [
        LeaderRow(place=n, name=mask_name(i.athlete_name), organization=i.organization, municipality=municipalities.get(athlete_city.get(i.athlete_id)),
                  points=Decimal(i.total), prizes=i.prizes)
        for n, i in enumerate(rows, start=1)
    ]


@router.get("/feed", response_model=list[FeedItem], summary="Лента: недавно опубликованные протоколы и победители")
async def feed(session: Session, limit: Annotated[int, Query(ge=1, le=20)] = 5) -> list[FeedItem]:
    latest = (
        select(Protocol.competition_id.label("cid"), func.max(Protocol.version).label("v"))
        .where(Protocol.status == ProtocolStatus.PUBLISHED).group_by(Protocol.competition_id).subquery()
    )
    rows = (await session.execute(
        select(Protocol, Competition, Discipline).join(latest, (Protocol.competition_id == latest.c.cid) & (Protocol.version == latest.c.v))
        .join(Competition, Competition.id == Protocol.competition_id).join(Discipline, Discipline.id == Competition.discipline_id)
        .order_by(Protocol.published_at.desc().nulls_last()).limit(limit)
    )).all()
    out = []
    for protocol, comp, disc in rows:
        snapshot_rows = protocol.snapshot.get("rows", [])
        winner = next((r["full_name"] for r in snapshot_rows if r.get("place") == 1), None)
        out.append(FeedItem(competition_id=comp.id, title=comp.title, discipline=disc.name, published_at=protocol.published_at,
                            participants=len(snapshot_rows), winner=mask_name(winner) if winner else None))
    return out
