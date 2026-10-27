from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import LinkStatus, pg_enum


class CoachAthleteLink(Base, CreatedAtMixin):
    __tablename__ = "coach_athlete_links"
    __table_args__ = (
        # одна живая связь на тренера, спортсмена и дисциплину
        Index(
            "uq_coach_athlete_links_open",
            "coach_id",
            "athlete_id",
            "discipline_id",
            unique=True,
            postgresql_where="status IN ('pending', 'active', 'suspended')",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coach_profiles.user_id", ondelete="RESTRICT"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    discipline_id: Mapped[int] = mapped_column(fk("disciplines.id"))
    status: Mapped[LinkStatus] = mapped_column(pg_enum(LinkStatus), default=LinkStatus.PENDING, server_default="pending")
    initiated_by_user_id: Mapped[int] = mapped_column(fk("users.id"))
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now())
    confirmed_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]


class CoachLinkHistory(Base, CreatedAtMixin):
    __tablename__ = "coach_link_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(fk("coach_athlete_links.id"), index=True)
    old_status: Mapped[LinkStatus | None] = mapped_column(pg_enum(LinkStatus))
    new_status: Mapped[LinkStatus] = mapped_column(pg_enum(LinkStatus))
    changed_by: Mapped[int] = mapped_column(fk("users.id"))
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    comment: Mapped[str | None] = mapped_column(Text)
