from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import decode_access_token
from app.models import Role, User, UserRole
from app.models.enums import RoleCode

bearer_scheme = HTTPBearer(auto_error=False, description="JWT из POST /api/v1/auth/login")

# порядок ролей в ответах и выбор активной роли по умолчанию при входе
ROLE_PRIORITY = [RoleCode.FEDERATION, RoleCode.ATHLETE, RoleCode.COACH, RoleCode.JUDGE, RoleCode.MINISTRY]

ROLE_TITLES = {
    RoleCode.FEDERATION: "Федерация",
    RoleCode.ATHLETE: "Спортсмен",
    RoleCode.COACH: "Тренер",
    RoleCode.JUDGE: "Судья",
    RoleCode.MINISTRY: "Министерство спорта",
}


@dataclass
class CurrentUser:
    user: User
    roles: list[RoleCode]
    active_role: RoleCode


async def load_roles(session: AsyncSession, user_id: int) -> list[RoleCode]:
    rows = await session.scalars(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return sorted(rows.all(), key=ROLE_PRIORITY.index)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    """Пользователь и активная роль из токена. Роли сверяются с БД на каждом запросе."""
    if credentials is None:
        raise _unauthorized("Требуется авторизация")
    try:
        payload = decode_access_token(credentials.credentials)
        active_role = RoleCode(payload["active_role"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized("Недействительный или просроченный токен") from None

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Пользователь не найден или заблокирован")
    roles = await load_roles(session, user.id)
    if active_role not in roles:
        raise _unauthorized("Активная роль больше не назначена пользователю, войдите заново")
    return CurrentUser(user=user, roles=roles, active_role=active_role)


def require_role(*allowed: RoleCode):
    """Зависимость: пускает, только если АКТИВНАЯ роль входит в allowed.

    Наличие роли у аккаунта недостаточно: пользователь с ролями спортсмен и тренер,
    работающий как спортсмен, получает 403 на тренерских эндпоинтах.
    """
    if not allowed:
        raise ValueError("require_role требует хотя бы одну роль")

    async def checker(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current.active_role not in allowed:
            need = ", ".join(ROLE_TITLES[r] for r in allowed)
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Недостаточно прав: активная роль «{ROLE_TITLES[current.active_role]}», требуется: {need}",
            )
        return current

    return checker
