from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Notification, NotificationDelivery, Role, User, UserRole
from app.models.enums import Channel, DeliveryStatus, NotificationKind, RoleCode


async def notify(
    session: AsyncSession,
    user_id: int,
    kind: NotificationKind,
    title: str,
    body: str,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    dedup_key: str | None = None,
    external: bool = True,
) -> bool:
    """Создаёт уведомление в личном кабинете и ставит его в очередь отправки на почту, если канал включён.

    С dedup_key повторно не создаётся. external=False оставляет уведомление только в кабинете.
    Возвращает True, если создано."""
    if dedup_key and await session.scalar(select(Notification.id).where(Notification.dedup_key == dedup_key)):
        return False
    notification = Notification(user_id=user_id, kind=kind, title=title, body=body, entity_type=entity_type,
                                entity_id=entity_id, dedup_key=dedup_key)
    session.add(notification)
    await session.flush()
    session.add(NotificationDelivery(notification_id=notification.id, channel=Channel.IN_APP,
                                     status=DeliveryStatus.SENT, sent_at=datetime.now(timezone.utc)))
    if external:
        user = await session.get(User, user_id)
        if settings.smtp_host and user is not None and user.email_notifications_enabled:
            session.add(NotificationDelivery(notification_id=notification.id, channel=Channel.EMAIL, status=DeliveryStatus.PENDING))
    return True


async def dispatch_channel(
    session: AsyncSession,
    channel: Channel,
    address: Callable[[User], str | None],
    send: Callable[[str, str], Awaitable[tuple[bool, str | None]]],
    batch_size: int = 50,
) -> int:
    """Отправляет очередь одного внешнего канала: pending → sent / failed с текстом ошибки.

    address достаёт адрес получателя из пользователя (chat_id, user_id), send отправляет текст.
    Строки блокируются SKIP LOCKED, поэтому параллельные обработчики не отправят одно и то же дважды."""
    rows = (await session.execute(
        select(NotificationDelivery, Notification, User)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .join(User, User.id == Notification.user_id)
        .where(NotificationDelivery.channel == channel, NotificationDelivery.status == DeliveryStatus.PENDING)
        .order_by(NotificationDelivery.id).limit(batch_size)
        .with_for_update(skip_locked=True, of=NotificationDelivery)
    )).all()
    for delivery, notification, user in rows:
        target = address(user)
        if not target:
            ok, error = False, "Канал у пользователя отвязан"
        else:
            ok, error = await send(target, f"{notification.title}\n\n{notification.body}")
        delivery.status = DeliveryStatus.SENT if ok else DeliveryStatus.FAILED
        delivery.sent_at = datetime.now(timezone.utc) if ok else None
        delivery.error = error
    await session.commit()
    return len(rows)


async def federation_user_ids(session: AsyncSession) -> list[int]:
    rows = await session.scalars(
        select(User.id).join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id)
        .where(Role.code == RoleCode.FEDERATION, User.is_active.is_(True))
    )
    return list(rows.all())
