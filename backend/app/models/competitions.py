from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, PrimaryKeyConstraint, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import (
    ApplicationStatus,
    CalendarPlan,
    CompetitionLevel,
    CompetitionStatus,
    RatingTier,
    RoleCode,
    StageFormat,
    pg_enum,
)


class Competition(Base, CreatedAtMixin):
    __tablename__ = "competitions"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="competition_dates"),
        CheckConstraint("calendar_plan = 'none' OR plan_number IS NOT NULL", name="plan_number_required"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    discipline_id: Mapped[int] = mapped_column(fk("disciplines.id"), index=True)
    type_id: Mapped[int] = mapped_column(fk("competition_types.id"))
    level: Mapped[CompetitionLevel] = mapped_column(pg_enum(CompetitionLevel))
    rating_tier: Mapped[RatingTier] = mapped_column(pg_enum(RatingTier))
    status: Mapped[CompetitionStatus] = mapped_column(
        pg_enum(CompetitionStatus), default=CompetitionStatus.DRAFT, server_default="draft", index=True
    )
    calendar_plan: Mapped[CalendarPlan] = mapped_column(
        pg_enum(CalendarPlan), default=CalendarPlan.NONE, server_default="none"
    )
    plan_number: Mapped[str | None] = mapped_column(String(64))
    start_date: Mapped[date]
    end_date: Mapped[date]
    location: Mapped[str | None] = mapped_column(String(300))
    regulation_file_id: Mapped[int | None] = mapped_column(fk("stored_files.id"))
    registration_opens_at: Mapped[datetime | None]
    registration_deadline: Mapped[datetime | None]
    is_team: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(fk("users.id"))


class CompetitionAgeGroup(Base):
    __tablename__ = "competition_age_groups"
    __table_args__ = (PrimaryKeyConstraint("competition_id", "age_group_id", name="pk_competition_age_groups"),)

    competition_id: Mapped[int] = mapped_column(fk("competitions.id"))
    age_group_id: Mapped[int] = mapped_column(fk("age_groups.id"))


class CompetitionStage(Base, CreatedAtMixin):
    """Этап соревнования. Формат (онлайн/очно) задаётся на этапе."""

    __tablename__ = "competition_stages"
    __table_args__ = (
        UniqueConstraint("competition_id", "order_no", name="uq_competition_stages_order"),
        CheckConstraint("ends_at >= starts_at", name="stage_dates"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"), index=True)
    order_no: Mapped[int]
    name: Mapped[str]
    format: Mapped[StageFormat] = mapped_column(pg_enum(StageFormat))
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    place_or_url: Mapped[str | None] = mapped_column(String(500))


class Team(Base, CreatedAtMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"), index=True)
    name: Mapped[str]
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coach_profiles.user_id", ondelete="RESTRICT"))


class CompetitionApplication(Base, CreatedAtMixin):
    __tablename__ = "competition_applications"
    __table_args__ = (
        # у спортсмена одна живая заявка на соревнование
        Index(
            "uq_competition_applications_active",
            "competition_id",
            "athlete_id",
            unique=True,
            postgresql_where="status IN ('pending', 'approved')",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    team_id: Mapped[int | None] = mapped_column(fk("teams.id"))
    submitted_by_user_id: Mapped[int] = mapped_column(fk("users.id"))
    submitted_by_role: Mapped[RoleCode] = mapped_column(pg_enum(RoleCode))
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coach_profiles.user_id", ondelete="RESTRICT"))
    status: Mapped[ApplicationStatus] = mapped_column(
        pg_enum(ApplicationStatus), default=ApplicationStatus.PENDING, server_default="pending"
    )
    age_on_start: Mapped[int]
    moderated_by: Mapped[int | None] = mapped_column(fk("users.id"))
    moderated_at: Mapped[datetime | None]
    moderation_comment: Mapped[str | None] = mapped_column(Text)


class CompetitionJudge(Base, CreatedAtMixin):
    """Судейская коллегия соревнования (С6)."""

    __tablename__ = "competition_judges"
    __table_args__ = (UniqueConstraint("competition_id", "judge_id", name="uq_competition_judges_judge"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"), index=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judge_profiles.user_id", ondelete="RESTRICT"), index=True)
    position_id: Mapped[int] = mapped_column(fk("judge_positions.id"))
    assigned_by: Mapped[int] = mapped_column(fk("users.id"))
