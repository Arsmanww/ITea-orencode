import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import exists, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import (
    AgeGroup,
    AthleteEnrollment,
    Competition,
    CompetitionAgeGroup,
    CompetitionStage,
    CompetitionType,
    Discipline,
    StoredFile,
)
from app.models.enums import (
    CalendarPlan,
    CompetitionLevel,
    CompetitionStatus,
    RoleCode,
    StageFormat,
)
from app.schemas.competitions import (
    STATUS_TRANSITIONS,
    AgeGroupOut,
    CompetitionCreate,
    CompetitionListOut,
    CompetitionOut,
    CompetitionUpdate,
    DisciplineRef,
    IdName,
    StageOut,
    check_plan_rules,
)
from app.services.common import get_competition_or_404
from app.services.deadlines import notify_registration_open

router = APIRouter(prefix="/competitions", tags=["competitions"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]

ALLOWED_REGULATION_EXT = {".pdf", ".doc", ".docx"}


async def build_outs(session: AsyncSession, comps: list[Competition]) -> list[CompetitionOut]:
    """Собирает ответы пакетно: этапы, возрастные группы, дисциплины и типы – по одному запросу."""
    if not comps:
        return []
    ids = [c.id for c in comps]
    stages = (await session.scalars(
        select(CompetitionStage).where(CompetitionStage.competition_id.in_(ids)).order_by(CompetitionStage.order_no)
    )).all()
    groups = (await session.execute(
        select(CompetitionAgeGroup.competition_id, AgeGroup)
        .join(AgeGroup, AgeGroup.id == CompetitionAgeGroup.age_group_id)
        .where(CompetitionAgeGroup.competition_id.in_(ids))
        .order_by(AgeGroup.min_age)
    )).all()
    disciplines = {d.id: d for d in await session.scalars(select(Discipline))}
    types = {t.id: t for t in await session.scalars(select(CompetitionType))}

    stages_by: dict[int, list[CompetitionStage]] = {}
    for s in stages:
        stages_by.setdefault(s.competition_id, []).append(s)
    groups_by: dict[int, list[AgeGroup]] = {}
    for cid, g in groups:
        groups_by.setdefault(cid, []).append(g)

    outs = []
    for c in comps:
        formats = {s.format for s in stages_by.get(c.id, [])}
        fmt: Literal["online", "offline", "mixed"] = (
            "mixed" if len(formats) > 1 else "online" if formats == {StageFormat.ONLINE} else "offline"
        )
        d, t = disciplines[c.discipline_id], types[c.type_id]
        outs.append(CompetitionOut(
            id=c.id, title=c.title, discipline=DisciplineRef(id=d.id, code=d.code, name=d.name),
            type=IdName(id=t.id, name=t.name), level=c.level, rating_tier=c.rating_tier, status=c.status,
            calendar_plan=c.calendar_plan, plan_number=c.plan_number, start_date=c.start_date, end_date=c.end_date,
            location=c.location, registration_opens_at=c.registration_opens_at,
            registration_deadline=c.registration_deadline, is_team=c.is_team, description=c.description,
            format=fmt,
            age_groups=[AgeGroupOut(id=g.id, name=g.name, min_age=g.min_age, max_age=g.max_age) for g in groups_by.get(c.id, [])],
            stages=[StageOut(id=s.id, order_no=s.order_no, name=s.name, format=s.format, starts_at=s.starts_at,
                             ends_at=s.ends_at, place_or_url=s.place_or_url) for s in stages_by.get(c.id, [])],
            regulation_url=f"/api/v1/competitions/{c.id}/regulation" if c.regulation_file_id else None,
        ))
    return outs


@router.post("", response_model=CompetitionOut, status_code=status.HTTP_201_CREATED, summary="Создать соревнование (федерация)")
async def create_competition(data: CompetitionCreate, request: Request, session: Session, current: FederationOnly) -> CompetitionOut:
    discipline = await session.get(Discipline, data.discipline_id)
    if discipline is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Дисциплина не найдена")
    ctype = await session.get(CompetitionType, data.type_id)
    if ctype is None or not ctype.is_active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Тип соревнования не найден или отключён")
    groups = (await session.scalars(select(AgeGroup).where(AgeGroup.id.in_(data.age_group_ids)))).all()
    if len(groups) != len(data.age_group_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Одна или несколько возрастных групп не найдены")
    if any(g.discipline_id not in (None, discipline.id) for g in groups):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Возрастная группа относится к другой дисциплине")

    comp = Competition(
        title=data.title, discipline_id=discipline.id, type_id=ctype.id, level=data.level, rating_tier=data.rating_tier,
        status=data.status, calendar_plan=data.calendar_plan,
        plan_number=data.plan_number.strip() if data.plan_number else None,
        start_date=data.start_date, end_date=data.end_date, location=data.location,
        registration_opens_at=data.registration_opens_at, registration_deadline=data.registration_deadline,
        is_team=data.is_team, description=data.description, created_by=current.user.id,
    )
    session.add(comp)
    await session.flush()
    session.add_all(CompetitionAgeGroup(competition_id=comp.id, age_group_id=g.id) for g in groups)
    session.add_all(
        CompetitionStage(competition_id=comp.id, order_no=n, name=s.name, format=s.format, starts_at=s.starts_at,
                         ends_at=s.ends_at, place_or_url=s.place_or_url)
        for n, s in enumerate(data.stages, start=1)
    )
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="competition.create", entity_type="competition", entity_id=comp.id,
                     diff={"title": comp.title, "status": comp.status.value, "calendar_plan": comp.calendar_plan.value})
    if comp.status == CompetitionStatus.REGISTRATION_OPEN:
        await session.flush()
        await notify_registration_open(session, comp)
    await session.commit()
    return (await build_outs(session, [comp]))[0]


@router.get("", response_model=CompetitionListOut, summary="Календарь соревнований с фильтрами")
async def list_competitions(
    session: Session,
    current: Authed,
    discipline_id: int | None = None,
    discipline: Annotated[str | None, Query(description="Код дисциплины, например algorithmic")] = None,
    status_: Annotated[CompetitionStatus | None, Query(alias="status")] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    level: CompetitionLevel | None = None,
    calendar_plan: CalendarPlan | None = None,
    age_group_id: Annotated[int | None, Query(description="Возрастная группа соревнования")] = None,
    for_me: Annotated[bool, Query(description="Роль «Спортсмен»: только те, куда он проходит по дисциплине и возрасту")] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CompetitionListOut:
    stmt = select(Competition)
    if age_group_id is not None:
        stmt = stmt.where(Competition.id.in_(select(CompetitionAgeGroup.competition_id).where(CompetitionAgeGroup.age_group_id == age_group_id)))
    if for_me:
        if current.active_role != RoleCode.ATHLETE:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Фильтр «подходит мне» доступен в роли «Спортсмен»")
        age = func.date_part("year", func.age(Competition.start_date, current.user.birth_date))
        stmt = stmt.where(
            exists(select(CompetitionAgeGroup.competition_id).join(AgeGroup, AgeGroup.id == CompetitionAgeGroup.age_group_id)
                   .where(CompetitionAgeGroup.competition_id == Competition.id, AgeGroup.min_age <= age, AgeGroup.max_age >= age)),
            exists(select(AthleteEnrollment.id).where(
                AthleteEnrollment.athlete_id == current.user.id, AthleteEnrollment.discipline_id == Competition.discipline_id,
                AthleteEnrollment.start_date <= Competition.start_date,
                or_(AthleteEnrollment.end_date.is_(None), AthleteEnrollment.end_date >= Competition.start_date))),
        )
    if current.active_role != RoleCode.FEDERATION:
        stmt = stmt.where(Competition.status != CompetitionStatus.DRAFT)
    if discipline_id is not None:
        stmt = stmt.where(Competition.discipline_id == discipline_id)
    if discipline is not None:
        stmt = stmt.join(Discipline, Discipline.id == Competition.discipline_id).where(Discipline.code == discipline)
    if status_ is not None:
        stmt = stmt.where(Competition.status == status_)
    if year is not None:
        stmt = stmt.where(extract("year", Competition.start_date) == year)
    if level is not None:
        stmt = stmt.where(Competition.level == level)
    if calendar_plan is not None:
        stmt = stmt.where(Competition.calendar_plan == calendar_plan)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    comps = (await session.scalars(stmt.order_by(Competition.start_date.desc(), Competition.id).limit(limit).offset(offset))).all()
    return CompetitionListOut(items=await build_outs(session, list(comps)), total=total or 0, limit=limit, offset=offset)


@router.get("/{competition_id}", response_model=CompetitionOut, summary="Карточка соревнования")
async def get_competition(competition_id: int, session: Session, current: Authed) -> CompetitionOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    return (await build_outs(session, [comp]))[0]


@router.patch("/{competition_id}", response_model=CompetitionOut, summary="Изменить соревнование и статус (федерация)")
async def update_competition(competition_id: int, data: CompetitionUpdate, request: Request, session: Session, current: FederationOnly) -> CompetitionOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    if comp.status in (CompetitionStatus.FINISHED, CompetitionStatus.CANCELLED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Завершённое или отменённое соревнование изменять нельзя")
    nullable = {"plan_number", "location", "registration_opens_at", "registration_deadline", "description"}
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None or k in nullable}

    new_status = changes.get("status", comp.status)
    if new_status != comp.status and new_status not in STATUS_TRANSITIONS[comp.status]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Переход статуса {comp.status.value} → {new_status.value} недопустим")
    if "type_id" in changes:
        ctype = await session.get(CompetitionType, changes["type_id"])
        if ctype is None or not ctype.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Тип соревнования не найден или отключён")

    plan = changes.get("calendar_plan", comp.calendar_plan)
    number = changes.get("plan_number", comp.plan_number)
    start, end = changes.get("start_date", comp.start_date), changes.get("end_date", comp.end_date)
    opens = changes.get("registration_opens_at", comp.registration_opens_at)
    deadline = changes.get("registration_deadline", comp.registration_deadline)
    try:
        if end < start:
            raise ValueError("Дата окончания раньше даты начала")
        if opens and deadline and deadline < opens:
            raise ValueError("Дедлайн приёма заявок раньше открытия регистрации")
        check_plan_rules(comp.level, comp.rating_tier, plan, number, new_status)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None

    before = {k: str(getattr(comp, k)) for k in changes}
    opened = new_status == CompetitionStatus.REGISTRATION_OPEN and comp.status != CompetitionStatus.REGISTRATION_OPEN
    for key, value in changes.items():
        setattr(comp, key, value)
    if opened:
        await notify_registration_open(session, comp)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="competition.update", entity_type="competition", entity_id=comp.id,
                     diff={"before": before, "after": {k: str(v) for k, v in changes.items()}})
    await session.commit()
    return (await build_outs(session, [comp]))[0]


@router.post("/{competition_id}/regulation", response_model=CompetitionOut, summary="Загрузить положение (регламент), PDF/DOC/DOCX")
async def upload_regulation(competition_id: int, file: UploadFile, request: Request, session: Session, current: FederationOnly) -> CompetitionOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_REGULATION_EXT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Положение принимается в формате PDF, DOC или DOCX")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Файл пустой")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Файл больше {settings.max_upload_mb} МБ")

    folder = Path(settings.upload_dir) / "regulations"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(content)
    stored = StoredFile(path=str(path), original_name=Path(file.filename or f"regulation{ext}").name[:255],
                        mime=file.content_type or "application/octet-stream", size=len(content), uploaded_by=current.user.id)
    session.add(stored)
    await session.flush()
    comp.regulation_file_id = stored.id
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="competition.regulation_upload", entity_type="competition", entity_id=comp.id,
                     diff={"file": stored.original_name, "size": stored.size})
    await session.commit()
    return (await build_outs(session, [comp]))[0]


@router.get("/{competition_id}/regulation", summary="Скачать положение (публично для опубликованных соревнований)")
async def download_regulation(competition_id: int, session: Session) -> FileResponse:
    comp = await get_competition_or_404(session, competition_id, RoleCode.ATHLETE)
    stored = await session.get(StoredFile, comp.regulation_file_id) if comp.regulation_file_id else None
    if stored is None or not Path(stored.path).is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Положение не загружено")
    return FileResponse(stored.path, media_type=stored.mime, filename=stored.original_name)
