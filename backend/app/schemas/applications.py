from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import ApplicationStatus, RoleCode


class ApplicationCreate(BaseModel):
    athlete_id: int | None = Field(default=None, description="Обязателен для тренера; спортсмен подаёт за себя")
    team_name: str | None = Field(default=None, max_length=255, description="Обязательно для командных соревнований")


class ApplicationModerate(BaseModel):
    status: Literal[ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _comment(self) -> "ApplicationModerate":
        if self.status == ApplicationStatus.REJECTED and not (self.comment and self.comment.strip()):
            raise ValueError("При отклонении заявки укажите причину (comment)")
        return self


class AthleteRef(BaseModel):
    id: int
    full_name: str
    birth_date: date


class TeamRef(BaseModel):
    id: int
    name: str


class ApplicationOut(BaseModel):
    id: int
    competition_id: int
    athlete: AthleteRef
    team: TeamRef | None
    status: ApplicationStatus
    age_on_start: int
    submitted_by_user_id: int
    submitted_by_role: RoleCode
    coach_id: int | None
    moderated_by: int | None
    moderated_at: AwareDatetime | None
    moderation_comment: str | None
    created_at: AwareDatetime
