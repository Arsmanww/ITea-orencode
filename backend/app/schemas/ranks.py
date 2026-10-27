from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.models.enums import RequestKind, RequestStatus, RoleCode
from app.schemas.people import DisciplineRef, IdName, UserRef, ValidityInfo


class RankRequestIn(BaseModel):
    athlete_id: int | None = Field(default=None, description="Обязателен для тренера; спортсмен подаёт за себя")
    rank_id: int
    kind: RequestKind
    competition_id: int
    result_id: int


class ResultBrief(BaseModel):
    id: int
    place: int | None
    score: Decimal | None


class RankRequestOut(BaseModel):
    id: int
    athlete: UserRef
    rank: IdName
    discipline: DisciplineRef
    kind: RequestKind
    competition: IdName
    result: ResultBrief
    submitted_by_user_id: int
    submitted_by_role: RoleCode
    coach_id: int | None
    status: RequestStatus
    evsk_match: bool | None = Field(description="Подсказка: результат может соответствовать требованиям ЕВСК")
    created_at: AwareDatetime
    decided_by: int | None
    decided_at: AwareDatetime | None
    decision_comment: str | None
    order_number: str | None = None
    order_date: date | None = None
    valid_until: date | None = None


class ExpiringItem(BaseModel):
    kind: Literal["rank", "judge_category"]
    assignment_id: int
    subject_id: int
    subject_name: str
    title: str
    discipline: str | None
    valid_until: date
    days_left: int
    expired: bool


class ExpiringOut(BaseModel):
    days: int
    total: int
    items: list[ExpiringItem]


class MyRankOut(BaseModel):
    discipline: DisciplineRef
    rank: ValidityInfo
    pending_request: bool
