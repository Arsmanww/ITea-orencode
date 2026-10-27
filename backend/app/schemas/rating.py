from datetime import date
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import RatingTier, SquadStatus
from app.schemas.people import DisciplineRef, IdName


class BreakdownItem(BaseModel):
    competition_id: int
    title: str
    date: date
    tier: RatingTier
    place: int | None
    points: int = Field(description="Базовые очки за место по таблице уровня соревнования")


class RatingItem(BaseModel):
    place: int
    athlete_id: int
    athlete_name: str
    birth_date: date
    age: int
    organization: str | None
    rank: str | None = Field(description="Действующий разряд по дисциплине")
    base_points: int
    prizes: int = Field(description="Число призовых мест (1–3) за сезон")
    coefficient: Decimal = Field(description="Коэффициент стабильности: 1 или заданный в настройках")
    total: Decimal
    breakdown: list[BreakdownItem]


class ExcludedItem(BaseModel):
    athlete_id: int
    athlete_name: str
    reason: str


class RatingTable(BaseModel):
    discipline: DisciplineRef
    total_athletes: int
    items: list[RatingItem]
    excluded: list[ExcludedItem]


class RuleOut(BaseModel):
    tier: RatingTier
    place: int
    points: int


class SettingsOut(BaseModel):
    stability_coef: Decimal
    stability_min_prizes: int
    rules: list[RuleOut]


class SeasonOut(BaseModel):
    id: int
    name: str
    date_from: date
    date_to: date


class RatingOut(BaseModel):
    season: SeasonOut
    as_of: date = Field(description="Дата, на которую проверяются санкции, возраст и разряд")
    age_group: IdName | None
    min_rank: IdName | None
    settings: SettingsOut
    tables: list[RatingTable]


class SettingsUpdate(BaseModel):
    stability_coef: Decimal | None = Field(default=None, ge=1, le=3, max_digits=3, decimal_places=2)
    stability_min_prizes: int | None = Field(default=None, ge=1, le=20)
    rules: list[RuleOut] | None = None

    @model_validator(mode="after")
    def _unique_rules(self) -> "SettingsUpdate":
        if self.rules:
            keys = [(r.tier, r.place) for r in self.rules]
            if len(set(keys)) != len(keys):
                raise ValueError("В таблице баллов повторяются пары (tier, place)")
            if any(r.place < 1 or r.points < 0 for r in self.rules):
                raise ValueError("Место должно быть ≥ 1, баллы ≥ 0")
        return self


class SquadMemberIn(BaseModel):
    athlete_id: int
    note: str | None = Field(default=None, max_length=255)


class SquadCreate(BaseModel):
    season_id: int
    discipline_id: int
    age_group_id: int | None = None
    title: str = Field(min_length=3, max_length=255)
    members: list[SquadMemberIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _unique(self) -> "SquadCreate":
        ids = [m.athlete_id for m in self.members]
        if len(set(ids)) != len(ids):
            raise ValueError("Спортсмен указан в составе несколько раз")
        return self


class SquadApprove(BaseModel):
    order_number: str = Field(min_length=1, max_length=100)


class SquadMemberOut(BaseModel):
    position: int
    athlete_id: int
    athlete_name: str
    birth_date: date
    rating_points: Decimal
    organization: str | None
    rank: str | None
    coach: str | None
    note: str | None


class SquadOut(BaseModel):
    id: int
    title: str
    season: SeasonOut
    discipline: DisciplineRef
    age_group: IdName | None
    status: SquadStatus
    order_number: str | None
    created_at: AwareDatetime
    members: list[SquadMemberOut]
