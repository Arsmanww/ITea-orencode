from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import (
    AthleteEnrollment,
    AthleteProfile,
    CoachAthleteLink,
    Competition,
    CompetitionJudge,
    Discipline,
    JudgePosition,
    Municipality,
    Organization,
    Rank,
    RankAssignment,
    RankRequest,
    Result,
    User,
)
from app.models.enums import LinkStatus, RoleCode
from app.reports.athlete_report_docx import build_athlete_report_docx
from app.reports.protocol_docx import build_protocol_docx
from app.routers.athletes import build_history, ensure_can_view_athlete
from app.routers.competitions import build_outs
from app.routers.judges import latest_category
from app.routers.results import latest_published
from app.services.common import full_name, get_competition_or_404
from app.services.eligibility import age_on
from app.services.files import attachment

router = APIRouter(tags=["documents"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]
AthleteOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))]
HistoryViewer = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION, RoleCode.ATHLETE, RoleCode.COACH))]
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/competitions/{competition_id}/protocol/export", summary="Официальный протокол соревнования в формате .docx")
async def export_protocol(competition_id: int, request: Request, session: Session, current: Authed):
    comp = await get_competition_or_404(session, competition_id, current.active_role)
    protocol = await latest_published(session, competition_id)
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Протокол ещё не опубликован")
    out = (await build_outs(session, [comp]))[0]

    judges = []
    for cj, judge, position in (await session.execute(
        select(CompetitionJudge, User, JudgePosition).join(User, User.id == CompetitionJudge.judge_id)
        .join(JudgePosition, JudgePosition.id == CompetitionJudge.position_id)
        .where(CompetitionJudge.competition_id == competition_id).order_by(CompetitionJudge.position_id, CompetitionJudge.id)
    )).all():
        latest = await latest_category(session, judge.id)
        judges.append({"position": position.name, "name": full_name(judge), "category": latest[1].name if latest else None})

    content = build_protocol_docx({
        "competition": {
            "title": comp.title, "discipline": out.discipline.name, "type": out.type.name, "level": comp.level.value,
            "plan": comp.calendar_plan.value, "plan_number": comp.plan_number, "start_date": comp.start_date, "end_date": comp.end_date,
            "location": comp.location, "format": out.format, "age_groups": [g.name for g in out.age_groups],
            "stages": [{"order_no": s.order_no, "name": s.name, "format": s.format.value, "starts_at": s.starts_at,
                        "ends_at": s.ends_at, "place_or_url": s.place_or_url} for s in out.stages],
        },
        "protocol": {"number": protocol.number, "version": protocol.version, "published_at": protocol.published_at},
        "rows": protocol.snapshot["rows"], "judges": judges,
    })
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="report.protocol_export",
                     entity_type="protocol", entity_id=protocol.id)
    await session.commit()
    safe = protocol.number.replace("/", "-")
    return attachment(content, DOCX, f"protocol-{competition_id}-v{protocol.version}.docx", f"Протокол {safe}.docx")


async def _athlete_report(session: AsyncSession, request: Request, current: CurrentUser, athlete_id: int):
    athlete = await session.get(User, athlete_id)
    if athlete is None or await session.get(AthleteProfile, athlete_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Спортсмен не найден")
    history = await build_history(session, athlete_id, None, None, 1000, 0)
    municipality = await session.get(Municipality, athlete.municipality_id) if athlete.municipality_id else None

    enrollments = [
        f"{d.name}" + (f" – {o.name}" if o else " – без организации")
        for e, d, o in (await session.execute(
            select(AthleteEnrollment, Discipline, Organization).join(Discipline, Discipline.id == AthleteEnrollment.discipline_id)
            .outerjoin(Organization, Organization.id == AthleteEnrollment.organization_id)
            .where(AthleteEnrollment.athlete_id == athlete_id).order_by(AthleteEnrollment.start_date)
        )).all()
    ]
    coaches = [
        f"{full_name(c)} ({d.name})"
        for c, d in (await session.execute(
            select(User, Discipline).join(CoachAthleteLink, CoachAthleteLink.coach_id == User.id)
            .join(Discipline, Discipline.id == CoachAthleteLink.discipline_id)
            .where(CoachAthleteLink.athlete_id == athlete_id, CoachAthleteLink.status == LinkStatus.ACTIVE)
        )).all()
    ]
    ranks = []
    for a, rank, disc, comp, res in (await session.execute(
        select(RankAssignment, Rank, Discipline, Competition, Result)
        .join(Rank, Rank.id == RankAssignment.rank_id).join(Discipline, Discipline.id == RankAssignment.discipline_id)
        .outerjoin(RankRequest, RankRequest.id == RankAssignment.request_id)
        .outerjoin(Competition, Competition.id == RankRequest.competition_id)
        .outerjoin(Result, Result.id == RankRequest.result_id)
        .where(RankAssignment.athlete_id == athlete_id).order_by(RankAssignment.assigned_at)
    )).all():
        ranks.append({
            "rank": rank.name, "discipline": disc.name, "order_number": a.order_number, "order_date": a.order_date,
            "assigned_at": a.assigned_at, "valid_until": a.valid_until,
            "basis": f"{comp.title}" + (f", место {res.place}" if res and res.place else "") if comp else None,
        })
    content = build_athlete_report_docx({
        "athlete": {"full_name": full_name(athlete), "birth_date": athlete.birth_date, "age": age_on(athlete.birth_date, date.today()),
                    "municipality": municipality.name if municipality else None, "enrollments": enrollments, "coaches": coaches},
        "history": [{"title": h.competition_title, "discipline_short": h.discipline, "level": h.level.value, "start_date": h.start_date,
                     "end_date": h.end_date, "place": h.place, "participants": h.participants, "status": h.status.value, "score": h.score,
                     "time_seconds": h.time_seconds, "tasks_solved": h.tasks_solved, "protocol_number": h.protocol_number}
                    for h in history.items],
        "ranks": ranks,
    })
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="report.athlete_export",
                     entity_type="athlete", entity_id=athlete_id)
    await session.commit()
    return attachment(content, DOCX, f"athlete-report-{athlete_id}.docx", f"Справка о выступлениях {full_name(athlete)}.docx")


@router.get("/athletes/me/report/export", summary="Моя справка о выступлениях (.docx)")
async def my_report(request: Request, session: Session, current: AthleteOnly):
    return await _athlete_report(session, request, current, current.user.id)


@router.get("/athletes/{athlete_id}/report/export", summary="Справка о выступлениях и разрядах спортсмена (.docx)")
async def athlete_report(athlete_id: int, request: Request, session: Session, current: HistoryViewer):
    await ensure_can_view_athlete(session, current, athlete_id)
    return await _athlete_report(session, request, current, athlete_id)
