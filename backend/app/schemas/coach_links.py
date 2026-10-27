from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from app.models.enums import LinkStatus
from app.schemas.people import DisciplineRef, UserRef, ValidityInfo


class LinkRequestIn(BaseModel):
    athlete_id: int | None = None
    athlete_email: str | None = Field(default=None, max_length=255)
    discipline_id: int

    @model_validator(mode="after")
    def _one_of(self) -> "LinkRequestIn":
        if (self.athlete_id is None) == (not self.athlete_email):
            raise ValueError("Укажите ровно одно из полей: athlete_id или athlete_email")
        return self


class CoachRequestAnswer(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CoachRequestDecision(BaseModel):
    status: CoachRequestAnswer
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("status", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        return v.lower() if isinstance(v, str) else v


class LinkOut(BaseModel):
    id: int
    status: LinkStatus
    coach: UserRef
    athlete: UserRef
    discipline: DisciplineRef
    requested_at: AwareDatetime
    confirmed_at: AwareDatetime | None
    ended_at: AwareDatetime | None


class CoachAthleteOut(BaseModel):
    link_id: int
    athlete: UserRef
    birth_date: date
    age: int
    discipline: DisciplineRef
    status: LinkStatus
    since: AwareDatetime | None
    rank: ValidityInfo | None


class LinkStatusChange(BaseModel):
    """Смена статуса связи: приостановить, возобновить или завершить."""

    status: LinkStatus = Field(description="suspended, active или ended")
    comment: str | None = Field(default=None, max_length=1000)


class LinkHistoryOut(BaseModel):
    old_status: LinkStatus | None
    new_status: LinkStatus
    changed_by: UserRef
    changed_at: AwareDatetime
    comment: str | None
