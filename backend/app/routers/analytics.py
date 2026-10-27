from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.database import get_session
from app.core.deps import CurrentUser, require_role
from app.models.enums import RoleCode
from app.reports.headcount_xlsx import build_headcount_xlsx
from app.services.files import attachment
from app.services.headcount import build_headcount

router = APIRouter(prefix="/analytics", tags=["analytics"])

Session = Annotated[AsyncSession, Depends(get_session)]
FederationOnly = Annotated[CurrentUser, Depends(require_role(RoleCode.FEDERATION))]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class HeadcountRow(BaseModel):
    label: str
    extra: str = ""
    counts: dict[int, int]


class HeadcountOut(BaseModel):
    years: list[int]
    total: dict[int, int]
    new: dict[int, int]
    coaches: dict[int, int]
    judges: dict[int, int]
    municipalities: list[HeadcountRow]
    organizations: list[HeadcountRow]
    disciplines: list[HeadcountRow]
    age_groups: list[HeadcountRow]


def _years(year_from: int | None, year_to: int | None) -> tuple[int, int]:
    year_to = year_to or date.today().year
    year_from = year_from or year_to - 2
    if year_to - year_from < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Динамика строится минимум за два года: year_to должен быть больше year_from")
    if year_to - year_from > 10:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Период не может быть длиннее 11 лет")
    return year_from, year_to


YearFrom = Annotated[int | None, Query(ge=2000, le=2100, description="По умолчанию: текущий год − 2")]
YearTo = Annotated[int | None, Query(ge=2000, le=2100, description="По умолчанию: текущий год")]


@router.get("/headcount", response_model=HeadcountOut, summary="Динамика численности занимающихся (данные для дашборда)")
async def headcount(session: Session, current: FederationOnly, year_from: YearFrom = None, year_to: YearTo = None) -> HeadcountOut:
    y1, y2 = _years(year_from, year_to)
    r = await build_headcount(session, y1, y2)
    rows = lambda items: [HeadcountRow(label=i.label, extra=i.extra, counts=i.counts) for i in items]  # noqa: E731
    return HeadcountOut(years=r.years, total=r.total, new=r.new, coaches=r.coaches, judges=r.judges, municipalities=rows(r.municipalities),
                        organizations=rows(r.organizations), disciplines=rows(r.disciplines), age_groups=rows(r.age_groups))


@router.get("/headcount/export", summary="Отчёт «Численность занимающихся» в формате .xlsx (динамика по годам)")
async def headcount_export(request: Request, session: Session, current: FederationOnly, year_from: YearFrom = None, year_to: YearTo = None):
    y1, y2 = _years(year_from, year_to)
    report = await build_headcount(session, y1, y2)
    content = build_headcount_xlsx(report, datetime.now(timezone(timedelta(hours=5))))
    await log_action(session, request, user_id=current.user.id, active_role=current.active_role,
                     action="report.headcount_export", entity_type="report", diff={"years": [y1, y2]})
    await session.commit()
    return attachment(content, XLSX, f"headcount_{y1}-{y2}.xlsx", f"Численность занимающихся {y1}-{y2}.xlsx")
