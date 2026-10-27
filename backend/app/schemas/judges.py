from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import CompetitionStatus, RequestKind, RequestStatus
from app.schemas.people import IdName, UserRef, ValidityInfo


class JudgeAssignIn(BaseModel):
    judge_id: int
    position_id: int


class CompetitionBrief(BaseModel):
    id: int
    title: str
    start_date: date
    end_date: date
    status: CompetitionStatus


class JudgeAssignmentOut(BaseModel):
    id: int
    competition: CompetitionBrief
    judge: UserRef
    position: IdName
    assigned_at: AwareDatetime


class MyAssignmentsOut(BaseModel):
    category: ValidityInfo | None
    upcoming: list[JudgeAssignmentOut]
    past: list[JudgeAssignmentOut]


class CategoryRequestIn(BaseModel):
    category_id: int
    kind: RequestKind
    comment: str | None = Field(default=None, max_length=2000)


class CategoryRequestOut(BaseModel):
    id: int
    judge: UserRef
    category: IdName
    kind: RequestKind
    status: RequestStatus
    comment: str | None
    created_at: AwareDatetime
    decided_by: int | None
    decided_at: AwareDatetime | None
    decision_comment: str | None
    order_number: str | None = None
    order_date: date | None = None
    valid_until: date | None = None


class RequestDecision(BaseModel):
    """Решение федерации по заявке на категорию или разряд."""

    status: Literal[RequestStatus.APPROVED, RequestStatus.REJECTED]
    comment: str | None = Field(default=None, max_length=2000)
    order_number: str | None = Field(default=None, max_length=100)
    order_date: date | None = None
    valid_until: date | None = Field(default=None, description="По умолчанию: дата приказа + срок категории/разряда")

    @model_validator(mode="after")
    def _rules(self) -> "RequestDecision":
        if self.status == RequestStatus.REJECTED and not (self.comment and self.comment.strip()):
            raise ValueError("При отклонении укажите причину (comment)")
        if self.status == RequestStatus.APPROVED and not (self.order_number and self.order_number.strip()):
            raise ValueError("При утверждении укажите номер приказа (order_number)")
        return self
