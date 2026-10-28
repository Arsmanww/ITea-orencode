from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Index, PrimaryKeyConstraint, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, fk
from app.models.enums import Gender, RoleCode, TrainingStage, pg_enum


class User(Base, CreatedAtMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    last_name: Mapped[str]
    first_name: Mapped[str]
    patronymic: Mapped[str | None]
    birth_date: Mapped[date]
    gender: Mapped[Gender] = mapped_column(pg_enum(Gender))
    phone: Mapped[str | None] = mapped_column(String(32))
    municipality_id: Mapped[int | None] = mapped_column(fk("municipalities.id"), index=True)
    # внешний канал уведомлений – почта из этого же поля email; пользователь может его выключить
    email_notifications_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))


class Role(Base, CreatedAtMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[RoleCode] = mapped_column(pg_enum(RoleCode), unique=True)
    name: Mapped[str]


class UserRole(Base, CreatedAtMixin):
    """Роли аккаунта. Активная роль живёт в JWT и здесь не хранится."""

    __tablename__ = "user_roles"
    __table_args__ = (PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),)

    user_id: Mapped[int] = mapped_column(fk("users.id"))
    role_id: Mapped[int] = mapped_column(fk("roles.id"))


class AthleteProfile(Base, CreatedAtMixin):
    __tablename__ = "athlete_profiles"

    user_id: Mapped[int] = mapped_column(fk("users.id"), primary_key=True)
    guardian_name: Mapped[str | None]
    guardian_phone: Mapped[str | None] = mapped_column(String(32))
    guardian_email: Mapped[str | None]
    antidoping_course_date: Mapped[date | None]
    antidoping_cert_url: Mapped[str | None] = mapped_column(String(500))


class CoachProfile(Base, CreatedAtMixin):
    __tablename__ = "coach_profiles"

    user_id: Mapped[int] = mapped_column(fk("users.id"), primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(fk("organizations.id"), index=True)
    bio: Mapped[str | None] = mapped_column(Text)


class JudgeProfile(Base, CreatedAtMixin):
    __tablename__ = "judge_profiles"

    user_id: Mapped[int] = mapped_column(fk("users.id"), primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(fk("organizations.id"), index=True)


class StoredFile(Base, CreatedAtMixin):
    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str]
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int]
    uploaded_by: Mapped[int | None] = mapped_column(fk("users.id"))


class Consent(Base, CreatedAtMixin):
    """Согласие на обработку ПДн (скан подписанного документа)."""

    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(fk("users.id"), index=True)
    signed_by_name: Mapped[str]
    is_guardian: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    file_id: Mapped[int | None] = mapped_column(fk("stored_files.id"))


class AthleteEnrollment(Base, CreatedAtMixin):
    """Занятия спортсмена по дисциплине в организации. Основа реестра и отчёта С8."""

    __tablename__ = "athlete_enrollments"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="enrollment_dates"),
        Index("ix_athlete_enrollments_athlete_discipline", "athlete_id", "discipline_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athlete_profiles.user_id", ondelete="RESTRICT"))
    discipline_id: Mapped[int] = mapped_column(fk("disciplines.id"))
    organization_id: Mapped[int | None] = mapped_column(fk("organizations.id"), index=True)
    training_stage: Mapped[TrainingStage | None] = mapped_column(pg_enum(TrainingStage))
    start_date: Mapped[date]
    end_date: Mapped[date | None]
