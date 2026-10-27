from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import SquadStatus, pg_enum


class Squad(Base, CreatedAtMixin):
    """Сборная региона (С9). Рейтинг считается налету, здесь хранится утверждённый состав."""

    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(fk("seasons.id"), index=True)
    discipline_id: Mapped[int] = mapped_column(fk("disciplines.id"))
    age_group_id: Mapped[int | None] = mapped_column(fk("age_groups.id"))
    title: Mapped[str]
    status: Mapped[SquadStatus] = mapped_column(
        pg_enum(SquadStatus), default=SquadStatus.DRAFT, server_default="draft"
    )
    order_number: Mapped[str | None]
    created_by: Mapped[int] = mapped_column(fk("users.id"))


class SquadMember(Base, CreatedAtMixin):
    __tablename__ = "squad_members"
    __table_args__ = (UniqueConstraint("squad_id", "athlete_id", name="uq_squad_members_athlete"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    squad_id: Mapped[int] = mapped_column(fk("squads.id"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"))
    position: Mapped[int]
    rating_points: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    note: Mapped[str | None]
