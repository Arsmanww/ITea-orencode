from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.models.enums import RoleCode


async def log_action(
    session: AsyncSession,
    request: Request,
    *,
    user_id: int | None,
    active_role: RoleCode | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    diff: dict[str, Any] | None = None,
) -> None:
    """Запись в журнал действий: кто, когда, что сделал. Коммит делает вызывающий код."""
    session.add(
        AuditLog(
            user_id=user_id,
            active_role=active_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff=diff,
            ip=request.client.host if request.client else None,
        )
    )
