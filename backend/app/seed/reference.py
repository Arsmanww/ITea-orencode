from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgeGroup,
    CompetitionType,
    ContentPage,
    Discipline,
    JudgeCategory,
    JudgePosition,
    Municipality,
    Organization,
    Rank,
    RankRequirement,
    RatingRule,
    RatingSettings,
    Role,
    Season,
)
from app.models.enums import CompetitionLevel, RatingTier, RoleCode
from app.seed import data

ROLE_NAMES = {
    RoleCode.FEDERATION: "Федерация",
    RoleCode.ATHLETE: "Спортсмен",
    RoleCode.COACH: "Тренер",
    RoleCode.JUDGE: "Судья",
    RoleCode.MINISTRY: "Министерство спорта",
}


@dataclass
class Refs:
    roles: dict[RoleCode, Role]
    municipalities: list[Municipality]
    organizations: list[Organization]
    disciplines: dict[str, Discipline]
    short_names: dict[str, str]
    age_groups: dict[str, AgeGroup]
    types: dict[str, CompetitionType]
    ranks: list[Rank]
    categories: list[JudgeCategory]
    positions: list[JudgePosition]


async def seed_references(session: AsyncSession) -> Refs:
    roles = {code: Role(code=code, name=name) for code, name in ROLE_NAMES.items()}
    municipalities = [Municipality(name=n) for n in data.MUNICIPALITIES]
    disciplines = {c: Discipline(code=c, name=n) for c, n, _ in data.DISCIPLINES}
    types = {n: CompetitionType(name=n) for n in data.COMPETITION_TYPES}
    ranks = [Rank(code=c, name=n, order_no=o, validity_months=v) for c, n, o, v in data.RANKS]
    categories = [JudgeCategory(code=c, name=n, order_no=o, validity_months=v) for c, n, o, v in data.JUDGE_CATEGORIES]
    positions = [JudgePosition(name=n) for n in data.JUDGE_POSITIONS]
    age_groups = {k: AgeGroup(name=n, min_age=lo, max_age=hi) for k, n, lo, hi in data.AGE_GROUPS}

    session.add_all(
        [*roles.values(), *municipalities, *disciplines.values(), *types.values(),
         *ranks, *categories, *positions, *age_groups.values()]
    )
    await session.flush()

    organizations = [
        Organization(name=n, type=t, municipality_id=municipalities[m].id, address=f"{data.MUNICIPALITIES[m]}, ул. Школьная, {i + 1}")
        for i, (n, t, m) in enumerate(data.ORGANIZATIONS)
    ]
    session.add_all(organizations)

    by_code = {r.code: r for r in ranks}
    session.add_all(
        RankRequirement(rank_id=by_code[code].id, level=CompetitionLevel(level), max_place=mp, min_participants=mn)
        for code, level, mp, mn in data.RANK_REQUIREMENTS
    )
    session.add_all(
        RatingRule(tier=RatingTier(tier), place=place, points=pts)
        for tier, points in data.RATING_POINTS
        for place, pts in enumerate(points, start=1)
    )
    session.add(RatingSettings())
    session.add_all(
        Season(name=f"Сезон {y}", date_from=date(y, 1, 1), date_to=date(y, 12, 31)) for y in range(2023, 2028)
    )
    session.add_all(
        ContentPage(
            slug=slug, title=title, body_md=body, order_no=order,
            discipline_id=disciplines[disc].id if disc else None,
        )
        for slug, title, order, disc, body in ((s, t, o, d, b) for s, t, o, d, b in data.CONTENT_PAGES)
    )
    await session.flush()

    return Refs(
        roles=roles,
        municipalities=municipalities,
        organizations=organizations,
        disciplines=disciplines,
        short_names={c: s for c, _, s in data.DISCIPLINES},
        age_groups=age_groups,
        types=types,
        ranks=ranks,
        categories=categories,
        positions=positions,
    )
