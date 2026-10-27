from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import ProtocolStatus, ResultStatus, SanctionKind, pg_enum


class Result(Base, CreatedAtMixin):
    """Результат участника. Создаётся только для одобренной заявки (проверка в сервисе)."""

    __tablename__ = "results"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_results_application"),
        UniqueConstraint("competition_id", "athlete_id", name="uq_results_competition_athlete"),
        CheckConstraint("place IS NULL OR place >= 1", name="place_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"), index=True)
    application_id: Mapped[int] = mapped_column(fk("competition_applications.id"))
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    place: Mapped[int | None]
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    tasks_solved: Mapped[int | None]
    details: Mapped[dict[str, Any] | None]
    status: Mapped[ResultStatus] = mapped_column(
        pg_enum(ResultStatus), default=ResultStatus.RANKED, server_default="ranked"
    )
    note: Mapped[str | None] = mapped_column(Text)


class Protocol(Base, CreatedAtMixin):
    """Протокол: JSONB-снимок строк, не меняется задним числом."""

    __tablename__ = "protocols"
    __table_args__ = (UniqueConstraint("competition_id", "version", name="uq_protocols_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"), index=True)
    number: Mapped[str]
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    status: Mapped[ProtocolStatus] = mapped_column(
        pg_enum(ProtocolStatus), default=ProtocolStatus.DRAFT, server_default="draft"
    )
    generated_by: Mapped[int] = mapped_column(fk("users.id"))
    generated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None]
    snapshot: Mapped[dict[str, Any]]


class Sanction(Base, CreatedAtMixin):
    """Дисквалификация или отстранение: исключает из рейтинга на время действия."""

    __tablename__ = "sanctions"
    __table_args__ = (CheckConstraint("date_to IS NULL OR date_to >= date_from", name="sanction_dates"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    kind: Mapped[SanctionKind] = mapped_column(pg_enum(SanctionKind))
    date_from: Mapped[date]
    date_to: Mapped[date | None]
    reason: Mapped[str] = mapped_column(Text)
    competition_id: Mapped[int | None] = mapped_column(fk("competitions.id"))
