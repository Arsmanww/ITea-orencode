from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services import max_bot

router = APIRouter(prefix="/me", tags=["profile"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]


class NotificationSettings(BaseModel):
    in_app: bool = True
    email: str
    max_bot_configured: bool
    max_bot_username: str | None
    max_bound: bool


class MaxLinkOut(BaseModel):
    code: str = Field(description="Одноразовый код; его можно отправить боту сообщением")
    link: str | None = Field(description="Ссылка https://max.ru/<бот>?start=<код>: открыть и нажать «Начать»")
    expires_at: datetime


def _settings_out(current: CurrentUser) -> NotificationSettings:
    return NotificationSettings(
        email=current.user.email, max_bot_configured=max_bot.max_enabled(), max_bot_username=settings.max_bot_username or None,
        max_bound=bool(current.user.max_user_id),
    )


@router.get("/notification-settings", response_model=NotificationSettings, summary="Каналы уведомлений пользователя")
async def notification_settings(current: Authed) -> NotificationSettings:
    return _settings_out(current)


@router.post("/max/link", response_model=MaxLinkOut,
             summary="Получить одноразовую ссылку привязки MAX (действует 15 минут)")
async def max_link(request: Request, session: Session, current: Authed) -> MaxLinkOut:
    if not max_bot.max_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Бот MAX на платформе не настроен")
    code, expires_at = max_bot.new_link_code()
    current.user.max_link_code, current.user.max_link_expires_at = code, expires_at
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="profile.max_link_issued", entity_type="user", entity_id=current.user.id)
    await session.commit()
    return MaxLinkOut(code=code, link=max_bot.deep_link(code), expires_at=expires_at)


@router.delete("/max", response_model=NotificationSettings, summary="Отвязать MAX")
async def unbind_max(request: Request, session: Session, current: Authed) -> NotificationSettings:
    current.user.max_user_id = current.user.max_link_code = current.user.max_link_expires_at = None
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="profile.max_unbind", entity_type="user", entity_id=current.user.id)
    await session.commit()
    return _settings_out(current)
