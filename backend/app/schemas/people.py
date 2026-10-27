"""Общие компактные ссылки на сущности для ответов API."""

from datetime import date

from pydantic import BaseModel


class UserRef(BaseModel):
    id: int
    full_name: str


class DisciplineRef(BaseModel):
    id: int
    code: str
    name: str


class IdName(BaseModel):
    id: int
    name: str


class ValidityInfo(BaseModel):
    """Разряд или категория со сроком действия и предупреждением."""

    id: int
    name: str
    assigned_at: date | None = None
    valid_until: date | None
    days_left: int | None
    expired: bool
    warning: bool
