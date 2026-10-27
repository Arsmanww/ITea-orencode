"""Диагностические эндпоинты проверки ролевой модели (С1): по одному на каждую роль.

Показывают на стенде, что права проверяются по активной роли, а не по набору ролей аккаунта.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_role
from app.models.enums import RoleCode
from app.schemas.auth import RbacCheckOut

router = APIRouter(prefix="/rbac", tags=["rbac"])


def _out(current: CurrentUser, required: RoleCode) -> RbacCheckOut:
    return RbacCheckOut(ok=True, required_role=required, active_role=current.active_role, user_id=current.user.id)


@router.get("/federation", response_model=RbacCheckOut, summary="Доступно только активной роли «Федерация»")
async def federation_only(current: Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]) -> RbacCheckOut:
    return _out(current, RoleCode.FEDERATION)


@router.get("/athlete", response_model=RbacCheckOut, summary="Доступно только активной роли «Спортсмен»")
async def athlete_only(current: Annotated[CurrentUser, Depends(require_role(RoleCode.ATHLETE))]) -> RbacCheckOut:
    return _out(current, RoleCode.ATHLETE)


@router.get("/coach", response_model=RbacCheckOut, summary="Доступно только активной роли «Тренер»")
async def coach_only(current: Annotated[CurrentUser, Depends(require_role(RoleCode.COACH))]) -> RbacCheckOut:
    return _out(current, RoleCode.COACH)


@router.get("/judge", response_model=RbacCheckOut, summary="Доступно только активной роли «Судья»")
async def judge_only(current: Annotated[CurrentUser, Depends(require_role(RoleCode.JUDGE))]) -> RbacCheckOut:
    return _out(current, RoleCode.JUDGE)
