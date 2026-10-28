from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


def pg_enum(cls: type[StrEnum]) -> ENUM:
    """Нативный enum PostgreSQL. Типы создаются в миграции явно (create_type=False)."""
    return ENUM(
        cls,
        name=cls.__name__.lower(),
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )


class RoleCode(StrEnum):
    FEDERATION = "federation"
    ATHLETE = "athlete"
    COACH = "coach"
    JUDGE = "judge"
    MINISTRY = "ministry"  # зарезервировано под Д9


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class OrgType(StrEnum):
    SCHOOL = "school"
    UNIVERSITY = "university"
    SPORTS_SCHOOL = "sports_school"
    CLUB = "club"
    OTHER = "other"


class CompetitionLevel(StrEnum):
    REGIONAL = "regional"
    INTERREGIONAL = "interregional"
    ALL_RUSSIAN = "all_russian"


class RatingTier(StrEnum):
    """Строка таблицы баллов рейтинга (4 уровня из кейса)."""

    RUSSIA_CHAMPIONSHIP = "russia_championship"
    RUSSIA_FIRST = "russia_first"
    INTERREGIONAL = "interregional"
    REGIONAL = "regional"


class CalendarPlan(StrEnum):
    NONE = "none"
    EKP_MINSPORT = "ekp_minsport"
    OREN_REGIONAL = "oren_regional"


class CompetitionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class StageFormat(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class LinkStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"


class RequestKind(StrEnum):
    """Присвоение или подтверждение (для разрядов и судейских категорий)."""

    ASSIGN = "assign"
    CONFIRM = "confirm"


class RequestStatus(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResultStatus(StrEnum):
    RANKED = "ranked"
    DISQUALIFIED = "disqualified"
    DID_NOT_START = "did_not_start"


class ProtocolStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class SquadStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class TrainingStage(StrEnum):
    INITIAL = "initial"
    TRAINING = "training"
    IMPROVEMENT = "improvement"
    HIGHER_MASTERY = "higher_mastery"


class SanctionKind(StrEnum):
    DISQUALIFICATION = "disqualification"
    SUSPENSION = "suspension"


class NotificationKind(StrEnum):
    REGISTRATION_OPEN = "registration_open"
    APPLICATION_STATUS = "application_status"
    PROTOCOL_PUBLISHED = "protocol_published"
    RANK_REQUEST = "rank_request"
    JUDGE_REQUEST = "judge_request"
    DEADLINE_SOON = "deadline_soon"
    RANK_EXPIRING = "rank_expiring"
    CATEGORY_EXPIRING = "category_expiring"
    LINK_REQUEST = "link_request"
    SANCTION = "sanction"


class Channel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
