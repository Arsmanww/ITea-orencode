"""Справочники для форм интерфейса. Доступны любому авторизованному пользователю."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models.enums import RoleCode
from app.models import (
    AgeGroup,
    CompetitionType,
    Discipline,
    JudgeCategory,
    JudgePosition,
    JudgeProfile,
    Municipality,
    Organization,
    Rank,
    User,
)

router = APIRouter(prefix="/reference", tags=["reference"], dependencies=[Depends(get_current_user)])
Session = Annotated[AsyncSession, Depends(get_session)]


class Item(BaseModel):
    id: int
    name: str
    code: str | None = None
    order_no: int | None = None
    validity_months: int | None = None
    is_active: bool | None = None


class AgeGroupItem(BaseModel):
    id: int
    name: str
    min_age: int
    max_age: int


class OrganizationItem(BaseModel):
    id: int
    name: str
    type: str
    municipality_id: int


@router.get("/disciplines", response_model=list[Item], summary="Шесть дисциплин вида спорта")
async def disciplines(session: Session) -> list[Item]:
    return [Item(id=d.id, name=d.name, code=d.code) for d in await session.scalars(select(Discipline).order_by(Discipline.id))]


@router.get("/age-groups", response_model=list[AgeGroupItem])
async def age_groups(session: Session) -> list[AgeGroupItem]:
    return [AgeGroupItem(id=g.id, name=g.name, min_age=g.min_age, max_age=g.max_age)
            for g in await session.scalars(select(AgeGroup).order_by(AgeGroup.min_age))]


@router.get("/competition-types", response_model=list[Item], summary="Типы соревнований (чемпионат, первенство, кубок…)")
async def competition_types(session: Session, include_inactive: bool = False) -> list[Item]:
    stmt = select(CompetitionType).order_by(CompetitionType.id)
    if not include_inactive:
        stmt = stmt.where(CompetitionType.is_active)
    return [Item(id=t.id, name=t.name, is_active=t.is_active) for t in await session.scalars(stmt)]


class CompetitionTypeIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class CompetitionTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None


FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]


async def _ensure_unique_type(session: AsyncSession, name: str, skip_id: int | None = None) -> None:
    stmt = select(CompetitionType.id).where(func.lower(CompetitionType.name) == name.lower())
    if skip_id is not None:
        stmt = stmt.where(CompetitionType.id != skip_id)
    if await session.scalar(stmt.limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Тип «{name}» уже есть в справочнике")


@router.post("/competition-types", response_model=Item, status_code=status.HTTP_201_CREATED,
             summary="Пополнить справочник типов соревнований (федерация)")
async def create_competition_type(data: CompetitionTypeIn, request: Request, session: Session, current: FederationOnly) -> Item:
    name = data.name.strip()
    await _ensure_unique_type(session, name)
    ctype = CompetitionType(name=name)
    session.add(ctype)
    await session.flush()
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="reference.competition_type_create",
                     entity_type="competition_type", entity_id=ctype.id, diff={"name": name})
    await session.commit()
    return Item(id=ctype.id, name=ctype.name, is_active=True)


@router.patch("/competition-types/{type_id}", response_model=Item,
              summary="Переименовать тип или скрыть его из формы создания соревнования (федерация)")
async def update_competition_type(type_id: int, data: CompetitionTypeUpdate, request: Request, session: Session, current: FederationOnly) -> Item:
    ctype = await session.get(CompetitionType, type_id)
    if ctype is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Тип соревнования не найден")
    before = {"name": ctype.name, "is_active": ctype.is_active}
    if data.name is not None:
        await _ensure_unique_type(session, data.name.strip(), ctype.id)
        ctype.name = data.name.strip()
    if data.is_active is not None:
        ctype.is_active = data.is_active
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="reference.competition_type_update",
                     entity_type="competition_type", entity_id=ctype.id,
                     diff={"before": before, "after": {"name": ctype.name, "is_active": ctype.is_active}})
    await session.commit()
    return Item(id=ctype.id, name=ctype.name, is_active=ctype.is_active)


@router.get("/ranks", response_model=list[Item], summary="Разряды и звания ЕВСК")
async def ranks(session: Session) -> list[Item]:
    return [Item(id=r.id, name=r.name, code=r.code, order_no=r.order_no, validity_months=r.validity_months)
            for r in await session.scalars(select(Rank).order_by(Rank.order_no))]


@router.get("/judge-categories", response_model=list[Item])
async def judge_categories(session: Session) -> list[Item]:
    return [Item(id=c.id, name=c.name, code=c.code, order_no=c.order_no, validity_months=c.validity_months)
            for c in await session.scalars(select(JudgeCategory).order_by(JudgeCategory.order_no))]


@router.get("/judge-positions", response_model=list[Item], summary="Судейские должности")
async def judge_positions(session: Session) -> list[Item]:
    return [Item(id=p.id, name=p.name) for p in await session.scalars(select(JudgePosition).order_by(JudgePosition.id))]


@router.get("/municipalities", response_model=list[Item])
async def municipalities(session: Session) -> list[Item]:
    return [Item(id=m.id, name=m.name) for m in await session.scalars(select(Municipality).order_by(Municipality.name))]


@router.get("/organizations", response_model=list[OrganizationItem])
async def organizations(session: Session) -> list[OrganizationItem]:
    return [OrganizationItem(id=o.id, name=o.name, type=o.type.value, municipality_id=o.municipality_id)
            for o in await session.scalars(select(Organization).order_by(Organization.name))]


class JudgeItem(BaseModel):
    id: int
    name: str
    category: str | None
    valid_until: str | None


@router.get("/judges", response_model=list[JudgeItem], summary="Судьи с действующей категорией (для назначения в коллегию, федерация)")
async def judges(session: Session, current: Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]) -> list[JudgeItem]:
    from app.routers.judges import latest_category
    from app.services.common import full_name

    rows = (await session.execute(select(User).join(JudgeProfile, JudgeProfile.user_id == User.id).order_by(User.last_name))).scalars().all()
    out = []
    for user in rows:
        latest = await latest_category(session, user.id)
        out.append(JudgeItem(id=user.id, name=full_name(user), category=latest[1].name if latest else None,
                             valid_until=latest[0].valid_until.isoformat() if latest and latest[0].valid_until else None))
    return out
