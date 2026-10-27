from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import (
    Competition,
    CompetitionApplication,
    Protocol,
    Result,
    Team,
    User,
)
from app.models.enums import ApplicationStatus, CompetitionStatus, NotificationKind, ProtocolStatus, ResultStatus, RoleCode
from app.schemas.results import EvskCandidate, ProtocolOut, ResultOut, ResultsIn
from app.services.common import full_name, get_competition_or_404
from app.services.notifications import notify
from app.services.ranking import assign_places
from app.services.ranks import evsk_candidates

router = APIRouter(prefix="/competitions/{competition_id}", tags=["results"])

Session = Annotated[AsyncSession, Depends(get_session)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
Authed = Annotated[CurrentUser, Depends(get_current_user)]

# результаты вносят после закрытия приёма заявок
RESULT_ENTRY_STATUSES = {CompetitionStatus.REGISTRATION_CLOSED, CompetitionStatus.IN_PROGRESS, CompetitionStatus.FINISHED}


async def latest_published(session: AsyncSession, competition_id: int) -> Protocol | None:
    return await session.scalar(
        select(Protocol)
        .where(Protocol.competition_id == competition_id, Protocol.status == ProtocolStatus.PUBLISHED)
        .order_by(Protocol.version.desc()).limit(1)
    )


def result_out(r: Result, name: str) -> ResultOut:
    return ResultOut(id=r.id, application_id=r.application_id, athlete_id=r.athlete_id, athlete_name=name, place=r.place,
                     status=r.status, score=r.score, time_seconds=r.time_seconds, tasks_solved=r.tasks_solved,
                     details=r.details, note=r.note)


async def load_results(session: AsyncSession, competition_id: int) -> list[tuple[Result, User]]:
    rows = (await session.execute(
        select(Result, User).join(User, User.id == Result.athlete_id)
        .where(Result.competition_id == competition_id)
        .order_by(Result.place.asc().nulls_last(), User.last_name)
    )).all()
    return [(r, u) for r, u in rows]


@router.post("/results", response_model=list[ResultOut], summary="Внести результаты участников с одобренными заявками (федерация)")
async def submit_results(competition_id: int, data: ResultsIn, request: Request, session: Session, current: FederationOnly) -> list[ResultOut]:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    if comp.status not in RESULT_ENTRY_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Результаты вносятся после закрытия приёма заявок (статусы registration_closed, in_progress)")
    if await latest_published(session, competition_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Протокол уже опубликован, результаты изменять нельзя")

    ids = [r.application_id for r in data.results]
    apps = {a.id: a for a in await session.scalars(
        select(CompetitionApplication).where(CompetitionApplication.id.in_(ids), CompetitionApplication.competition_id == competition_id)
    )}
    unknown = [i for i in ids if i not in apps]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Заявки не найдены в этом соревновании: {unknown}")
    not_approved = [i for i in ids if apps[i].status != ApplicationStatus.APPROVED]
    if not_approved:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Результат можно внести только для одобренных заявок, нарушают: {not_approved}")

    existing = {r.application_id: r for r in await session.scalars(select(Result).where(Result.application_id.in_(ids)))}
    for item in data.results:
        ranked = item.status == ResultStatus.RANKED
        values = dict(
            status=item.status,
            score=item.score if ranked else None,
            time_seconds=item.time_seconds if ranked else None,
            tasks_solved=item.tasks_solved if ranked else None,
            details=item.details if ranked else None,
            note=item.note,
            place=None,
        )
        result = existing.get(item.application_id)
        if result is None:
            session.add(Result(competition_id=competition_id, application_id=item.application_id,
                               athlete_id=apps[item.application_id].athlete_id, **values))
        else:
            for k, v in values.items():
                setattr(result, k, v)
    await session.flush()
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="results.submit", entity_type="competition", entity_id=competition_id,
                     diff={"applications": ids})
    await session.commit()
    return [result_out(r, full_name(u)) for r, u in await load_results(session, competition_id)]


@router.get("/results", response_model=list[ResultOut], summary="Внесённые результаты (федерация)")
async def list_results(competition_id: int, session: Session, current: FederationOnly) -> list[ResultOut]:
    await get_competition_or_404(session, competition_id, current.active_role)
    return [result_out(r, full_name(u)) for r, u in await load_results(session, competition_id)]


@router.post("/publish-protocol", response_model=ProtocolOut, status_code=status.HTTP_201_CREATED,
             summary="Ранжировать всех участников и опубликовать протокол (федерация)")
async def publish_protocol(competition_id: int, request: Request, session: Session, current: FederationOnly) -> ProtocolOut:
    comp: Competition = await get_competition_or_404(session, competition_id, current.active_role)
    if comp.status not in RESULT_ENTRY_STATUSES or comp.status == CompetitionStatus.FINISHED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Протокол публикуется после закрытия приёма заявок и ввода результатов")
    if await latest_published(session, competition_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Протокол этого соревнования уже опубликован")

    approved = (await session.scalars(
        select(CompetitionApplication).where(CompetitionApplication.competition_id == competition_id,
                                             CompetitionApplication.status == ApplicationStatus.APPROVED)
    )).all()
    if not approved:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Нет участников с одобренными заявками")
    rows = await load_results(session, competition_id)
    have = {r.application_id for r, _ in rows}
    missing = [a.id for a in approved if a.id not in have]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Не внесены результаты по заявкам {missing}; для неявившихся укажите status=did_not_start")

    assign_places([r for r, _ in rows])
    teams = {t.id: t.name for t in await session.scalars(select(Team).where(Team.competition_id == competition_id))}
    team_of = {a.athlete_id: teams.get(a.team_id) for a in approved}

    ordered = sorted(rows, key=lambda x: (x[0].place is None, x[0].place or 0, x[1].last_name, x[1].first_name))
    snapshot_rows = [
        {
            "place": r.place, "athlete_id": u.id, "full_name": full_name(u), "birth_date": u.birth_date.isoformat(),
            "team": team_of.get(u.id),
            "score": str(r.score) if r.score is not None else None,
            "time_seconds": str(r.time_seconds) if r.time_seconds is not None else None,
            "tasks_solved": r.tasks_solved, "status": r.status.value, "note": r.note,
        }
        for r, u in ordered
    ]
    version = (await session.scalar(select(func.max(Protocol.version)).where(Protocol.competition_id == competition_id)) or 0) + 1
    now = datetime.now(timezone.utc)
    protocol = Protocol(
        competition_id=competition_id, number=f"П-{competition_id:04d}/{comp.start_date.year}", version=version,
        status=ProtocolStatus.PUBLISHED, generated_by=current.user.id, generated_at=now, published_at=now,
        snapshot={"competition": comp.title, "start_date": comp.start_date.isoformat(), "end_date": comp.end_date.isoformat(),
                  "location": comp.location, "participants": len(snapshot_rows), "rows": snapshot_rows},
    )
    session.add(protocol)
    comp.status = CompetitionStatus.FINISHED
    await session.flush()
    coach_of = {a.athlete_id: a.coach_id for a in approved}
    for r, u in rows:
        place = f"место {r.place}" if r.place else {"did_not_start": "неявка", "disqualified": "дисквалификация"}.get(r.status.value, "участие")
        for uid in {u.id, *([coach_of[u.id]] if coach_of.get(u.id) else [])}:
            await notify(session, uid, NotificationKind.PROTOCOL_PUBLISHED, "Опубликован протокол",
                         f"{full_name(u)}: протокол {protocol.number} соревнования «{comp.title}» опубликован, результат: {place}.",
                         entity_type="protocol", entity_id=protocol.id)
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="protocol.publish", entity_type="protocol", entity_id=protocol.id,
                     diff={"competition_id": competition_id, "version": version, "participants": len(snapshot_rows)})
    await session.commit()
    return ProtocolOut(id=protocol.id, competition_id=competition_id, number=protocol.number, version=protocol.version,
                       status=protocol.status, published_at=protocol.published_at, snapshot=protocol.snapshot)


@router.get("/protocol", response_model=ProtocolOut, summary="Опубликованный протокол соревнования")
async def get_protocol(competition_id: int, session: Session, current: Authed) -> ProtocolOut:
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    protocol = await latest_published(session, competition_id)
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Протокол ещё не опубликован")
    evsk = await evsk_candidates(session, comp) if current.active_role == RoleCode.FEDERATION else []
    return ProtocolOut(id=protocol.id, competition_id=competition_id, number=protocol.number, version=protocol.version,
                       status=protocol.status, published_at=protocol.published_at, snapshot=protocol.snapshot,
                       evsk=[EvskCandidate(**c) for c in evsk])
