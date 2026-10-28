"""Динамика численности занимающихся (С8).

Спортсмен считается занимающимся в году Y, если у него есть занятия по дисциплине,
пересекающиеся с календарным годом. Возраст считается на 31 декабря года.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgeGroup,
    AthleteEnrollment,
    CoachAthleteLink,
    Discipline,
    JudgeCategoryAssignment,
    Municipality,
    Organization,
    User,
)
from app.models.enums import LinkStatus, OrgType
from app.services.eligibility import age_on

ORG_TYPE_LABELS = {
    OrgType.SCHOOL: "Школа",
    OrgType.UNIVERSITY: "Вуз",
    OrgType.SPORTS_SCHOOL: "Спортивная школа",
    OrgType.CLUB: "Клуб",
    OrgType.OTHER: "Колледж / иная организация",
}
NO_ORG = "Без организации"


@dataclass
class Row:
    label: str
    counts: dict[int, int]
    extra: str = ""


@dataclass
class HeadcountReport:
    years: list[int]
    total: dict[int, int]
    new: dict[int, int]
    coaches: dict[int, int]
    judges: dict[int, int]
    municipalities: list[Row] = field(default_factory=list)
    organizations: list[Row] = field(default_factory=list)
    disciplines: list[Row] = field(default_factory=list)
    age_groups: list[Row] = field(default_factory=list)
    matrix_year: int = 0
    matrix_columns: list[str] = field(default_factory=list)
    matrix: list[tuple[str, dict[str, int]]] = field(default_factory=list)


def _overlaps(start: date, end: date | None, year: int) -> bool:
    return start <= date(year, 12, 31) and (end is None or end >= date(year, 1, 1))


async def build_headcount(session: AsyncSession, year_from: int, year_to: int) -> HeadcountReport:
    years = list(range(year_from, year_to + 1))
    municipalities = list(await session.scalars(select(Municipality).order_by(Municipality.name)))
    organizations = list(await session.scalars(select(Organization).order_by(Organization.name)))
    disciplines = list(await session.scalars(select(Discipline).order_by(Discipline.id)))
    groups = list(await session.scalars(select(AgeGroup).order_by(AgeGroup.min_age)))
    enrollments = (await session.execute(
        select(AthleteEnrollment, User.birth_date, User.municipality_id).join(User, User.id == AthleteEnrollment.athlete_id)
    )).all()

    first_start: dict[int, date] = {}
    for e, _, _ in enrollments:
        if e.athlete_id not in first_start or e.start_date < first_start[e.athlete_id]:
            first_start[e.athlete_id] = e.start_date

    min_age = groups[0].min_age if groups else 0

    def bucket(age: int) -> str:
        for g in groups:
            if g.min_age <= age <= g.max_age:
                return g.name
        return f"Младше {min_age} лет" if age < min_age else "Вне возрастных групп"

    bucket_labels = [g.name for g in groups]
    extra_bucket = f"Младше {min_age} лет"
    if any(age_on(b, date(year_to, 12, 31)) < min_age for _, b, _ in enrollments):
        bucket_labels.insert(0, extra_bucket)

    report = HeadcountReport(years=years, total={}, new={}, coaches={}, judges={})
    muni = {m.id: {y: set() for y in years} for m in municipalities}
    org = {o.id: {y: set() for y in years} for o in organizations}
    org["none"] = {y: set() for y in years}
    disc = {d.id: {y: set() for y in years} for d in disciplines}
    age = {label: {y: set() for y in years} for label in bucket_labels}

    for y in years:
        athletes: set[int] = set()
        for e, birth, muni_id in enrollments:
            if not _overlaps(e.start_date, e.end_date, y):
                continue
            athletes.add(e.athlete_id)
            if muni_id in muni:
                muni[muni_id][y].add(e.athlete_id)
            org[e.organization_id if e.organization_id in org else "none"][y].add(e.athlete_id)
            disc[e.discipline_id][y].add(e.athlete_id)
            label = bucket(age_on(birth, date(y, 12, 31)))
            age.setdefault(label, {yy: set() for yy in years})[y].add(e.athlete_id)
        report.total[y] = len(athletes)
        report.new[y] = sum(1 for a, d in first_start.items() if d.year == y and a in athletes)

    def to_rows(source: dict, labels: dict, extras: dict | None = None) -> list[Row]:
        return [Row(labels[k], {y: len(v[y]) for y in years}, (extras or {}).get(k, "")) for k, v in source.items() if k in labels]

    report.municipalities = to_rows(muni, {m.id: m.name for m in municipalities})
    org_labels = {o.id: o.name for o in organizations} | {"none": NO_ORG}
    org_types = {o.id: ORG_TYPE_LABELS[o.type] for o in organizations} | {"none": "–"}
    report.organizations = to_rows(org, org_labels, org_types)
    report.disciplines = to_rows(disc, {d.id: d.name for d in disciplines})
    report.age_groups = [Row(label, {y: len(v[y]) for y in years}) for label, v in age.items()]

    # дисциплины × возраст на последний год
    report.matrix_year = year_to
    report.matrix_columns = list(age.keys())
    pairs: dict[int, dict[str, set[int]]] = {d.id: {label: set() for label in age} for d in disciplines}
    for e, birth, _ in enrollments:
        if _overlaps(e.start_date, e.end_date, year_to):
            pairs[e.discipline_id][bucket(age_on(birth, date(year_to, 12, 31)))].add(e.athlete_id)
    report.matrix = [(d.name, {label: len(pairs[d.id][label]) for label in age}) for d in disciplines]

    # тренеры и судьи
    links = (await session.execute(
        select(CoachAthleteLink.coach_id, CoachAthleteLink.confirmed_at, CoachAthleteLink.ended_at)
        .where(CoachAthleteLink.confirmed_at.is_not(None), CoachAthleteLink.status.in_([LinkStatus.ACTIVE, LinkStatus.ENDED, LinkStatus.SUSPENDED]))
    )).all()
    cats = (await session.execute(select(JudgeCategoryAssignment.judge_id, JudgeCategoryAssignment.assigned_at, JudgeCategoryAssignment.valid_until))).all()
    for y in years:
        report.coaches[y] = len({c for c, start, end in links if _overlaps(start.date(), end.date() if end else None, y)})
        report.judges[y] = len({j for j, start, end in cats if _overlaps(start, end, y)})
    return report
