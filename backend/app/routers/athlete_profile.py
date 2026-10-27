import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import (
    AthleteEnrollment,
    AthleteProfile,
    CoachAthleteLink,
    Consent,
    Discipline,
    Municipality,
    Organization,
    StoredFile,
    User,
)
from app.models.enums import LinkStatus, RoleCode, TrainingStage
from app.schemas.auth import UserOut
from app.schemas.people import DisciplineRef, UserRef
from app.services.common import full_name
from app.services.eligibility import age_on

router = APIRouter(tags=["athlete-profile"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]
AthleteOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))]
ALLOWED_CONSENT_EXT = {".pdf", ".jpg", ".jpeg", ".png"}


class EnrollmentOut(BaseModel):
    discipline: DisciplineRef
    organization: str | None
    training_stage: TrainingStage | None
    start_date: date


class CoachOut(BaseModel):
    coach: UserRef
    discipline: DisciplineRef


class ConsentOut(BaseModel):
    accepted: bool
    has_scan: bool
    signed_by: str | None
    is_guardian: bool = False


class AthleteProfileOut(BaseModel):
    user: UserOut
    age: int
    municipality: str | None
    guardian_name: str | None
    guardian_phone: str | None
    guardian_email: str | None
    antidoping_course_date: date | None
    antidoping_cert_url: str | None
    enrollments: list[EnrollmentOut]
    coaches: list[CoachOut]
    consent: ConsentOut


class AntidopingIn(BaseModel):
    course_date: date
    cert_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://\S+$")


async def _consent_out(session: AsyncSession, user_id: int) -> ConsentOut:
    consent = await session.scalar(select(Consent).where(Consent.user_id == user_id).order_by(Consent.id.desc()).limit(1))
    if consent is None:
        return ConsentOut(accepted=False, has_scan=False, signed_by=None)
    return ConsentOut(accepted=True, has_scan=consent.file_id is not None, signed_by=consent.signed_by_name, is_guardian=consent.is_guardian)


async def _profile_out(session: AsyncSession, user: User) -> AthleteProfileOut:
    profile = await session.get(AthleteProfile, user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль спортсмена не найден")
    municipality = await session.get(Municipality, user.municipality_id) if user.municipality_id else None
    enrollments = [
        EnrollmentOut(discipline=DisciplineRef(id=d.id, code=d.code, name=d.name), organization=o.name if o else None,
                      training_stage=e.training_stage, start_date=e.start_date)
        for e, d, o in (await session.execute(
            select(AthleteEnrollment, Discipline, Organization).join(Discipline, Discipline.id == AthleteEnrollment.discipline_id)
            .outerjoin(Organization, Organization.id == AthleteEnrollment.organization_id)
            .where(AthleteEnrollment.athlete_id == user.id, AthleteEnrollment.end_date.is_(None)).order_by(Discipline.id)
        )).all()
    ]
    coaches = [
        CoachOut(coach=UserRef(id=c.id, full_name=full_name(c)), discipline=DisciplineRef(id=d.id, code=d.code, name=d.name))
        for c, d in (await session.execute(
            select(User, Discipline).join(CoachAthleteLink, CoachAthleteLink.coach_id == User.id)
            .join(Discipline, Discipline.id == CoachAthleteLink.discipline_id)
            .where(CoachAthleteLink.athlete_id == user.id, CoachAthleteLink.status == LinkStatus.ACTIVE).order_by(Discipline.id)
        )).all()
    ]
    return AthleteProfileOut(
        user=UserOut.model_validate(user), age=age_on(user.birth_date, date.today()), municipality=municipality.name if municipality else None,
        guardian_name=profile.guardian_name, guardian_phone=profile.guardian_phone, guardian_email=profile.guardian_email,
        antidoping_course_date=profile.antidoping_course_date, antidoping_cert_url=profile.antidoping_cert_url,
        enrollments=enrollments, coaches=coaches, consent=await _consent_out(session, user.id),
    )


@router.get("/athletes/me/profile", response_model=AthleteProfileOut, summary="Профиль спортсмена: занятия, тренеры, антидопинг, согласие")
async def my_profile(session: Session, current: AthleteOnly) -> AthleteProfileOut:
    return await _profile_out(session, current.user)


@router.put("/athletes/me/antidoping", response_model=AthleteProfileOut, summary="Отметка о прохождении онлайн-курса РУСАДА")
async def set_antidoping(data: AntidopingIn, request: Request, session: Session, current: AthleteOnly) -> AthleteProfileOut:
    if data.course_date > date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Дата прохождения курса не может быть в будущем")
    profile = await session.get(AthleteProfile, current.user.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль спортсмена не найден")
    before = {"course_date": str(profile.antidoping_course_date), "cert_url": profile.antidoping_cert_url}
    profile.antidoping_course_date, profile.antidoping_cert_url = data.course_date, data.cert_url
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="athlete.antidoping_update",
                     entity_type="athlete_profile", entity_id=current.user.id,
                     diff={"before": before, "after": {"course_date": str(data.course_date), "cert_url": data.cert_url}})
    await session.commit()
    return await _profile_out(session, current.user)


@router.get("/me/consent", response_model=ConsentOut, summary="Состояние согласия на обработку персональных данных")
async def my_consent(session: Session, current: Authed) -> ConsentOut:
    return await _consent_out(session, current.user.id)


@router.post("/me/consent", response_model=ConsentOut, status_code=status.HTTP_201_CREATED,
             summary="Загрузить скан подписанного согласия (спортсмена или законного представителя)")
async def upload_consent(file: UploadFile, request: Request, session: Session, current: Authed, signed_by_name: Annotated[str | None, Form()] = None) -> ConsentOut:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_CONSENT_EXT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Скан принимается в формате PDF, JPG или PNG")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Файл пустой")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Файл больше {settings.max_upload_mb} МБ")
    folder = Path(settings.upload_dir) / "consents"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(content)
    stored = StoredFile(path=str(path), original_name=Path(file.filename or f"consent{ext}").name[:255],
                        mime=file.content_type or "application/octet-stream", size=len(content), uploaded_by=current.user.id)
    session.add(stored)
    await session.flush()
    consent = await session.scalar(select(Consent).where(Consent.user_id == current.user.id).order_by(Consent.id.desc()).limit(1))
    if consent is None:
        consent = Consent(user_id=current.user.id, signed_by_name=(signed_by_name or full_name(current.user)).strip(), is_guardian=False)
        session.add(consent)
    consent.file_id = stored.id
    if signed_by_name and signed_by_name.strip():
        consent.signed_by_name = signed_by_name.strip()
    await session.flush()
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role, action="consent.scan_upload",
                     entity_type="consent", entity_id=consent.id, diff={"file": stored.original_name, "size": stored.size})
    await session.commit()
    return await _consent_out(session, current.user.id)
