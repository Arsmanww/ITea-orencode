import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import Channel, DeliveryStatus, NotificationKind, RoleCode, pg_enum


class Notification(Base, CreatedAtMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(fk("users.id"), index=True)
    kind: Mapped[NotificationKind] = mapped_column(pg_enum(NotificationKind))
    title: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None]
    read_at: Mapped[datetime | None]
    dedup_key: Mapped[str | None] = mapped_column(unique=True)


class NotificationDelivery(Base, CreatedAtMixin):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("notification_id", "channel", name="uq_notification_deliveries_channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(fk("notifications.id"), index=True)
    channel: Mapped[Channel] = mapped_column(pg_enum(Channel))
    status: Mapped[DeliveryStatus] = mapped_column(
        pg_enum(DeliveryStatus), default=DeliveryStatus.PENDING, server_default="pending"
    )
    sent_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base, CreatedAtMixin):
    """Журнал действий: кто, когда, что сделал."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(fk("users.id"), index=True)
    active_role: Mapped[RoleCode | None] = mapped_column(pg_enum(RoleCode))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None]
    diff: Mapped[dict[str, Any] | None]
    ip: Mapped[str | None] = mapped_column(String(64))


class ParticipationCertificate(Base, CreatedAtMixin):
    """Справка об участии с QR (Д10); подлинность проверяется по verify_token."""

    __tablename__ = "participation_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(unique=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    result_id: Mapped[int] = mapped_column(fk("results.id"))
    verify_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    snapshot: Mapped[dict[str, Any]]
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked: Mapped[bool] = mapped_column(default=False, server_default=text("false"))


class PasswordResetToken(Base, CreatedAtMixin):
    """Запрос на сброс пароля («Забыли пароль?»).

    Хранится хеш токена (sha256), а не сам токен: утечка БД не даёт захватить аккаунт по этой
    таблице. Токен одноразовый – used_at проставляется при успешном сбросе; новый запрос
    на тот же email не удаляет прежние строки, они просто перестают быть actionable по сроку.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(fk("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class ContentPage(Base, CreatedAtMixin):
    """Контент публичного навигатора новичка (Д11)."""

    __tablename__ = "content_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    body_md: Mapped[str] = mapped_column(Text)
    order_no: Mapped[int] = mapped_column(default=0, server_default="0")
    discipline_id: Mapped[int | None] = mapped_column(fk("disciplines.id"))
    is_published: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
