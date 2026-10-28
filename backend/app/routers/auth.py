from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import ROLE_PRIORITY, ROLE_TITLES, CurrentUser, get_current_user, load_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AthleteEnrollment, AthleteProfile, Consent, Discipline, Municipality, Organization, Role, User, UserRole
from app.models.enums import RoleCode, TrainingStage
from app.schemas.auth import ForgotPasswordIn, LoginIn, MeOut, RegisterIn, ResetPasswordIn, SwitchRoleIn, TokenOut, UserOut
from app.services.email import notify_account_event
from app.services.password_reset import consume_reset_token, issue_reset_token

router = APIRouter(prefix="/auth", tags=["auth"])

# сравнение с фиктивным хешем выравнивает время ответа для несуществующих email
_DUMMY_HASH = hash_password("dummy-password")

Session = Annotated[AsyncSession, Depends(get_session)]


def _token_response(user_id: int, roles: list, active_role) -> TokenOut:
    token, expires_in = create_access_token(user_id, [r.value for r in roles], active_role.value)
    return TokenOut(access_token=token, expires_in=expires_in, roles=roles, active_role=active_role)


@router.post("/login", response_model=TokenOut, summary="Вход по email и паролю")
async def login(data: LoginIn, request: Request, session: Session) -> TokenOut:
    user = await session.scalar(select(User).where(User.email == data.email.strip().lower()))
    password_ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok or not user.is_active:
        await log_action(session, request, user_id=user.id if user else None, active_role=None,
                         action="auth.login_failed", entity_type="user", entity_id=user.id if user else None,
                         diff={"email": data.email[:255]})
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль", headers={"WWW-Authenticate": "Bearer"})

    roles = await load_roles(session, user.id)
    if not roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунту не назначено ни одной роли")
    if data.role is not None:
        if data.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"У пользователя нет роли «{ROLE_TITLES[data.role]}»")
        active_role = data.role
    else:
        active_role = min(roles, key=ROLE_PRIORITY.index)

    await log_action(session, request, user_id=user.id, active_role=active_role,
                     action="auth.login", entity_type="user", entity_id=user.id)
    await session.commit()
    await notify_account_event(
        user, "Выполнен вход в аккаунт — ФСП Оренбургской области",
        f"Здравствуйте, {user.first_name}!\n\n"
        f"Выполнен вход в ваш аккаунт на платформе ФСП Оренбургской области ({user.email}).\n\n"
        "Если это были не вы — смените пароль через «Забыли пароль?» на странице входа.",
    )
    return _token_response(user.id, roles, active_role)


@router.get("/me", response_model=MeOut, summary="Профиль текущего пользователя и его роли")
async def me(current: Annotated[CurrentUser, Depends(get_current_user)]) -> MeOut:
    return MeOut(user=UserOut.model_validate(current.user), roles=current.roles, active_role=current.active_role)


@router.post("/switch-role", response_model=TokenOut, summary="Переключить активную роль без повторного входа")
async def switch_role(
    data: SwitchRoleIn,
    request: Request,
    session: Session,
    current: Annotated[CurrentUser, Depends(get_current_user)],
) -> TokenOut:
    if data.role not in current.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"У пользователя нет роли «{ROLE_TITLES[data.role]}»")
    await log_action(session, request, user_id=current.user.id, active_role=data.role,
                     action="auth.switch_role", entity_type="user", entity_id=current.user.id,
                     diff={"from": current.active_role.value, "to": data.role.value})
    await session.commit()
    return _token_response(current.user.id, current.roles, data.role)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED,
             summary="Быстрая регистрация спортсмена с согласием на обработку ПДн")
async def register(data: RegisterIn, request: Request, session: Session) -> TokenOut:
    email = data.email.strip().lower()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с таким email уже зарегистрирован")
    disciplines = (await session.scalars(select(Discipline).where(Discipline.id.in_(set(data.discipline_ids))))).all()
    if len(disciplines) != len(set(data.discipline_ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Дисциплина не найдена")
    if data.organization_id and await session.get(Organization, data.organization_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Организация не найдена")
    if data.municipality_id and await session.get(Municipality, data.municipality_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Муниципалитет не найден")

    today = date.today()
    minor = (today.year - data.birth_date.year - ((today.month, today.day) < (data.birth_date.month, data.birth_date.day))) < 18
    user = User(email=email, password_hash=hash_password(data.password), last_name=data.last_name.strip(), first_name=data.first_name.strip(),
                patronymic=data.patronymic.strip() if data.patronymic else None, birth_date=data.birth_date, gender=data.gender,
                municipality_id=data.municipality_id)
    session.add(user)
    await session.flush()
    role = await session.scalar(select(Role).where(Role.code == RoleCode.ATHLETE))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.add(AthleteProfile(user_id=user.id, guardian_name=data.guardian_name if minor else None,
                               guardian_phone=data.guardian_phone if minor else None, guardian_email=data.guardian_email if minor else None))
    await session.flush()
    session.add_all(
        AthleteEnrollment(athlete_id=user.id, discipline_id=d.id, organization_id=data.organization_id,
                          training_stage=TrainingStage.INITIAL, start_date=today)
        for d in disciplines
    )
    signer = (data.guardian_name or "").strip() if minor else f"{user.last_name} {user.first_name}"
    session.add(Consent(user_id=user.id, signed_by_name=signer, is_guardian=minor, file_id=None))
    await log_action(session, request, user_id=user.id, active_role=RoleCode.ATHLETE, action="auth.register",
                     entity_type="user", entity_id=user.id, diff={"consent": True, "minor": minor})
    await session.commit()
    await notify_account_event(
        user, "Регистрация на платформе — ФСП Оренбургской области",
        f"Здравствуйте, {user.first_name}!\n\n"
        f"Ваш аккаунт на платформе ФСП Оренбургской области успешно зарегистрирован.\nЛогин: {user.email}\n\n"
        "Теперь можно подавать заявки на соревнования и следить за их статусом в личном кабинете.",
    )
    return _token_response(user.id, [RoleCode.ATHLETE], RoleCode.ATHLETE)


class MessageOut(BaseModel):
    detail: str


_FORGOT_PASSWORD_MESSAGE = "Если такой email зарегистрирован, на него отправлена ссылка для восстановления пароля"


@router.post("/forgot-password", response_model=MessageOut, summary="Запросить ссылку для восстановления пароля")
async def forgot_password(data: ForgotPasswordIn, request: Request, session: Session) -> MessageOut:
    """Ответ одинаков независимо от того, существует ли такой email, — иначе по этому эндпоинту
    можно было бы проверять, кто зарегистрирован на платформе."""
    user = await session.scalar(select(User).where(User.email == data.email.strip().lower()))
    if user is not None and user.is_active:
        await issue_reset_token(session, user)
        await log_action(session, request, user_id=user.id, active_role=None,
                         action="auth.password_reset_requested", entity_type="user", entity_id=user.id)
        await session.commit()
    return MessageOut(detail=_FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=MessageOut, summary="Задать новый пароль по ссылке из письма")
async def reset_password(data: ResetPasswordIn, request: Request, session: Session) -> MessageOut:
    user = await consume_reset_token(session, data.token)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ссылка недействительна или уже использована, запросите новую")
    user.password_hash = hash_password(data.new_password)
    await log_action(session, request, user_id=user.id, active_role=None,
                     action="auth.password_reset", entity_type="user", entity_id=user.id)
    await session.commit()
    return MessageOut(detail="Пароль изменён, можно войти с новым паролем")
