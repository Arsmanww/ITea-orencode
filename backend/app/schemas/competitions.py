from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import (
    CalendarPlan,
    CompetitionLevel,
    CompetitionStatus,
    RatingTier,
    StageFormat,
)

RATING_TIERS_BY_LEVEL = {
    CompetitionLevel.REGIONAL: {RatingTier.REGIONAL},
    CompetitionLevel.INTERREGIONAL: {RatingTier.INTERREGIONAL},
    CompetitionLevel.ALL_RUSSIAN: {RatingTier.RUSSIA_CHAMPIONSHIP, RatingTier.RUSSIA_FIRST},
}

# допустимые ручные переходы статуса; завершение (finished) происходит только публикацией протокола
STATUS_TRANSITIONS: dict[CompetitionStatus, set[CompetitionStatus]] = {
    CompetitionStatus.DRAFT: {CompetitionStatus.PUBLISHED, CompetitionStatus.REGISTRATION_OPEN, CompetitionStatus.CANCELLED},
    CompetitionStatus.PUBLISHED: {CompetitionStatus.DRAFT, CompetitionStatus.REGISTRATION_OPEN, CompetitionStatus.CANCELLED},
    CompetitionStatus.REGISTRATION_OPEN: {CompetitionStatus.REGISTRATION_CLOSED, CompetitionStatus.CANCELLED},
    CompetitionStatus.REGISTRATION_CLOSED: {CompetitionStatus.REGISTRATION_OPEN, CompetitionStatus.IN_PROGRESS, CompetitionStatus.CANCELLED},
    CompetitionStatus.IN_PROGRESS: {CompetitionStatus.CANCELLED},
    CompetitionStatus.FINISHED: set(),
    CompetitionStatus.CANCELLED: set(),
}
CREATE_STATUSES = {CompetitionStatus.DRAFT, CompetitionStatus.PUBLISHED, CompetitionStatus.REGISTRATION_OPEN}


def check_plan_rules(
    level: CompetitionLevel,
    tier: RatingTier,
    plan: CalendarPlan,
    plan_number: str | None,
    status: CompetitionStatus,
) -> None:
    """Правила календарных планов и рейтинга; бросает ValueError с понятным текстом."""
    if tier not in RATING_TIERS_BY_LEVEL[level]:
        allowed = ", ".join(sorted(t.value for t in RATING_TIERS_BY_LEVEL[level]))
        raise ValueError(f"rating_tier не соответствует уровню соревнования, допустимо: {allowed}")
    if plan != CalendarPlan.NONE and not (plan_number and plan_number.strip()):
        raise ValueError("Для соревнования в календарном плане обязателен номер в плане (plan_number)")
    if level == CompetitionLevel.REGIONAL and plan == CalendarPlan.EKP_MINSPORT:
        raise ValueError("Региональные соревнования включаются в календарный план Оренбургской области, а не в ЕКП Минспорта России")
    if level != CompetitionLevel.REGIONAL and plan == CalendarPlan.OREN_REGIONAL:
        raise ValueError("Всероссийские и межрегиональные соревнования включаются в ЕКП Минспорта России")
    if status != CompetitionStatus.DRAFT and plan == CalendarPlan.NONE:
        raise ValueError("Опубликовать можно только соревнование, включённое в календарный план")


class StageIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    format: StageFormat
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    place_or_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _dates(self) -> "StageIn":
        if self.ends_at < self.starts_at:
            raise ValueError("Окончание этапа раньше его начала")
        return self


class CompetitionCreate(BaseModel):
    title: str = Field(min_length=5, max_length=300)
    discipline_id: int
    type_id: int
    level: CompetitionLevel
    rating_tier: RatingTier
    status: CompetitionStatus = CompetitionStatus.DRAFT
    calendar_plan: CalendarPlan = CalendarPlan.NONE
    plan_number: str | None = Field(default=None, max_length=64)
    start_date: date
    end_date: date
    location: str | None = Field(default=None, max_length=300)
    registration_opens_at: AwareDatetime | None = None
    registration_deadline: AwareDatetime | None = None
    is_team: bool = False
    description: str | None = None
    age_group_ids: list[int] = Field(min_length=1)
    stages: list[StageIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _rules(self) -> "CompetitionCreate":
        if self.end_date < self.start_date:
            raise ValueError("Дата окончания раньше даты начала")
        if self.status not in CREATE_STATUSES:
            raise ValueError("При создании допустимы статусы draft, published, registration_open")
        if self.registration_opens_at and self.registration_deadline and self.registration_deadline < self.registration_opens_at:
            raise ValueError("Дедлайн приёма заявок раньше открытия регистрации")
        if len(set(self.age_group_ids)) != len(self.age_group_ids):
            raise ValueError("Возрастные группы повторяются")
        check_plan_rules(self.level, self.rating_tier, self.calendar_plan, self.plan_number, self.status)
        return self


class CompetitionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=300)
    type_id: int | None = None
    status: CompetitionStatus | None = None
    calendar_plan: CalendarPlan | None = None
    plan_number: str | None = Field(default=None, max_length=64)
    start_date: date | None = None
    end_date: date | None = None
    location: str | None = Field(default=None, max_length=300)
    registration_opens_at: AwareDatetime | None = None
    registration_deadline: AwareDatetime | None = None
    description: str | None = None


class DisciplineRef(BaseModel):
    id: int
    code: str
    name: str


class IdName(BaseModel):
    id: int
    name: str


class AgeGroupOut(BaseModel):
    id: int
    name: str
    min_age: int
    max_age: int


class StageOut(BaseModel):
    id: int
    order_no: int
    name: str
    format: StageFormat
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    place_or_url: str | None


class CompetitionOut(BaseModel):
    id: int
    title: str
    discipline: DisciplineRef
    type: IdName
    level: CompetitionLevel
    rating_tier: RatingTier
    status: CompetitionStatus
    calendar_plan: CalendarPlan
    plan_number: str | None
    start_date: date
    end_date: date
    location: str | None
    registration_opens_at: AwareDatetime | None
    registration_deadline: AwareDatetime | None
    is_team: bool
    description: str | None
    format: Literal["online", "offline", "mixed"]
    age_groups: list[AgeGroupOut]
    stages: list[StageOut]
    regulation_url: str | None


class CompetitionListOut(BaseModel):
    items: list[CompetitionOut]
    total: int
    limit: int
    offset: int
