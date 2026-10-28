from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import CompetitionLevel, ProtocolStatus, RatingTier, RequestKind, ResultStatus


class ResultIn(BaseModel):
    application_id: int
    status: ResultStatus = ResultStatus.RANKED
    score: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    time_seconds: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=3)
    tasks_solved: int | None = Field(default=None, ge=0)
    details: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _metrics(self) -> "ResultIn":
        if self.status == ResultStatus.RANKED and self.score is None and self.tasks_solved is None and self.time_seconds is None:
            raise ValueError("Для участника в зачёте укажите хотя бы один показатель: score, tasks_solved или time_seconds")
        return self


class ResultsIn(BaseModel):
    results: list[ResultIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "ResultsIn":
        ids = [r.application_id for r in self.results]
        if len(set(ids)) != len(ids):
            raise ValueError("Результаты для одной заявки переданы несколько раз")
        return self


class ResultOut(BaseModel):
    id: int
    application_id: int
    athlete_id: int
    athlete_name: str
    place: int | None
    status: ResultStatus
    score: Decimal | None
    time_seconds: Decimal | None
    tasks_solved: int | None
    details: dict[str, Any] | None
    note: str | None


class EvskCandidate(BaseModel):
    """Участник, чей результат в протоколе может соответствовать требованиям ЕВСК."""

    athlete_id: int
    full_name: str
    place: int
    rank_id: int
    rank: str
    current_rank: str | None
    kind: RequestKind
    request_pending: bool


class ProtocolOut(BaseModel):
    id: int
    competition_id: int
    number: str
    version: int
    status: ProtocolStatus
    published_at: AwareDatetime | None
    snapshot: dict[str, Any]
    evsk: list[EvskCandidate] = Field(default_factory=list, description="Подсветка ЕВСК – только для федерации")


class HistoryItem(BaseModel):
    result_id: int
    competition_id: int
    competition_title: str
    discipline: str
    level: CompetitionLevel
    rating_tier: RatingTier
    start_date: date
    end_date: date
    place: int | None
    status: ResultStatus
    score: Decimal | None
    time_seconds: Decimal | None
    tasks_solved: int | None
    participants: int
    protocol_id: int
    protocol_number: str


class HistoryOut(BaseModel):
    athlete_id: int
    athlete_name: str
    total: int
    prizes: int
    items: list[HistoryItem]
