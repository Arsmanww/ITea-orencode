from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import RequestKind, RequestStatus, RoleCode, pg_enum


class RankRequest(Base, CreatedAtMixin):
    """Заявка на разряд (С7). Основание – результат из протокола."""

    __tablename__ = "rank_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    rank_id: Mapped[int] = mapped_column(fk("ranks.id"))
    discipline_id: Mapped[int] = mapped_column(fk("disciplines.id"))
    kind: Mapped[RequestKind] = mapped_column(pg_enum(RequestKind))
    competition_id: Mapped[int] = mapped_column(fk("competitions.id"))
    result_id: Mapped[int] = mapped_column(fk("results.id"))
    submitted_by_user_id: Mapped[int] = mapped_column(fk("users.id"))
    submitted_by_role: Mapped[RoleCode] = mapped_column(pg_enum(RoleCode))
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coach_profiles.user_id", ondelete="RESTRICT"))
    status: Mapped[RequestStatus] = mapped_column(
        pg_enum(RequestStatus), default=RequestStatus.SUBMITTED, server_default="submitted", index=True
    )
    decided_by: Mapped[int | None] = mapped_column(fk("users.id"))
    decided_at: Mapped[datetime | None]
    decision_comment: Mapped[str | None] = mapped_column(Text)


class RankAssignment(Base, CreatedAtMixin):
    __tablename__ = "rank_assignments"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_rank_assignments_request"),
        CheckConstraint("valid_until IS NULL OR valid_until > assigned_at", name="rank_validity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"), index=True)
    rank_id: Mapped[int] = mapped_column(fk("ranks.id"))
    discipline_id: Mapped[int] = mapped_column(fk("disciplines.id"))
    assigned_at: Mapped[date]
    valid_until: Mapped[date | None] = mapped_column(index=True)
    order_number: Mapped[str]
    order_date: Mapped[date]
    request_id: Mapped[int | None] = mapped_column(fk("rank_requests.id"))


class JudgeCategoryRequest(Base, CreatedAtMixin):
    __tablename__ = "judge_category_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judge_profiles.user_id", ondelete="RESTRICT"), index=True)
    category_id: Mapped[int] = mapped_column(fk("judge_categories.id"))
    kind: Mapped[RequestKind] = mapped_column(pg_enum(RequestKind))
    status: Mapped[RequestStatus] = mapped_column(
        pg_enum(RequestStatus), default=RequestStatus.SUBMITTED, server_default="submitted", index=True
    )
    comment: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(fk("users.id"))
    decided_at: Mapped[datetime | None]
    decision_comment: Mapped[str | None] = mapped_column(Text)


class JudgeCategoryAssignment(Base, CreatedAtMixin):
    __tablename__ = "judge_category_assignments"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_judge_category_assignments_request"),
        CheckConstraint("valid_until IS NULL OR valid_until > assigned_at", name="category_validity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("judge_profiles.user_id", ondelete="RESTRICT"), index=True)
    category_id: Mapped[int] = mapped_column(fk("judge_categories.id"))
    assigned_at: Mapped[date]
    valid_until: Mapped[date | None] = mapped_column(index=True)
    order_number: Mapped[str]
    order_date: Mapped[date]
    request_id: Mapped[int | None] = mapped_column(fk("judge_category_requests.id"))
