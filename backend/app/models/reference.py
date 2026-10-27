from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import CompetitionLevel, OrgType, RatingTier, pg_enum


class Municipality(Base, CreatedAtMixin):
    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class Organization(Base, CreatedAtMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    type: Mapped[OrgType] = mapped_column(pg_enum(OrgType))
    municipality_id: Mapped[int] = mapped_column(fk("municipalities.id"), index=True)
    address: Mapped[str | None]


class Discipline(Base, CreatedAtMixin):
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str]


class AgeGroup(Base, CreatedAtMixin):
    __tablename__ = "age_groups"
    __table_args__ = (CheckConstraint("max_age >= min_age", name="age_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    min_age: Mapped[int]
    max_age: Mapped[int]
    discipline_id: Mapped[int | None] = mapped_column(fk("disciplines.id"))


class CompetitionType(Base, CreatedAtMixin):
    __tablename__ = "competition_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class Rank(Base, CreatedAtMixin):
    __tablename__ = "ranks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str]
    order_no: Mapped[int] = mapped_column(unique=True)
    validity_months: Mapped[int | None]


class JudgeCategory(Base, CreatedAtMixin):
    __tablename__ = "judge_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str]
    order_no: Mapped[int] = mapped_column(unique=True)
    validity_months: Mapped[int | None]


class JudgePosition(Base, CreatedAtMixin):
    __tablename__ = "judge_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)


class RankRequirement(Base, CreatedAtMixin):
    """Подсказки ЕВСК: какой результат может давать право на разряд."""

    __tablename__ = "rank_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    rank_id: Mapped[int] = mapped_column(fk("ranks.id"), index=True)
    level: Mapped[CompetitionLevel] = mapped_column(pg_enum(CompetitionLevel))
    max_place: Mapped[int]
    min_participants: Mapped[int | None]
    discipline_id: Mapped[int | None] = mapped_column(fk("disciplines.id"))


class Season(Base, CreatedAtMixin):
    __tablename__ = "seasons"
    __table_args__ = (CheckConstraint("date_to >= date_from", name="season_dates"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    date_from: Mapped[date]
    date_to: Mapped[date]


class RatingRule(Base, CreatedAtMixin):
    __tablename__ = "rating_rules"
    __table_args__ = (
        UniqueConstraint("tier", "place", name="uq_rating_rules_tier_place"),
        CheckConstraint("place >= 1", name="place_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tier: Mapped[RatingTier] = mapped_column(pg_enum(RatingTier))
    place: Mapped[int]
    points: Mapped[int]


class RatingSettings(Base, CreatedAtMixin):
    """Одна строка: коэффициент стабильности и порог числа призовых мест."""

    __tablename__ = "rating_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    stability_coef: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), default=Decimal("1.20"), server_default=text("1.20")
    )
    stability_min_prizes: Mapped[int] = mapped_column(default=2, server_default=text("2"))
