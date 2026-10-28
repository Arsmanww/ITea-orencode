from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import CurrentUser, get_current_user, require_role
from app.models import Notification
from app.models.enums import RoleCode
from app.schemas.notifications import NotificationListOut, NotificationOut
from app.services.expiry import run_expiry_check

router = APIRouter(tags=["notifications"])

Session = Annotated[AsyncSession, Depends(get_session)]
Authed = Annotated[CurrentUser, Depends(get_current_user)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]


class ExpiryCheckOut(BaseModel):
    created: int


@router.get("/notifications", response_model=NotificationListOut, summary="Мои уведомления в личном кабинете")
async def list_notifications(
    session: Session,
    current: Authed,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> NotificationListOut:
    stmt = select(Notification).where(Notification.user_id == current.user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    items = (await session.scalars(stmt.order_by(Notification.id.desc()).limit(limit))).all()
    unread = await session.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == current.user.id, Notification.read_at.is_(None))
    )
    return NotificationListOut(
        unread=unread or 0,
        items=[NotificationOut(id=n.id, kind=n.kind, title=n.title, body=n.body, entity_type=n.entity_type,
                               entity_id=n.entity_id, created_at=n.created_at, read_at=n.read_at) for n in items],
    )


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, summary="Отметить уведомление прочитанным")
async def mark_read(notification_id: int, session: Session, current: Authed) -> None:
    n = await session.get(Notification, notification_id)
    if n is None or n.user_id != current.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Уведомление не найдено")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await session.commit()


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT, summary="Отметить все прочитанными")
async def mark_all_read(session: Session, current: Authed) -> None:
    await session.execute(
        update(Notification).where(Notification.user_id == current.user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await session.commit()


@router.post("/federation/expiry-check", response_model=ExpiryCheckOut,
             summary="Запустить проверку сроков сейчас: разряды, категории, приём заявок, премии Губернатора (иначе – каждый час)")
async def expiry_check(session: Session, current: FederationOnly) -> ExpiryCheckOut:
    return ExpiryCheckOut(created=await run_expiry_check(session, date.today()))
