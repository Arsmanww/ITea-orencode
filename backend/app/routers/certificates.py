"""Справка об участии с QR-кодом (Д10): выдача спортсменом и публичная проверка подлинности."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models import Competition, Discipline, ParticipationCertificate, Result, User
from app.models.enums import CompetitionLevel, ResultStatus, RoleCode
from app.reports.certificate_docx import build_certificate_docx
from app.reports.qr import qr_png
from app.routers.results import latest_published
from app.services.common import full_name
from app.services.files import attachment

router = APIRouter(tags=["certificates"])

Session = Annotated[AsyncSession, Depends(get_session)]
AthleteOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))]
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class CertificateOut(BaseModel):
    id: int
    number: str
    verify_token: uuid.UUID
    verify_url: str
    issued_at: AwareDatetime
    revoked: bool
    competition_title: str
    discipline: str
    place: int | None
    participants: int


class VerifyOut(BaseModel):
    """Публичные данные справки. Дата рождения и контакты не раскрываются."""

    valid: bool
    status: str
    number: str
    issued_at: AwareDatetime
    athlete_name: str
    competition_title: str
    discipline: str
    level: CompetitionLevel
    start_date: date
    end_date: date
    place: int | None
    participants: int
    score: Decimal | None


class CertificateCreate(BaseModel):
    result_id: int


def verify_url(token: uuid.UUID) -> str:
    return f"{settings.public_base_url.rstrip('/')}/verify/{token}"


async def _details(session: AsyncSession, cert: ParticipationCertificate):
    row = (await session.execute(
        select(Result, Competition, Discipline, User)
        .join(Competition, Competition.id == Result.competition_id)
        .join(Discipline, Discipline.id == Competition.discipline_id)
        .join(User, User.id == Result.athlete_id)
        .where(Result.id == cert.result_id)
    )).one()
    result, comp, disc, user = row
    participants = len((await session.scalars(
        select(Result.id).where(Result.competition_id == comp.id, Result.status == ResultStatus.RANKED))).all())
    return result, comp, disc, user, participants


async def _out(session: AsyncSession, cert: ParticipationCertificate) -> CertificateOut:
    result, comp, disc, _, participants = await _details(session, cert)
    return CertificateOut(id=cert.id, number=cert.number, verify_token=cert.verify_token, verify_url=verify_url(cert.verify_token),
                          issued_at=cert.issued_at, revoked=cert.revoked, competition_title=comp.title, discipline=disc.name,
                          place=result.place, participants=participants)


@router.post("/athletes/me/certificates", response_model=CertificateOut, summary="Сформировать справку об участии с номером и QR-кодом")
async def create_certificate(data: CertificateCreate, request: Request, response: Response, session: Session, current: AthleteOnly) -> CertificateOut:
    result = await session.get(Result, data.result_id)
    if result is None or result.athlete_id != current.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Результат не найден")
    if result.status != ResultStatus.RANKED or result.place is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Справка выдаётся по результату участника в зачёте")
    if await latest_published(session, result.competition_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Протокол соревнования ещё не опубликован")

    existing = await session.scalar(
        select(ParticipationCertificate).where(ParticipationCertificate.result_id == result.id, ParticipationCertificate.revoked.is_(False)).limit(1)
    )
    if existing is not None:
        return await _out(session, existing)

    comp = await session.get(Competition, result.competition_id)
    cert = ParticipationCertificate(number=f"tmp-{uuid.uuid4().hex}", athlete_id=current.user.id, result_id=result.id,
                                    snapshot={"competition_id": comp.id, "place": result.place})
    session.add(cert)
    await session.flush()
    cert.number = f"ФСП-56-{comp.end_date.year}-{cert.id:05d}"
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="certificate.issue",
                     entity_type="certificate", entity_id=cert.id, diff={"result_id": result.id})
    await session.commit()
    await session.refresh(cert)
    response.status_code = status.HTTP_201_CREATED
    return await _out(session, cert)


@router.get("/athletes/me/certificates", response_model=list[CertificateOut], summary="Мои справки об участии")
async def my_certificates(session: Session, current: AthleteOnly) -> list[CertificateOut]:
    certs = (await session.scalars(
        select(ParticipationCertificate).where(ParticipationCertificate.athlete_id == current.user.id).order_by(ParticipationCertificate.id.desc())
    )).all()
    return [await _out(session, c) for c in certs]


@router.get("/athletes/me/certificates/{certificate_id}/export", summary="Справка об участии с QR-кодом (.docx)")
async def export_certificate(certificate_id: int, session: Session, current: AthleteOnly):
    cert = await session.get(ParticipationCertificate, certificate_id)
    if cert is None or cert.athlete_id != current.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Справка не найдена")
    result, comp, disc, user, participants = await _details(session, cert)
    protocol = await latest_published(session, comp.id)
    content = build_certificate_docx(
        {
            "number": cert.number, "athlete_name": full_name(user), "birth_date": user.birth_date, "competition_title": comp.title,
            "discipline": disc.name, "level": comp.level.value, "start_date": comp.start_date, "end_date": comp.end_date,
            "location": comp.location, "place": result.place, "participants": participants, "score": result.score,
            "protocol_number": protocol.number if protocol else "–", "issued_at": cert.issued_at, "verify_url": verify_url(cert.verify_token),
        },
        qr_png(verify_url(cert.verify_token)),
    )
    return attachment(content, DOCX, f"certificate-{cert.id}.docx", f"Справка об участии {cert.number}.docx")


@router.get("/public/certificates/{token}", response_model=VerifyOut, summary="Публичная проверка подлинности справки (без авторизации)")
async def verify_certificate(token: uuid.UUID, session: Session) -> VerifyOut:
    cert = await session.scalar(select(ParticipationCertificate).where(ParticipationCertificate.verify_token == token))
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Справка с таким номером не найдена")
    result, comp, disc, user, participants = await _details(session, cert)
    return VerifyOut(valid=not cert.revoked, status="revoked" if cert.revoked else "valid", number=cert.number, issued_at=cert.issued_at,
                     athlete_name=full_name(user), competition_title=comp.title, discipline=disc.name, level=comp.level,
                     start_date=comp.start_date, end_date=comp.end_date, place=result.place, participants=participants, score=result.score)


@router.get("/public/certificates/{token}/qr.png", summary="QR-код справки (PNG)", response_class=Response)
async def certificate_qr(token: uuid.UUID, session: Session) -> Response:
    exists = await session.scalar(select(ParticipationCertificate.id).where(ParticipationCertificate.verify_token == token))
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Справка не найдена")
    return Response(content=qr_png(verify_url(token)), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
